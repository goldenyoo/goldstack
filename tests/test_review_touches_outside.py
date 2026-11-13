"""goldstack-v38 05: 티켓 diff의 파일 중 touches 밖 경로를 첫 리뷰 프롬프트에 싣고 보고서에 `touches 밖:` 줄을 남긴다(spec 결정 2-6)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support

from gs import config, review, state, report

D = Path("/d.patch")
ANSWER = {"findings": []}


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


class OutsideTouchesTest(unittest.TestCase):
    """실제 임시 레포의 diff(merge-base..branch)를 touches와 대조한다. 리뷰어는 GS_REVIEWER_CMD seam, 판단 모델은 classify 대체."""

    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "keep.txt").write_text("k")
        (self.repo / "old.py").write_text("o")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "checkout", "-qb", "ticket")
        (self.repo / "src").mkdir()
        (self.repo / "src/a.py").write_text("a")
        (self.repo / "src/b.py").write_text("b")
        (self.repo / "src/deep").mkdir()
        (self.repo / "src/deep/c.py").write_text("c")
        git(self.repo, "rm", "-q", "old.py")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "ticket")
        self.answer = self.root / "answer.json"
        self.answer.write_text(json.dumps(ANSWER))
        self.cfg = SimpleNamespace(models=config.ModelsConfig("judge", "review", "agy", "codex"),
                                   timeouts=config.TimeoutsConfig(30, 10, 60))
        for p in (mock.patch.dict(os.environ, {"GS_REVIEWER_CMD": f"cat {self.answer}"}),
                  mock.patch.object(review, "_env", side_effect=lambda wt: dict(os.environ)),
                  mock.patch.object(review, "classify", return_value="")):
            p.start()
            self.addCleanup(p.stop)

    def run_review(self, touches):
        rdir = self.root / "r" / str(len(list((self.root / "r").glob("*")) if (self.root / "r").exists() else []))
        rec = review.run(repo=self.repo, worktree=self.repo, rdir=rdir, base="main", branch="ticket",
                         ticket=self.root / "ticket.md", spec=self.root / "spec.md", model="claude", reviewer="codex",
                         cfg=self.cfg, touches=touches)
        return rec, (rdir / "prompt.md").read_text(encoding="utf-8")

    def test_paths_outside_touches_are_listed_in_prompt(self):
        rec, prompt = self.run_review(["src/a.py"])
        section = prompt.split(f"{review.OUTSIDE_TITLE}:", 1)[1].split("\n경로마다", 1)[0]
        rows = [line for line in section.splitlines() if line.startswith("- ")]
        # diff 순서(경로 사전순): 지운 old.py도 touches 밖이다. src/a.py는 touches 안이라 실리지 않는다
        self.assertEqual(rows, ["- `old.py`", "- `src/b.py`", "- `src/deep/c.py`"])
        self.assertIn("정당", prompt)
        self.assertIn("지적", prompt)
        self.assertEqual(rec["touches_outside"], ["old.py", "src/b.py", "src/deep/c.py"])

    def test_only_b_is_listed_when_touches_cover_the_rest(self):
        rec, prompt = self.run_review(["src/a.py", "old.py", "src/deep/"])
        self.assertIn(f"{review.OUTSIDE_TITLE}:", prompt)
        self.assertIn("- `src/b.py`\n", prompt)
        self.assertNotIn("- `src/a.py`", prompt)
        self.assertNotIn("- `old.py`", prompt)
        self.assertNotIn("- `src/deep/c.py`", prompt)
        self.assertEqual(rec["touches_outside"], ["src/b.py"])

    def test_glob_covering_all_paths_has_no_section(self):
        _, covered = self.run_review(["src/*.py", "src/**/*.py", "old.py"])
        self.assertNotIn(review.OUTSIDE_TITLE, covered)
        rec, _ = self.run_review(["src/*.py", "src/**/*.py", "old.py"])
        self.assertNotIn("touches_outside", rec)
        # `*`는 `/`를 넘지 않는다: src/*.py만으로는 src/deep/c.py가 밖이다
        rec, prompt = self.run_review(["src/*.py", "old.py"])
        self.assertEqual(rec["touches_outside"], ["src/deep/c.py"])

    def test_unnormalized_touches_do_not_flag_declared_paths(self):
        # check._touches_overlap처럼 `./`·`//`·끝 `/`가 있어도 같은 경로로 본다(tests/test_touches.py)
        rec, prompt = self.run_review(["./src//a.py", "src/b.py", "src/deep/**", "old.py"])
        self.assertNotIn(review.OUTSIDE_TITLE, prompt)
        self.assertNotIn("touches_outside", rec)
        rec, _ = self.run_review(["./src/a.py", "src//b.py", "./src/deep//", "./old.py"])
        self.assertNotIn("touches_outside", rec)

    def test_no_touches_means_no_section_and_unchanged_prompt(self):
        for touches in (None, []):
            with self.subTest(touches=touches):
                rec, prompt = self.run_review(touches)
                self.assertNotIn(review.OUTSIDE_TITLE, prompt)
                self.assertNotIn("touches_outside", rec)
                plain = review.review_prompt(D, D, D, D, family="codex")
                self.assertNotIn(review.OUTSIDE_TITLE, plain)


class PromptTest(unittest.TestCase):
    def test_section_only_in_first_review_prompt_and_only_with_paths(self):
        plain = review.review_prompt(D, D, D, D, D, family="codex")
        self.assertEqual(review.review_prompt(D, D, D, D, D, family="codex", outside=[]), plain)
        self.assertEqual(review.review_prompt(D, D, D, D, D, family="codex", outside=None), plain)
        asked = review.review_prompt(D, D, D, D, D, family="codex", outside=["x/y.py"])
        self.assertIn(f"{review.OUTSIDE_TITLE}:", asked)
        self.assertIn("- `x/y.py`", asked)
        self.assertLess(asked.index(review.OUTSIDE_TITLE), asked.index("답은 아래 JSON"))
        self.assertNotIn(review.OUTSIDE_TITLE, review.rereview_prompt(D, D, D, D, D, family="codex"))
        self.assertNotIn(review.OUTSIDE_TITLE, review.repair_review_prompt(D, "log", D, D, D, family="codex"))

    def test_in_touches_matches_exact_glob_and_directory(self):
        self.assertTrue(review.in_touches("src/a.py", ["src/a.py"]))
        self.assertTrue(review.in_touches("src/a.py", ["src/*.py"]))
        self.assertTrue(review.in_touches("src/x/a.py", ["src/**/*.py"]))
        self.assertTrue(review.in_touches("docs/guide.md", ["docs/"]))
        self.assertTrue(review.in_touches("docs/guide.md", ["docs"]))
        self.assertFalse(review.in_touches("docs2/guide.md", ["docs"]))
        self.assertFalse(review.in_touches("src/x/a.py", ["src/*.py"]))
        self.assertFalse(review.in_touches("src/b.py", ["src/a.py"]))
        self.assertTrue(review.in_touches("src/a.py", ["./src/a.py"]))
        self.assertTrue(review.in_touches("src/a.py", ["src//a.py"]))
        self.assertTrue(review.in_touches("src/a.py", ["./src//*.py"]))
        self.assertTrue(review.in_touches("docs/guide.md", ["./docs//"]))
        self.assertFalse(review.in_touches("src/b.py", ["./src/a.py"]))


class ReportLineTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        rundir = repo / ".goldstack/work/demo/run"
        rundir.mkdir(parents=True)
        st = state.State(feature="demo", finish={"phase": "verified", "url": "https://example.com/pr/1"})
        self.ts = st.ticket("01")
        self.ts.status = state.MERGED
        self.r = SimpleNamespace(st=st, name="demo", order=["01"], repo=repo, iwt=repo,
                                 rundir=rundir, base="main", base_ref="origin/main", remote="origin",
                                 cfg=config.Config(config.GitConfig("origin", "main"),
                                                   config.ModelsConfig("opus", "opus", "agy", "codex"),
                                                   config.TimeoutsConfig(30, 30, 60), config.NotifyConfig(False)),
                                 feat=SimpleNamespace(tickets={"01": SimpleNamespace(title="티켓")},
                                                      spec=SimpleNamespace(verify="true", path=repo / "spec.md")))

    def results_table(self):
        return report.evidence(self.r).split("### 티켓별 결과", 1)[1].split("### 리뷰 지적", 1)[0]

    def test_report_shows_touches_outside_line_in_ticket_result(self):
        self.ts.review = {"reviewer": "codex", "findings": [], "touches_outside": ["src/b.py", "old.py"]}
        self.ts.second_review = {"reviewer": "agy", "findings": [], "touches_outside": ["old.py", "z.md"]}
        table = self.results_table()
        row = next(line for line in table.splitlines() if line.startswith("| 01 |"))
        self.assertIn("touches 밖: `src/b.py`, `old.py`, `z.md`", row)

    def test_no_line_without_paths(self):
        self.ts.review = {"reviewer": "codex", "findings": []}
        self.assertNotIn("touches 밖", self.results_table())
        self.ts.review = {"reviewer": "codex", "findings": [], "touches_outside": []}
        self.assertNotIn("touches 밖", self.results_table())
        self.ts.review = {}
        self.assertNotIn("touches 밖", self.results_table())


if __name__ == "__main__":
    unittest.main()
