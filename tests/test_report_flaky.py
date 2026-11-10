"""보고서 Summary의 flaky 줄과 integration 검증 실패의 티켓 이유."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import finish, git, report, state
import support

NEW = "\nflaky: {} {} 따로 돌려 통과, 전체 다시 통과\n"
OLD = "\nflaky: {} 재시도 {}번 만에 통과\n"


class ReportFlakyTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        support.sh(repo, "git", "init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            support.sh(repo, "git", "config", key, value)
        support.sh(repo, "git", "commit", "-qm", "init", "--allow-empty")
        self.rundir = repo / ".goldstack/work/demo/run"
        (self.rundir / "finish").mkdir(parents=True)
        (self.rundir / "05").mkdir()
        st = state.State(feature="demo", finish={"phase": "verified", "integration_ok": True, "main_ok": True})
        st.ticket("05").status = state.MERGED
        tickets = {"05": SimpleNamespace(title="티켓 05", touches=[])}
        self.r = SimpleNamespace(st=st, name="demo", order=["05"], repo=repo, iwt=repo, rundir=self.rundir,
                                 base="main", base_ref="origin/main", remote="origin",
                                 feat=SimpleNamespace(tickets=tickets, spec=SimpleNamespace(verify="check")))

    def ticket_log(self, text):
        (self.rundir / "05/verify.log").write_text("$ check\n" + text)

    def finish_log(self, label, text):
        (self.rundir / f"finish/{label}-verify.log").write_text("$ check\n" + text)

    def summary(self):
        text = report.write(self.r, "요약").read_text()
        return text.split("## Evidence")[0]

    def test_new_lines_from_ticket_integration_and_main_logs(self):
        self.ticket_log(NEW.format("ticket-05", "test_resume_report"))
        self.finish_log("integration", NEW.format("integration", "test_a test_b"))
        self.finish_log("main", NEW.format("main", "test_c"))
        text = self.summary()
        self.assertIn("- flaky: 05 티켓 검증 test_resume_report (따로 돌려 통과, 전체 다시 통과)", text)
        self.assertIn("- flaky: integration test_a test_b (따로 돌려 통과, 전체 다시 통과)", text)
        self.assertIn("- flaky: main test_c (따로 돌려 통과, 전체 다시 통과)", text)

    def test_old_retry_line_says_the_file_is_unknown(self):
        self.ticket_log(OLD.format("ticket-05", 2))
        self.finish_log("integration-final", OLD.format("integration-final", 1))
        text = self.summary()
        self.assertIn("- flaky: 05 티켓 검증 (전체 재시도 2번 만에 통과, 시험 파일 모름)", text)
        self.assertIn("- flaky: integration-final (전체 재시도 1번 만에 통과, 시험 파일 모름)", text)

    def test_flaky_lines_sit_under_the_status_line_not_in_the_model_summary(self):
        self.ticket_log(NEW.format("ticket-05", "test_x"))
        text = self.summary()
        status = text.index("마무리: verified")
        self.assertLess(status, text.index("- flaky: 05 티켓 검증 test_x"))
        self.assertLess(text.index("요약"), status)

    def test_no_flaky_leaves_the_summary_unchanged(self):
        self.ticket_log("OK\n")
        self.finish_log("integration", "OK\n")
        self.assertEqual(report.flaky_lines(self.r), [])
        self.assertNotIn("- flaky:", self.summary())

    def test_same_flaky_line_appears_once(self):
        self.ticket_log(NEW.format("ticket-05", "test_x") * 2)
        self.assertEqual(len(report.flaky_lines(self.r)), 1)

    def reason(self):
        row = next(x for x in report.evidence(self.r).splitlines() if x.startswith("| 05 |"))
        return row.split("|")[4].strip()

    def test_not_merged_by_each_integration_verify_names_the_failed_step(self):
        for label in ("integration", "integration-final", "integration-recheck"):
            with self.subTest(label=label):
                self.r.st.finish = {"phase": "not_merged", "integration_ok": False, "failed_verify": label}
                self.assertEqual(self.reason(), f"integration에 병합(티켓 검증 통과) · {label} 검증 실패")

    def test_verified_keeps_the_current_reason(self):
        self.assertEqual(self.reason(), "integration에 병합·검증됨")

    def test_not_merged_without_an_integration_failure_keeps_the_current_reason(self):
        self.r.st.finish = {"phase": "not_merged", "integration_ok": True}
        self.assertEqual(self.reason(), "integration에 병합·검증됨")
        self.r.st.finish = {"phase": "reverted", "main_ok": False, "failed_verify": "integration"}
        self.assertEqual(self.reason(), "integration에 병합·검증됨")

    def test_a_reason_written_on_the_ticket_is_kept(self):
        self.r.st.finish = {"phase": "not_merged", "integration_ok": False, "failed_verify": "integration"}
        self.r.st.tickets["05"].reason = "티켓에 적힌 이유"
        self.assertEqual(self.reason(), "티켓에 적힌 이유")

    def test_recheck_failure_leaves_failed_verify_for_the_report(self):
        head = "a" * 40
        saved = {}
        r = SimpleNamespace(repo=self.r.repo, remote="origin", ihead="", iwt=self.r.repo,
                            st=SimpleNamespace(finish={"merge_head": "b" * 40}))
        with (mock.patch.object(git, "run"), mock.patch.object(finish, "_restore_integration"),
              mock.patch.object(finish, "_verify", return_value=False) as verify,
              mock.patch.object(finish, "_save", side_effect=lambda _r, **kw: saved.update(kw))):
            self.assertFalse(finish._refresh_check_head(r, {"headRefOid": head}))
        self.assertEqual(verify.call_args.args[2], "integration-recheck")
        self.assertEqual(saved["failed_verify"], "integration-recheck")
        self.assertEqual(saved["phase"], "not_merged")


if __name__ == "__main__":
    unittest.main()
