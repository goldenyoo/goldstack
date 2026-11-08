"""codex 리뷰어는 리뷰마다 새로 만든 빈 임시 폴더에서 workspace-write로 돈다. worktree는 쓰지 못하고 네트워크는 꺼진다."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, review

ANSWER = json.dumps({"findings": [], "verdicts": []})


class CodexReviewSandboxTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.wt = self.root / "wt"
        self.wt.mkdir()
        self.cfg = SimpleNamespace(models=config.ModelsConfig("judge", "review", "agy", "codex"),
                                   timeouts=config.TimeoutsConfig(30, 10, 60))
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GS_REVIEWER_CMD", None)

    def run_review(self, family="codex", nth=0, fail_first=False):
        """review.run/rereview/repair_review를 가짜 `_call`로 돌린다. 호출마다 (argv, 그때 -C 폴더의 상태)를 모아 돌려준다."""
        seen = []

        def call(argv, **kwargs):
            entry = {"argv": argv, "prompt": kwargs.get("prompt")}
            if "-C" in argv:
                scratch = Path(argv[argv.index("-C") + 1])
                entry.update(scratch=scratch, existed=scratch.is_dir(), entries=sorted(p.name for p in scratch.iterdir()),
                             tmp_writable=os.access(scratch, os.W_OK))
                (scratch / "probe").write_text("리뷰어가 쓴 임시 파일")  # 리뷰어가 시험하다 남긴 파일
            seen.append(entry)
            if fail_first and len(seen) == 1:
                raise review.ReviewTransient("연결 끊김")
            Path(argv[argv.index("--output-last-message") + 1]).write_text(ANSWER)
            return "events"

        rdir = self.root / "rdir" / str(nth)
        with mock.patch.object(review, "_call", side_effect=call), \
                mock.patch.object(review, "_env", return_value={}), \
                mock.patch.object(review, "call_waiting", new=lambda f, cfg, on_wait=None, family="": _retry_once(f)), \
                mock.patch.object(review, "write_diff", return_value=("base", False)), \
                mock.patch.object(review.git, "run", return_value=SimpleNamespace(stdout="diff")):
            common = dict(repo=self.wt, worktree=self.wt, rdir=rdir, ticket=self.root / "ticket", spec=self.root / "spec",
                          reviewer=family, cfg=self.cfg)
            if nth == "수리":
                review.repair_review(**common, base="base", head="head", verify_log="verify")
            elif nth:
                review.rereview(**common, base="base", head="head", found=[], nth=nth)
            else:
                review.run(**common, base="base", branch="branch", model="claude")
        return seen, rdir

    def test_argv_is_workspace_write_without_network_in_a_fresh_empty_dir(self):
        for nth in (0, 1, "수리"):
            with self.subTest(nth=nth):
                seen, _ = self.run_review(nth=nth)
                self.assertEqual(len(seen), 1)
                argv, scratch = seen[0]["argv"], seen[0]["scratch"]
                self.assertNotIn("read-only", argv)
                self.assertEqual(argv[argv.index("-s") + 1], "workspace-write")
                configs = [argv[i + 1] for i, a in enumerate(argv) if a == "-c"]
                self.assertIn("sandbox_workspace_write.network_access=false", configs)
                self.assertNotEqual(scratch, self.wt)
                self.assertNotIn(self.wt, scratch.parents)
                self.assertNotIn(scratch, self.wt.parents)
                self.assertTrue(seen[0]["existed"])
                self.assertEqual(seen[0]["entries"], [], "리뷰어를 띄울 때 -C 폴더는 비어 있어야 한다")

    def test_scratch_dir_is_removed_after_review(self):
        for nth in (0, 1, "수리"):
            with self.subTest(nth=nth):
                seen, _ = self.run_review(nth=nth)
                self.assertTrue(seen[0]["existed"])
                self.assertFalse(seen[0]["scratch"].exists(), "리뷰가 끝나면 임시 폴더를 지운다(안에 리뷰어가 남긴 파일 포함)")

    def test_scratch_dir_is_removed_when_the_call_fails(self):
        def boom(argv, **kwargs):
            seen.append(Path(argv[argv.index("-C") + 1]))
            raise review.ReviewError("실패")
        seen = []
        with mock.patch.object(review, "_call", side_effect=boom), mock.patch.object(review, "_env", return_value={}), \
                mock.patch.object(review, "write_diff", return_value=("base", False)), \
                mock.patch.object(review.git, "run", return_value=SimpleNamespace(stdout="diff")):
            rec = review.run(repo=self.wt, worktree=self.wt, rdir=self.root / "failed", ticket=self.root / "t",
                             spec=self.root / "s", reviewer="codex", cfg=self.cfg, base="base", branch="b", model="claude")
        self.assertIn("리뷰 실패", rec["note"])
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_retry_after_a_cut_call_gets_another_fresh_empty_dir(self):
        seen, _ = self.run_review(fail_first=True)
        self.assertEqual(len(seen), 2)
        first, second = seen[0]["scratch"], seen[1]["scratch"]
        self.assertNotEqual(first, second)
        self.assertEqual(seen[1]["entries"], [])
        self.assertFalse(first.exists() or second.exists())

    def test_prompt_tells_codex_the_worktree_path_and_where_it_may_write(self):
        seen, rdir = self.run_review()
        text = (rdir / "prompt.md").read_text(encoding="utf-8")
        self.assertIn(str(self.wt), text)
        self.assertIn("쓰기는 지금 디렉터리(임시 폴더)와 TMPDIR에만", text)
        self.assertIn("worktree는 쓰기가 막혀 있고", text)
        self.assertEqual(seen[0]["prompt"], text)
        p = Path("x")
        for prompt in (review.rereview_prompt(p, p, p, p, p, family="codex"),
                       review.repair_review_prompt(p, "log", p, p, p, family="codex")):
            self.assertIn("쓰기는 지금 디렉터리(임시 폴더)와 TMPDIR에만", prompt)
            self.assertNotIn("지금 디렉터리, 코드 맥락", prompt)

    def test_other_families_keep_their_worktree_and_prompt(self):
        p = Path("x")
        for family in ("", "agy", "claude"):
            with self.subTest(family=family):
                text = review.review_prompt(p, p, p, p, family=family)
                self.assertIn("구현 worktree(지금 디렉터리, 코드 맥락)", text)
                self.assertNotIn("TMPDIR", text)
        for family in ("claude", "agy"):
            argv, _, _ = review.reviewer_argv(family, self.wt, "prompt", self.root / "out", self.cfg.models)
            self.assertNotIn("workspace-write", argv)

    def test_custom_reviewer_command_makes_no_scratch_dir(self):
        os.environ["GS_REVIEWER_CMD"] = "true"
        with mock.patch.object(review.tempfile, "mkdtemp") as mk:
            argv, stdin, to_file = review.reviewer_argv("codex", self.wt, "prompt", self.root / "out", self.cfg.models)
        mk.assert_not_called()
        self.assertEqual((argv, stdin, to_file), (["bash", "-c", "true"], "prompt", False))


def _retry_once(call):
    """call_waiting 대신: 일시 오류면 기다리지 않고 한 번 더 부른다."""
    try:
        return call()
    except review.ReviewTransient:
        return call()


if __name__ == "__main__":
    unittest.main()
