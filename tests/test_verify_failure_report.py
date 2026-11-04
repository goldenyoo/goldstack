"""마무리 검증 실패의 원본 줄·후보 티켓과 후보 탐색 실패 시 보고서 보존."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import finish, report, state
import support


class FailureEvidenceTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        support.sh(repo, "git", "init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            support.sh(repo, "git", "config", key, value)
        support.sh(repo, "git", "commit", "-qm", "init", "--allow-empty")
        rundir = repo / ".goldstack/work/demo/run"
        (rundir / "finish").mkdir(parents=True)
        st = state.State(feature="demo", finish={"phase": "not_merged", "integration_ok": False,
                                                "failed_verify": "integration"})
        tickets = {tid: SimpleNamespace(title=f"티켓 {tid}", touches=touches) for tid, touches in (
            ("01", ["src/foo.py"]), ("02", []), ("03", ["test/**"]),
            ("04", ["src/unrelated.py"]), ("05", ["src/foo.py"]))}
        for tid in tickets:
            st.ticket(tid).status = state.MERGED
        st.tickets["05"].status = state.FAILED
        self.r = SimpleNamespace(st=st, name="demo", order=list(tickets), repo=repo, iwt=repo,
                                 rundir=rundir, base="main", base_ref="origin/main", remote="origin",
                                 feat=SimpleNamespace(tickets=tickets, spec=SimpleNamespace(verify="check")))
        self.log = rundir / "finish/integration-verify.log"

    def merge_ticket(self, tid, path):
        repo = self.r.repo
        support.sh(repo, "git", "checkout", "-qb", f"ticket-{tid}")
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("changed\n")
        support.sh(repo, "git", "add", "--", path)
        support.sh(repo, "git", "commit", "-qm", f"worker {tid}")
        support.sh(repo, "git", "checkout", "-q", "main")
        support.sh(repo, "git", "merge", "-q", "--no-ff", f"ticket-{tid}",
                   "-m", f"Merge {tid}\n\ngs-ticket: demo/{tid}")
        support.sh(repo, "git", "branch", "-D", f"ticket-{tid}")

    def test_paths_names_and_touches_glob_include_only_merged_candidates(self):
        self.merge_ticket("02", "lib/actual.test.js")
        self.log.write_text("FAIL: /tmp/project/src/foo.py:4\n"
                            "ERROR actual.test.js:8\nfailed src/other.py\nnot ok 3 test/foo.test.js\n")
        text = report.verification_failure(self.r)
        self.assertIn("### 검증 실패", text)
        self.assertIn(str(self.log.resolve()), text)
        self.assertIn("후보 티켓(추정): 01, 02, 03\n", text)
        for line in self.log.read_text().splitlines():
            self.assertIn(line, text)

    def test_only_first_ten_failure_lines_and_not_unrelated_output(self):
        self.log.write_text("passed src/foo.py\n" + "\n".join(f"not ok {i} unknown.js" for i in range(1, 14)))
        text = report.verification_failure(self.r)
        self.assertEqual(text.count("not ok "), 10)
        self.assertIn("not ok 10 unknown.js\n", text)
        self.assertNotIn("not ok 11", text)
        self.assertNotIn("passed src/foo.py", text)
        self.assertIn("후보 티켓(추정): 후보 없음", text)

    def test_filename_substrings_do_not_match(self):
        self.log.write_text("ERROR other_foo.py and unrelated.pyc\n")
        self.assertIn("후보 없음", report.verification_failure(self.r))

    def test_candidate_exception_does_not_prevent_writing_report(self):
        self.log.write_text("not ok 3 test/foo.test.js\n")
        with mock.patch.object(report, "_failure_candidates", side_effect=RuntimeError("broken lookup")):
            path = report.write(self.r, "요약")
        text = path.read_text()
        self.assertIn("not ok 3 test/foo.test.js", text)
        self.assertIn(str(self.log.resolve()), text)
        self.assertIn("후보 탐색 오류: broken lookup", text)
        self.assertIn("## Merge Danger", text)

    def test_missing_log_or_no_matching_lines_still_explains_failure(self):
        self.assertIn("로그를 읽지 못함", report.verification_failure(self.r))
        self.log.write_text("시간 초과: 1분\n")
        text = report.verification_failure(self.r)
        self.assertIn("해당 실패 줄 없음", text)
        self.assertIn("후보 없음", text)

    def test_success_report_is_unchanged_even_with_stale_failure_log(self):
        self.r.st.finish = {"phase": "verified", "integration_ok": True, "main_ok": True}
        self.log.write_text("FAIL src/foo.py\n")
        self.r.st.finish["failed_verify"] = "integration"
        # verify 출력에는 원래부터 로그가 붙는다. 같은 로그가 있는 기존 렌더링과 비교한다.
        with mock.patch.object(report, "verification_failure", return_value=""):
            expected = report.write(self.r, "요약").read_text()
        with mock.patch.object(report, "_failure_candidates", side_effect=AssertionError("호출하면 안 됨")):
            text = report.write(self.r, "요약").read_text()
        self.assertEqual(text, expected)
        self.assertNotIn("### 검증 실패", text)
        self.assertNotIn("후보 티켓", text)


class FinishFailureReportTest(support.GoTest):
    def configure(self, command):
        path = self.repo / ".goldstack/work/demo/spec.md"
        path.write_text('---\nfeature: demo\nmax_workers: 1\nverify_ticket: "true"\n'
                        f'verify: {json.dumps(command)}\n---\n')
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", "verify failure scenario")
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def assert_failure(self, label):
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "not_merged")
        text = self.final_report()
        section = text.split("### 검증 실패\n", 1)[1].split("### 티켓별 결과", 1)[0]
        self.assertIn(f"검증: `{label}`", section)
        self.assertIn(str(self.rundir / f"finish/{label}-verify.log"), section)
        self.assertIn("not ok 3 file_01", section)
        self.assertIn("후보 티켓(추정): 01", section)
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), text)
        self.assertFalse(any(line.startswith("pr merge ") for line in self.lines("gh.log")))

    def test_integration_failure_reports_changed_file_after_branch_cleanup(self):
        self.configure("echo 'not ok 3 file_01'; exit 1")
        # 옛 integration-final 로그가 있어도 이번에 실패한 integration 로그를 고른다.
        (self.rundir / "finish").mkdir(parents=True)
        (self.rundir / "finish/integration-final-verify.log").write_text("ERROR stale.js\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assert_ticket_cleaned("01")
        self.assert_failure("integration")

    def test_integration_final_failure_uses_final_log(self):
        script = self.bin / "verify.sh"
        script.write_text("if [ -f extra ]; then echo 'not ok 3 file_01'; exit 1; fi\necho pass\n")
        self.configure(f"bash {script}")
        original = finish._commit_report
        changed = []

        def commit(r, summary):
            path = original(r, summary)
            if not changed:
                changed.append(True)
                (r.iwt / "extra").write_text("code change\n")
                support.sh(r.iwt, "git", "add", "extra")
                support.sh(r.iwt, "git", "commit", "-qm", "extra code")
            return path

        with mock.patch.object(finish, "_commit_report", side_effect=commit):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assert_failure("integration-final")


if __name__ == "__main__":
    unittest.main()
