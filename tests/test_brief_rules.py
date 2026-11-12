"""worker brief의 시험 규칙(바뀐 이름을 시험 폴더에서도 grep, 새 분기·호출 지점 시험)과 base 줄(goldstack-v33 03)."""
import tempfile
import unittest
from pathlib import Path

from gs import git, review, worker
from gs.feature import Spec, Ticket
import support

FINDING = {"id": "1", "severity": "high", "location": "a.py:1", "claim": "틀렸다", "evidence": "e"}
GREP_RULE = ("서명이나 읽는 속성을 바꾼 함수·클래스는 그 이름을 시험 폴더(이 레포는 profile을 본다. 예: `tests/`)에서도 grep한다. "
             "나온 시험 파일을 모두 파일마다 따로 돌리고, 돌린 파일 목록을 마지막 메시지에 적는다.")
BRANCHES = "diff가 더한 새 분기와 바꾼 호출 지점 모두를 시험한다"


class BriefRulesTest(unittest.TestCase):
    def briefs(self, blocked_by=None, merged=None, touches=None) -> dict[str, str]:
        """첫·재개 worker는 go.py처럼 merged를 받고, 수정·수리 worker는 받지 않는다."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="05", title="t", blocked_by=blocked_by or [], model="claude", reviewer="codex",
                            path=root / "05-t.md", body="## 목표\n하나", touches=touches or [])
            spec = Spec(feature="demo", verify="full", max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            out = {}
            for name, kwargs, tail in (
                    ("first", {"merged": merged}, ""),
                    ("resumed", {"resumed": True, "merged": merged}, ""),
                    ("fix1", {}, review.fix_brief([FINDING], 1)),
                    ("fix2", {}, review.fix_brief([FINDING], 2)),
                    ("repair", {}, review.repair_brief("/x/verify.log"))):
                job = worker.Job(ticket=ticket, worktree=root, rundir=root / name)
                job.rundir.mkdir()
                worker.write_brief(job, spec, "demo", "gs/demo/05", **kwargs)
                out[name] = job.brief.read_text(encoding="utf-8") + tail
            return out

    def test_every_brief_tells_to_grep_changed_names_in_tests(self):
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                self.assertIn(GREP_RULE, text)
                self.assertIn(worker.CHANGED_NAMES_RULE, text)
                self.assertEqual(text.count("나온 시험 파일을 모두 파일마다 따로 돌리고"), 1)

    def test_grep_rule_does_not_assume_the_test_folder(self):
        self.assertIn("시험 폴더(이 레포는 profile을 본다", worker.CHANGED_NAMES_RULE)

    def test_every_brief_asks_to_test_new_branches_and_changed_call_sites(self):
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                self.assertIn(BRANCHES, text)
                self.assertIn(worker.REAL_TEST_RULE, text)

    def test_every_brief_tells_to_write_left_observations(self):
        self.assertEqual(worker.OBSERVATIONS_HEADING, "## 남긴 관찰")
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                self.assertIn(worker.OBSERVATIONS_RULE, text)
                self.assertIn(f"`{worker.OBSERVATIONS_HEADING}` 제목 아래 한 줄에 하나씩 쓴다. 없으면 절을 쓰지 않는다", text)
                self.assertIn("리뷰가 짚지 않은 의심, 돌리지 못한 확인, touches 밖에서 고쳐야 할 것", text)

    def test_every_brief_tells_to_start_nested_sessions_with_gs_child(self):
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                self.assertIn("`gs child -- <명령>`으로 띄우고 모델·effort를 명령에 명시한다. `GS_*`를 지우지 않는다", text)

    def test_every_brief_tells_to_split_test_runs_without_dropping_files(self):
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                self.assertIn("hook이 한 명령의 시험 파일 수를 막으면 명령을 나눠 돌린다. 일부를 빼지 않는다.", text)
                self.assertNotRegex(text, r"시험 파일 \d+개")  # 상한 숫자는 레포 config 값이라 brief에 적지 않는다

    def test_first_and_resumed_briefs_list_touches(self):
        briefs = self.briefs(merged=[], touches=["src/a.py", "tests/test_a.py"])
        for name in ("first", "resumed"):
            with self.subTest(brief=name):
                self.assertIn(worker.TOUCHES_LABEL + "`src/a.py`, `tests/test_a.py`. touches 밖 파일은 고치지 않는다. "
                              "고쳐야 하면 `## 남긴 관찰`에 적는다.", briefs[name])

    def test_ticket_without_touches_has_no_touches_line(self):
        for name, text in self.briefs(merged=[]).items():
            with self.subTest(brief=name):
                self.assertNotIn(worker.TOUCHES_LABEL, text)
                self.assertNotIn("touches 밖 파일은 고치지 않는다", text)

    def test_fix_and_repair_briefs_do_not_get_the_first_workers_touches_line(self):
        briefs = self.briefs(merged=[], touches=["src/a.py"])
        for name in ("fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                self.assertNotIn(worker.TOUCHES_LABEL, briefs[name])
                self.assertNotIn("touches 밖 파일은 고치지 않는다", briefs[name])

    def test_base_line_without_merged_tickets(self):
        for name, text in self.briefs(merged=[]).items():
            if name in ("first", "resumed"):
                with self.subTest(brief=name):
                    self.assertIn("- base에 이미 병합된 티켓: 없음\n", text)
                    self.assertNotIn("아직 병합되지 않은", text)

    def test_base_line_lists_merged_tickets_with_commits(self):
        merged = [("04", "9fb522d"), ("01", "1a2b3c4")]
        for name, text in self.briefs(merged=merged).items():
            if name in ("first", "resumed"):
                with self.subTest(brief=name):
                    self.assertIn("- base에 이미 병합된 티켓: 04(9fb522d), 01(1a2b3c4)\n", text)
                    self.assertNotIn("없음", text)

    def test_fix_and_repair_briefs_have_no_base_line(self):
        briefs = self.briefs(merged=[("04", "9fb522d")])
        for name in ("fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                self.assertNotIn("base에 이미 병합된 티켓", briefs[name])

    def test_unmerged_blocked_by_is_listed_separately(self):
        briefs = self.briefs(blocked_by=["04", "02"], merged=[("04", "9fb522d")])
        for name in ("first", "resumed"):
            with self.subTest(brief=name):
                self.assertIn("- base에 이미 병합된 티켓: 04(9fb522d)\n", briefs[name])
                self.assertIn("- base에 아직 병합되지 않은 blocked_by 티켓: 02\n", briefs[name])

    def test_merged_blocked_by_is_not_listed_as_unmerged(self):
        text = self.briefs(blocked_by=["04"], merged=[("04", "9fb522d")])["first"]
        self.assertNotIn("아직 병합되지 않은", text)

    def test_replay_style_call_without_merged_still_works(self):
        text = self.briefs()["first"]
        self.assertNotIn("base에 이미 병합된 티켓", text)


class MergedTicketsTest(unittest.TestCase):
    """git.merged_tickets: worktree의 base에서 닿는 이번 feature의 티켓 병합 커밋."""

    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            self.git("config", key, value)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.git("branch", "base")

    def git(self, *args):
        return support.sh(self.repo, "git", *args)

    def merge(self, message):
        self.git("checkout", "-qb", "ticket")
        self.git("commit", "-q", "--allow-empty", "-m", "worker")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "ticket", "-m", message)
        self.git("branch", "-D", "ticket")
        return self.git("rev-parse", "--short", "HEAD")

    def test_none_merged(self):
        self.assertEqual(git.merged_tickets(self.repo, "f", "main", base_ref="base"), [])

    def test_lists_this_features_tickets_newest_first_with_commits(self):
        first = self.merge("Merge 01\n\ngs-ticket: f/01")
        self.merge("Merge other\n\ngs-ticket: g/09")
        second = self.merge("Merge 04\n\ngs-ticket: f/04")
        self.assertEqual(git.merged_tickets(self.repo, "f", "main", base_ref="base"), [("04", second), ("01", first)])

    def test_only_reads_up_to_the_given_base(self):
        first = self.merge("Merge 01\n\ngs-ticket: f/01")
        self.git("branch", "wt-base")
        self.merge("Merge 04\n\ngs-ticket: f/04")
        self.assertEqual(git.merged_tickets(self.repo, "f", "wt-base", base_ref="base"), [("01", first)])

    def test_worker_commit_marks_are_not_counted(self):
        self.git("commit", "-q", "--allow-empty", "-m", "worker\n\ngs-ticket: f/02")
        self.assertEqual(git.merged_tickets(self.repo, "f", "main", base_ref="base"), [])


if __name__ == "__main__":
    unittest.main()
