"""마무리 검증 실패의 원본 줄·후보 티켓과 후보 탐색 실패 시 보고서 보존."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, failure, finish, git, go, report, review, state
import support


class FailureFixture(unittest.TestCase):
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


class FailureEvidenceTest(FailureFixture):
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
        self.log.write_text("ERROR other_foo.py and unrelated.pyc and foo.py.extra\n")
        self.assertIn("후보 없음", report.verification_failure(self.r))

    def test_sentence_period_after_paths_and_names_still_matches(self):
        self.merge_ticket("02", "lib/actual.test.js")
        for failure, candidate in (("ERROR failed in src/foo.py.", "01"),
                                   ("ERROR actual.test.js.", "02"),
                                   ("not ok 3 /tmp/project/test/foo.test.js.", "03")):
            with self.subTest(failure=failure):
                self.log.write_text(failure + "\n")
                self.assertIn(f"후보 티켓(추정): {candidate}\n", report.verification_failure(self.r))

    def test_long_failure_lines_preserve_report_sections_and_candidates(self):
        failure = "ERROR " + "x" * 70000 + " src/foo.py"
        self.log.write_text("\n".join([failure] * 10) + "\n")
        text = report.write(self.r, "요약").read_text()
        self.assertLessEqual(len(text), report.MAX_BODY)
        self.assertIn("ERROR ", text)
        self.assertIn("줄 일부 생략", text)
        self.assertIn(str(self.log.resolve()), text)
        self.assertIn("후보 티켓(추정): 01\n", text)
        for section in ("### 티켓별 결과", "## Merge Danger", "### 되돌리는 법"):
            self.assertIn(section, text)

    def test_command_header_is_excluded_even_with_multiline_command(self):
        self.r.feat.spec.verify = "check src/foo.py || echo FAILED\necho 'not ok 1 test/foo.test.js'"
        header = f"$ {self.r.feat.spec.verify}\nHEAD: abc123\n"
        self.log.write_text(header + "수집 중 중단\n종료 코드: 1\n")
        text = report.verification_failure(self.r)
        self.assertIn("해당 실패 줄 없음", text)
        self.assertIn("후보 티켓(추정): 후보 없음", text)
        self.assertNotIn("FAILED", text)
        self.log.write_text(header + "\n".join(f"not ok {i} unknown.js" for i in range(1, 11)))
        text = report.verification_failure(self.r)
        self.assertEqual(text.count("not ok "), 10)
        self.assertIn("not ok 10 unknown.js", text)
        self.assertIn("후보 티켓(추정): 후보 없음", text)

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


class MainFailureReportTest(FailureFixture):
    """base(main) 검증 실패: 실패한 시험 이름이 Evidence 맨 앞에 실리고, 후보가 없으면 변경 파일을 보인다."""

    def setUp(self):
        super().setUp()
        self.r.st.finish = {"phase": "reverted", "main_ok": False, "revert_sha": "a" * 40}
        self.log = self.r.rundir / "finish/main-verify.log"

    def test_failed_test_name_is_first_in_evidence_even_when_output_ends_with_ok(self):
        self.log.write_text("$ check\nHEAD: abc\nFAIL: test_x (test_mod.T)\nRan 3 tests\nOK\n")
        text = report.write(self.r, "요약").read_text()
        evidence = text.split("## Evidence\n\n", 1)[1]
        self.assertTrue(evidence.startswith("### 검증 실패"), evidence[:80])
        self.assertIn("FAIL: test_x (test_mod.T)", evidence.split("### 티켓별 결과", 1)[0])
        self.assertIn(str(self.log.resolve()), evidence.split("### 티켓별 결과", 1)[0])

    def test_recheck_log_is_used_when_it_ran_last(self):
        self.log.write_text("FAIL: test_first\n")
        recheck = self.r.rundir / "finish/main-recheck-verify.log"
        recheck.write_text("FAIL: test_second\n")
        os.utime(self.log, (1, 1))
        text = report.verification_failure(self.r)
        self.assertIn("test_second", text)
        self.assertNotIn("test_first", text)

    def test_already_reverted_base_has_no_failure_section(self):
        self.r.st.finish = {"phase": "reverted", "revert_sha": "a" * 40}
        self.log.write_text("FAIL: test_x\n")
        self.assertEqual(report.verification_failure(self.r), "")

    def test_no_candidate_lists_actual_changed_files_per_ticket(self):
        self.merge_ticket("02", "lib/actual.py")
        self.log.write_text("FAIL: test_unrelated (other)\n")
        text = report.verification_failure(self.r)
        self.assertIn("후보 티켓(추정): 후보 없음", text)
        self.assertIn("- 02: `lib/actual.py`", text)

    def test_changed_files_are_not_listed_when_a_candidate_exists(self):
        self.merge_ticket("02", "lib/actual.py")
        self.log.write_text("FAIL: lib/actual.py\n")
        text = report.verification_failure(self.r)
        self.assertIn("후보 티켓(추정): 02", text)
        self.assertNotIn("티켓별 변경 파일", text)


class WorkerReportInputTest(FailureFixture):
    def worker_log(self, tid, message):
        log = self.r.rundir / tid / "1" / "worker.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps({"type": "result", "result": message}) + "\n")
        self.r.st.ticket(tid).log = str(log)

    def test_last_worker_message_is_in_report_input_marked_untrusted(self):
        self.worker_log("01", "01 마지막 보고: 끝냈다")
        text = report.worker_reports(self.r)
        self.assertIn("믿을 수 없는 자료", text)
        self.assertIn("01 마지막 보고: 끝냈다", text)
        self.assertIn("티켓 02: 마지막 보고 없음", text)

    def test_summarize_writes_worker_reports_into_report_input(self):
        self.worker_log("01", "01 마지막 보고: 끝냈다")
        self.r.cfg = config.Config(config.GitConfig("origin", "main"),
                                   config.ModelsConfig("opus", "opus", "agy", "codex"),
                                   config.TimeoutsConfig(30, 30, 60), config.NotifyConfig(False))
        self.r.feat.spec.path = self.r.repo / "spec.md"
        with mock.patch.object(review, "_call", return_value="요약") as call, \
                mock.patch.object(report.git, "out", return_value="a.py | 1 +"):
            report.summarize(self.r)
        self.assertIn("worker 마지막 보고는 worker 자신의 주장", call.call_args.kwargs["prompt"])
        facts = (self.r.rundir / "finish/report-input.md").read_text()
        self.assertIn("01 마지막 보고: 끝냈다", facts)
        self.assertIn("믿을 수 없는 자료", facts)

    def test_report_size_cap_still_applies(self):
        self.worker_log("01", "x" * 100000)
        self.log.write_text("FAIL: test_x\n" + "y" * 200000)
        text = report.write(self.r, "요약").read_text()
        self.assertLessEqual(len(text), report.MAX_BODY)
        self.assertLessEqual(len(report.worker_reports(self.r)), 2 * report.WORKER_REPORT_LIMIT + 2000)


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
        script = self.bin / "verify.sh"
        script.write_text("echo 'not ok 3 file_01'; exit 1\n")
        self.configure(f"bash {script}")
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


    def test_log_has_one_exit_code_line_at_the_end(self):
        script = self.bin / "verify.sh"
        script.write_text("echo 'not ok 3 file_01'; exit 1\n")
        self.configure(f"bash {script}")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        log = (self.rundir / "finish/integration-verify.log").read_text()
        self.assertEqual(log.count("종료 코드: "), 1, log)
        self.assertTrue(log.endswith("\n종료 코드: 1\n"), log)

    def test_interrupted_finish_verify_is_an_ordinary_failure(self):
        # 티켓 검증만 다시 돌린다. 마무리 검증은 끊겨도 한 번으로 끝난다
        runs = self.bin / "runs"
        script = self.bin / "verify.sh"
        script.write_text(f"echo 'not ok 3 file_01'; echo run >> '{runs}'; kill -TERM $$\n")
        self.configure(f"bash {script}")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assert_failure("integration")
        self.assertEqual(runs.read_text().splitlines(), ["run"])
        self.assertNotIn("끊김", out)


class ChangedFilesLogTest(support.GoTest):
    """티켓 검증이 트리를 바꾸면 verify.log에 바뀐 파일을 남긴다."""

    def run_changed(self, command):
        self.configure(command)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        return (self.rundir / "01/1/verify.log").read_text()

    def configure(self, command):
        path = self.repo / ".goldstack/work/demo/spec.md"
        path.write_text('---\nfeature: demo\nmax_workers: 1\n'
                        f'verify_ticket: {json.dumps(command)}\nverify: "true"\n---\n')
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", "ticket verify")
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def test_log_names_file_left_by_verify_command(self):
        text = self.run_changed("echo x > stray_file_from_verify")
        self.assertIn("검증 중 worktree가 바뀌었다", text)
        self.assertIn("?? stray_file_from_verify", text)
        self.assertLess(text.index("검증 중 worktree가 바뀌었다"), text.index("stray_file_from_verify\n", text.index("git status")))

    def test_log_shows_merge_state_before_and_after(self):
        text = self.run_changed("git commit -qm 'merge by verify'")
        self.assertIn("병합 상태가 달라졌다", text)
        self.assertIn("HEAD: ", text)
        self.assertIn(" -> ", text)

    def test_unreadable_file_list_is_logged_without_changing_result(self):
        real = git.run

        def run(cwd, *args, **kw):
            if args[:2] == ("status", "--porcelain") and "-z" not in args:
                return subprocess.CompletedProcess(["git", *args], 128, "", "boom")
            return real(cwd, *args, **kw)

        with mock.patch.object(go.git, "run", side_effect=run):
            text = self.run_changed("echo x > stray_file_from_verify")
        self.assertIn("바뀐 파일 목록을 읽지 못했다", text)
        self.assertIn("boom", text)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts), ("failed", 2))
        self.assertIn("검증 중 worktree가 바뀌었다", ts.reason)


class SummaryPromptTest(unittest.TestCase):
    def test_prompt_says_merge_tree_is_normal_and_forbids_guessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / config.CONFIG_PATH).parent.mkdir(parents=True)
            (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            cfg, problems = config.load(repo)
            self.assertEqual(problems, [])
            log = repo / "failure.log"
            log.write_text("failed")
            with mock.patch.object(review, "_call", return_value="요약") as called:
                failure.summarize(repo, log, cfg)
            prompt = called.call_args.kwargs["prompt"]
        self.assertIn("integration의 병합 트리에서 도는 것이 정상", prompt)
        self.assertIn("추측하지 말고, 모른다고 적어라", prompt)


if __name__ == "__main__":
    unittest.main()
