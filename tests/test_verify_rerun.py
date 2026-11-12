"""판별(verify 머리말, config `[verify]`, goldstack-v31 02): 실패한 시험 파일을 따로 돌려 1회성인지 가리고, 통과하면 전체를 한 번 더 돈다.

전체 명령과 판별 명령은 가짜 bash 조각이다. n번째 전체 실행이 무엇을 할지는 full.sh의 case가 정하고, 판별 명령은 받은 값을 rerun.calls에 적는다.
시간 초과와 시간 예산은 실제 시간에 기대지 않고 verify._run_once·_launch·_clock을 바꿔 본다.
"""
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_config
import test_verify_modes
from gs import config, metrics, replay, state, verify

REPO = Path(__file__).resolve().parents[1]
FAILED_FILE = r"^(?:FAIL|ERROR): \S+ \((test_\w+)\."


def fail(*modules):
    """unittest 실패 줄을 찍고 1로 끝나는 셸 조각."""
    lines = "".join(f"echo 'FAIL: test_x ({m}.Case.test_x)'; " for m in modules)
    return lines + "exit 1"


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "verify.log"
        self.unchanged = mock.Mock(return_value=True)

    def full(self, *runs):
        """n번째 전체 실행은 runs[n-1](셸 조각)을 돈다. 넘으면 마지막 것. 횟수는 full.count에 남는다."""
        cases = "".join(f"  {i}) {body};;\n" for i, body in enumerate(runs, 1))
        (self.dir / "full.sh").write_text('n=$(( $(cat full.count 2>/dev/null || echo 0) + 1 )); echo $n > full.count\n'
                                          f'case $n in\n{cases}  *) {runs[-1]};;\nesac\n')
        return "bash full.sh"

    def triage(self, rerun="echo {file} >> rerun.calls; test ! -f rerun.fail", failed_file=FAILED_FILE, max_files=3):
        return config.VerifyConfig(failed_file, rerun, max_files)

    def run_verify(self, command, triage=None, retries=0, header=""):
        spec = SimpleNamespace(verify=command, verify_minutes=1, verify_retries=retries)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": ""}), self.log.open("w", encoding="utf-8") as f:
            f.write(header)
            res = verify.run(spec, self.dir, f, triage, self.unchanged)
            verify.flaky(res, "point", f)
        return res, self.log.read_text(encoding="utf-8")

    def count(self):
        path = self.dir / "full.count"
        return int(path.read_text()) if path.exists() else 0

    def calls(self):
        path = self.dir / "rerun.calls"
        return path.read_text().split() if path.exists() else []


class TriageTest(Case):
    def test_off_is_the_old_behaviour(self):
        for triage in (None, config.VerifyConfig(), config.VerifyConfig(max_files=1)):
            with self.subTest(triage=triage):
                (self.dir / "full.count").unlink(missing_ok=True)
                res, log = self.run_verify(self.full(fail("test_a"), "exit 0"), triage)
                self.assertEqual((res.ok, res.code, res.retries, res.triaged, self.count()), (False, 1, 0, (), 1))
                self.assertEqual(log, "FAIL: test_x (test_a.Case.test_x)\n\n종료 코드: 1\n")
                self.assertEqual(res.samples, ({"seconds": res.samples[0]["seconds"], "code": 1, "timed_out": False, "ok": False},))
                self.assertEqual(self.calls(), [])
                self.unchanged.assert_not_called()

    def test_triage_passes_and_full_passes_again(self):
        res, log = self.run_verify(self.full(fail("test_a", "test_b", "test_a"), "exit 0"), self.triage())
        self.assertEqual((res.ok, res.retries, res.triaged, self.count()), (True, 0, ("test_a", "test_b"), 2))
        self.assertEqual(self.calls(), ["test_a", "test_b"])
        self.assertIn("\n판별 test_a: $ echo test_a >> rerun.calls; test ! -f rerun.fail\n", log)
        self.assertIn("\n판별 통과: test_a test_b. 전체 검증을 한 번 더 돌린다\n", log)
        self.assertTrue(log.endswith("\n종료 코드: 0\n\nflaky: point test_a test_b 따로 돌려 통과, 전체 다시 통과\n"), log)
        self.assertEqual(self.unchanged.call_count, 2)  # 판별 전, 전체 재실행 전
        first, again = res.samples
        self.assertEqual((first["ok"], first["triage"], first["triage_files"], first["triage_reason"]),
                         (False, "passed", ["test_a", "test_b"], ""))
        self.assertNotIn("after_triage", first)
        self.assertEqual((again["ok"], again["after_triage"]), (True, True))
        self.assertNotIn("triage", again)

    def test_triage_passes_but_full_fails_again(self):
        res, log = self.run_verify(self.full(fail("test_a"), "echo still; exit 2"), self.triage())
        self.assertEqual((res.ok, res.code, res.triaged, self.count()), (False, 2, ("test_a",), 2))
        self.assertEqual(self.calls(), ["test_a"])
        self.assertNotIn("flaky", log)
        self.assertTrue(log.endswith("still\n\n종료 코드: 2\n"), log)

    def test_triage_failure_does_not_run_the_full_command_again(self):
        (self.dir / "rerun.fail").touch()
        res, log = self.run_verify(self.full(fail("test_a", "test_b"), "exit 0"), self.triage())
        self.assertEqual((res.ok, res.triaged, self.count()), (False, (), 1))
        self.assertEqual(self.calls(), ["test_a"])  # 첫 실패에서 멈춘다
        self.assertIn("\n판별 종료 코드: 1\n\n판별 실패: test_a. 전체 검증은 다시 돌리지 않는다\n", log)
        self.assertEqual(self.unchanged.call_count, 1)
        self.assertEqual((res.samples[0]["triage"], res.samples[0]["triage_reason"]), ("failed", "test_a"))
        self.assertEqual(len(res.samples), 1)

    def test_deterministic_triage_failure_skips_remaining_retries(self):
        res, log = self.run_verify(self.full(fail("test_a", "test_b"), "exit 0"),
                                   self.triage(rerun="echo {file} >> rerun.calls; exit 7"), retries=1)
        self.assertEqual(self.count(), 1)
        self.assertEqual((res.ok, res.code, res.retries, res.triaged), (False, 1, 0, ()))
        self.assertEqual(self.calls(), ["test_a"])
        self.assertIn("\n판별 실패: test_a. 전체 검증은 다시 돌리지 않는다\n", log)
        self.assertNotIn("검증 재시도 1", log)
        self.assertNotIn("flaky:", log)
        self.assertEqual(len(res.samples), 1)
        self.assertEqual((res.samples[0]["triage"], res.samples[0]["triage_files"], res.samples[0]["triage_reason"]),
                         ("failed", ["test_a", "test_b"], "test_a"))

    def test_deterministic_failure_on_a_retry_keeps_the_retry_count(self):
        res, log = self.run_verify(self.full("exit 1", fail("test_a"), "exit 0"),
                                   self.triage(rerun="exit 7 # {file}"), retries=2)
        self.assertEqual((res.ok, res.code, res.retries, self.count()), (False, 1, 1, 2))
        self.assertEqual([s["triage"] for s in res.samples], ["skipped", "failed"])
        self.assertIn("검증 재시도 1", log)
        self.assertNotIn("검증 재시도 2", log)

    def test_skipped_triage_keeps_retries(self):
        cases = (
            ("no_match", "echo boom; exit 1", self.triage()),
            ("too_many", fail("test_a", "test_b"), self.triage(max_files=1)),
            ("bad_value", "echo 'FAIL: a/b'; exit 1", self.triage(failed_file=r"^FAIL: (.*)$")),
            ("no_check", fail("test_a"), self.triage()),
        )
        for reason, output, triage in cases:
            with self.subTest(reason=reason):
                (self.dir / "full.count").unlink(missing_ok=True)
                self.unchanged = None if reason == "no_check" else mock.Mock(return_value=True)
                res, log = self.run_verify(self.full(output), triage, retries=1)
                self.assertEqual((res.ok, res.retries, self.count(), self.calls()), (False, 1, 2, []))
                self.assertEqual([(s["triage"], s["triage_reason"]) for s in res.samples],
                                 [("skipped", reason), ("skipped", reason)])
                self.assertEqual(log.count("검증 재시도 1"), 1)

    def test_timeout_and_interrupted_full_runs_keep_retries(self):
        for result, reason in ((verify.Result(-15, True, "1"), "timeout"),
                               (verify.Result(1, False, "1", interrupted=True), "interrupted")):
            with self.subTest(reason=reason):
                with mock.patch.object(verify, "_run_once", return_value=result) as full:
                    res, log = self.run_verify("unused", self.triage(), retries=1)
                self.assertEqual((res.ok, res.retries, full.call_count, self.calls()), (False, 1, 2, []))
                self.assertEqual([(s["triage"], s["triage_reason"]) for s in res.samples],
                                 [("skipped", reason), ("skipped", reason)])
                self.assertEqual(log.count("검증 재시도 1"), 1)

    def test_timeout_and_interrupted_triage_runs_keep_retries(self):
        real = verify._launch
        for result in (verify.Result(-15, True, "1"), verify.Result(0, True, "1"),
                       verify.Result(1, False, "1", interrupted=True)):
            with self.subTest(result=result):
                (self.dir / "full.count").unlink(missing_ok=True)

                def launch(command, seconds, cwd, stream):
                    if command == "bash full.sh":
                        return real(command, seconds, cwd, stream)
                    return result

                with mock.patch.object(verify, "_launch", side_effect=launch):
                    res, log = self.run_verify(self.full(fail("test_a")), self.triage(), retries=1)
                self.assertEqual((res.ok, res.retries, self.count()), (False, 1, 2))
                self.assertEqual([(s["triage"], s["triage_reason"]) for s in res.samples],
                                 [("failed", "test_a"), ("failed", "test_a")])
                self.assertEqual(log.count("검증 재시도 1"), 1)

    def test_exhausted_triage_budget_keeps_retries(self):
        with mock.patch.object(verify, "_clock", side_effect=[0, 60, 100, 160]):
            res, log = self.run_verify(self.full(fail("test_a")), self.triage(), retries=1)
        self.assertEqual((res.ok, res.retries, self.count(), self.calls()), (False, 1, 2, []))
        self.assertEqual([(s["triage"], s["triage_reason"]) for s in res.samples],
                         [("failed", "test_a"), ("failed", "test_a")])
        self.assertEqual(log.count("판별 시간(1분)을 다 써서 돌리지 않았다"), 2)
        self.assertEqual(log.count("검증 재시도 1"), 1)

    def assert_skipped(self, output, reason, triage=None, files=()):
        (self.dir / "full.count").unlink(missing_ok=True)
        res, log = self.run_verify(self.full(output, "exit 0"), triage or self.triage())
        self.assertEqual((res.ok, self.count(), self.calls()), (False, 1, []), log)
        self.assertIn("\n판별 안 함: ", log)
        self.assertEqual((res.samples[0]["triage"], res.samples[0]["triage_reason"], res.samples[0]["triage_files"]),
                         ("skipped", reason, list(files)))
        return log

    def test_no_match_too_many_and_unsafe_values_are_not_triaged(self):
        self.assert_skipped("echo boom; exit 1", "no_match")
        self.assert_skipped(fail("test_a", "test_b", "test_c", "test_d"), "too_many",
                            files=("test_a", "test_b", "test_c", "test_d"))
        self.assert_skipped(fail("test_a", "test_b"), "too_many", self.triage(max_files=1), ("test_a", "test_b"))
        loose = r"^FAIL: (.*)$"  # 무엇이든 뽑는 정규식이라도 값이 SAFE_FILE이 아니면 명령에 넣지 않는다
        for value in ("$(touch pwned)", "a'b", 'a"b', "a b", "`touch pwned`", "a;b"):
            with self.subTest(value=value):
                self.assert_skipped(f"printf 'FAIL: %s\\n' {value!r}; exit 1", "bad_value",
                                    self.triage(failed_file=loose), (value,))
                self.assertFalse((self.dir / "pwned").exists())
        self.assert_skipped("echo 'FAIL: ok'; echo 'FAIL: x;y'; exit 1", "bad_value",
                            self.triage(failed_file=loose), ("ok", "x;y"))
        self.assert_skipped("echo 'FAIL: '; exit 1", "bad_value", self.triage(failed_file=loose), ("",))
        self.unchanged.assert_not_called()

    def test_timeout_and_interrupted_full_runs_are_not_triaged(self):
        output = "FAIL: test_x (test_a.Case.test_x)\n"
        for first, reason in ((verify.Result(-15, True, "1"), "timeout"),
                              (verify.Result(1, False, "1", interrupted=True), "interrupted")):
            with self.subTest(reason=reason):
                def once(spec, cwd, stream):
                    stream.write(output)
                    return first
                with mock.patch.object(verify, "_run_once", side_effect=once) as full:
                    res, log = self.run_verify("unused", self.triage())
                self.assertEqual((res.ok, full.call_count, self.calls()), (False, 1, []))
                self.assertEqual((res.samples[0]["triage"], res.samples[0]["triage_reason"]), ("skipped", reason))
                self.assertIn("판별 안 함: ", log)
        self.unchanged.assert_not_called()

    def test_triage_run_that_times_out_fails_even_with_exit_zero(self):
        real = verify._launch

        def launch(command, seconds, cwd, stream):
            if command.startswith("bash full.sh"):
                return real(command, seconds, cwd, stream)
            return verify.Result(0, True, "1")
        with mock.patch.object(verify, "_launch", side_effect=launch):
            res, log = self.run_verify(self.full(fail("test_a"), "exit 0"), self.triage())
        self.assertEqual((res.ok, self.count()), (False, 1))
        self.assertIn("\n판별 종료 코드: 0\n\n판별 실패: test_a 시간 초과. 전체 검증은 다시 돌리지 않는다\n", log)
        self.assertEqual(res.samples[0]["triage"], "failed")

    def test_triage_runs_share_one_time_budget(self):
        real = verify._launch
        seen = []
        now = [1000.0]

        def launch(command, seconds, cwd, stream):
            if command.startswith("bash full.sh"):
                return real(command, seconds, cwd, stream)
            seen.append((command.split()[1], seconds))
            now[0] += 45  # 판별 하나가 45초 걸린 것으로 친다
            return verify.Result(0, False, "1")
        with mock.patch.object(verify, "_launch", side_effect=launch), \
                mock.patch.object(verify, "_clock", side_effect=lambda: now[0]):
            res, log = self.run_verify(self.full(fail("test_a", "test_b", "test_c"), "exit 0"), self.triage())
        self.assertEqual(seen, [("test_a", 60), ("test_b", 15)])  # verify_minutes 1 = 60초를 나눠 쓴다
        self.assertIn("판별 시간(1분)을 다 써서 돌리지 않았다", log)
        self.assertEqual((res.ok, self.count(), res.samples[0]["triage_reason"]), (False, 1, "test_c"))

    def test_earlier_attempt_and_header_matches_do_not_count(self):
        header = "$ " + fail("test_head") + "\nFAIL: test_x (test_head.Case.test_x)\n"
        # 끊긴 판별은 재시도하므로 앞 시도·머리말의 매치를 다음 판별에서 빼는지 본다.
        triage = self.triage(rerun="echo {file} >> rerun.calls; exit 130")
        res, log = self.run_verify(self.full(fail("test_a"), fail("test_b"), "exit 0"), triage, retries=1, header=header)
        self.assertEqual((res.ok, res.retries, self.count()), (False, 1, 2))
        self.assertEqual(self.calls(), ["test_a", "test_b"])
        self.assertEqual([s["triage_files"] for s in res.samples], [["test_a"], ["test_b"]])

    def test_retries_triage_every_attempt_and_run_full_again_once_each(self):
        res, log = self.run_verify(self.full(fail("test_a")), self.triage(), retries=1)
        self.assertEqual((res.ok, res.retries, res.triaged, self.count()), (False, 1, ("test_a",), 4))
        self.assertEqual(self.calls(), ["test_a", "test_a"])
        self.assertEqual([(s.get("triage"), s.get("after_triage", False)) for s in res.samples],
                         [("passed", False), (None, True), ("passed", False), (None, True)])
        self.assertEqual(log.count("검증 재시도 1"), 1)

    def test_pass_on_a_retry_after_triage_writes_the_triage_line_only(self):
        res, log = self.run_verify(self.full("exit 1", fail("test_b"), "exit 0"), self.triage(), retries=1)
        self.assertEqual((res.ok, res.retries, res.triaged, self.count()), (True, 1, ("test_b",), 3))
        self.assertIn("\nflaky: point test_b 따로 돌려 통과, 전체 다시 통과\n", log)
        self.assertNotIn("재시도 1번 만에 통과", log)

    def test_changed_tree_stops_triage_and_the_full_run_again(self):
        self.unchanged.return_value = False
        res, log = self.run_verify(self.full(fail("test_a"), "exit 0"), self.triage())
        self.assertEqual((res.ok, self.count(), self.calls()), (False, 1, []))
        self.assertIn("\n판별 안 함: 검증 중 트리가 바뀌었다\n", log)
        self.assertEqual(res.samples[0]["triage_reason"], "tree_changed")

        (self.dir / "full.count").unlink()
        self.unchanged = mock.Mock(side_effect=[True, False])  # 판별 실행이 트리를 바꿨다
        res, log = self.run_verify(self.full(fail("test_a"), "exit 0"), self.triage())
        self.assertEqual((res.ok, res.triaged, self.count(), self.calls()), (False, (), 1, ["test_a"]))
        self.assertIn("\n판별 통과, 전체 검증은 다시 돌리지 않는다: 판별 중 트리가 바뀌었다\n", log)
        self.assertEqual((res.samples[0]["triage"], res.samples[0]["triage_reason"]), ("passed", "tree_changed"))

    def test_changed_tree_stops_the_retries_too(self):
        """판별이나 앞 실행이 바꾼 트리를 다음 재시도가 되돌려 통과하지 않게, 재시도 전에도 트리를 보고 바뀌었으면 더 돌리지 않는다."""
        cases = (  # (이름, 판별 명령 실패, 확인 함수가 돌려줄 값들, 전체 실행들, 전체 실행 수, 판별 값들)
            ("판별 전에 바뀜", False, [False, False], (fail("test_a"), "exit 0"), 1, []),
            ("판별 통과 뒤 바뀜", False, [True, False, False], (fail("test_a"), "exit 0"), 1, ["test_a"]),
            ("판별 실패 뒤 바뀜", True, [True, False], (fail("test_a"), "exit 0"), 1, ["test_a"]),
            ("판별 안 한 실행 뒤 바뀜", False, [False], ("echo boom; exit 1", "exit 0"), 1, []),
            ("전체 재실행 뒤 바뀜", False, [True, True, False], (fail("test_a"), "exit 2", "exit 0"), 2, ["test_a"]),
        )
        for name, rerun_fails, checks, runs, count, calls in cases:
            with self.subTest(name):
                for leftover in ("full.count", "rerun.calls", "rerun.fail"):
                    (self.dir / leftover).unlink(missing_ok=True)
                if rerun_fails:
                    (self.dir / "rerun.fail").touch()
                self.unchanged = mock.Mock(side_effect=checks)
                res, log = self.run_verify(self.full(*runs), self.triage(), retries=1)
                self.assertEqual((res.ok, res.retries, self.count(), self.calls()), (False, 0, count, calls), log)
                self.assertIn("\n검증 재시도 안 함: 검증 중 트리가 바뀌었다\n", log)
                self.assertNotIn("검증 재시도 1", log)
                self.assertEqual(self.unchanged.call_count, len(checks))

        with self.subTest("꺼짐"):  # 판별이 꺼져 있으면 지금처럼 확인 함수를 부르지 않고 재시도한다
            (self.dir / "full.count").unlink()
            self.unchanged = mock.Mock(return_value=False)
            res, log = self.run_verify(self.full("exit 1", "exit 0"), None, retries=1)
            self.assertEqual((res.ok, res.retries, self.count()), (True, 1, 2))
            self.unchanged.assert_not_called()

    def test_without_a_tree_check_there_is_no_triage(self):
        self.unchanged = None
        res, log = self.run_verify(self.full(fail("test_a"), "exit 0"), self.triage())
        self.assertEqual((res.ok, self.count(), self.calls()), (False, 1, []))
        self.assertEqual(res.samples[0]["triage_reason"], "no_check")

    def test_full_run_again_reaches_commands_after_the_failed_link_of_the_chain(self):
        command = self.full(fail("test_a"), "exit 0") + " && touch tail.ran"
        res, log = self.run_verify(command, self.triage())
        self.assertEqual((res.ok, self.count(), self.calls()), (True, 2, ["test_a"]))
        self.assertTrue((self.dir / "tail.ran").exists())  # 판별(test_a만)이 아니라 전체 사슬이 통과를 정했다

    def test_triage_keys_reach_validation_rows(self):
        res, _ = self.run_verify(self.full(fail("test_a"), "exit 0"), self.triage())
        r = SimpleNamespace(st=SimpleNamespace(metrics={}), save=lambda: None)
        metrics.validation(r, "ticket-01", "cmd", "head", res)
        rows = r.st.metrics["validations"]
        self.assertEqual([(x["retry"], x["result"], x.get("triage"), x.get("triage_files"), x.get("after_triage"))
                          for x in rows], [(1, "failed", "passed", ["test_a"], None), (2, "passed", None, None, True)])

    def test_this_repo_regex_takes_the_module_and_skips_import_errors(self):
        cfg, problems = config.load(REPO)
        self.assertEqual(problems, [])
        self.assertEqual(cfg.verify, config.VerifyConfig(FAILED_FILE, ".venv/bin/python -m unittest discover -s tests -p {file}.py", 3))
        output = ("FAIL: test_x (test_resume_report.ProtectedResumeTest.test_x)\n"
                  "ERROR: test_x (unittest.loader._FailedTest.test_x)\n"
                  "ERROR: test_y (test_verify.StaleTest.test_y)\n")
        self.assertEqual(verify.failed_files(cfg.verify.failed_file, output), ("test_resume_report", "test_verify"))
        self.assertEqual(verify.failed_files(cfg.verify.failed_file, "ERROR: test_x (unittest.loader._FailedTest.test_x)\n"), ())


class PointsTest(unittest.TestCase):
    """모든 검증 지점(go._verify, finish._verify)이 실행 중인 config `[verify]`와 트리 확인 함수를 넘긴다.

    `[verify]`는 main checkout의 config에만 적고 커밋하지 않는다: 검증하는 worktree의 config에는 없다."""
    BASE, REMOTE = "main", "origin"
    G, V = support.GoTest, test_verify_modes.VerifyModesTest
    setUp, tearDown, go, calls, rundir, final_report, lines = G.setUp, G.tearDown, G.go, G.calls, G.rundir, G.final_report, G.lines
    configure, change_code_with_report = V.configure, V.change_code_with_report

    def test_every_point_triages_with_the_running_config(self):
        script = self.bin / "verify.sh"
        script.write_text(f'''\
here={self.bin}
if [ "${{PWD##*/}}" = base ]; then point=main
elif git rev-parse -q --verify MERGE_HEAD >/dev/null; then point=ticket-01
elif [ -f extra ]; then point=integration-final
else point=integration; fi
echo "$point" >> "$here/verifies"
if [ ! -f "$here/passed-$point" ]; then touch "$here/passed-$point"; echo "FAIL: test_x (test_flaky.Case.test_x)"; exit 1; fi
''')
        self.configure(verify=f"bash {script}")
        with (self.repo / config.CONFIG_PATH).open("a") as f:
            f.write(f"\n[verify]\nfailed_file = '{FAILED_FILE}'\nrerun = \"echo {{file}} >> {self.bin}/rerun.calls\"\n")
        with self.change_code_with_report():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        points = ("ticket-01", "integration", "integration-final", "main")
        self.assertEqual(self.lines("verifies"), [p for p in points for _ in range(2)])
        self.assertEqual(self.lines("rerun.calls"), ["test_flaky"] * 4)
        logs = {"ticket-01": self.rundir / "01/1/verify.log",
                **{p: self.rundir / "finish" / f"{p}-verify.log" for p in points[1:]}}
        for point, log in logs.items():
            self.assertIn(f"\nflaky: {point} test_flaky 따로 돌려 통과, 전체 다시 통과\n", log.read_text())
        rows = state.load(self.rundir, "demo").metrics["validations"]
        self.assertEqual([(x["label"], x.get("triage"), x.get("after_triage", False)) for x in rows],
                         [(p, t, a) for p in points for t, a in (("passed", False), (None, True))])
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")


class ReplayPointTest(unittest.TestCase):
    """replay._verify도 실행 중인 config `[verify]`와 트리 확인 함수(_at_head)를 넘기고, 판별로 통과하면 flaky 줄을 쓴다.

    트리는 커밋 하나짜리 임시 레포다. 전체 명령·횟수·판별 기록은 트리 밖에 두어 트리를 더럽히지 않는다."""

    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.tree = self.dir / "tree"
        self.tree.mkdir()
        (self.tree / "tracked").write_text("original\n")
        for args in (["init", "-q"], ["add", "tracked"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qm", "init"]):
            subprocess.run(["git", *args], cwd=self.tree, check=True, capture_output=True)
        self.head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.tree, check=True, capture_output=True, text=True).stdout.strip()

    def replay(self, full, rerun, retries=0):
        """full은 전체 명령의 셸 조각(실행마다 full.runs에 한 줄), rerun은 판별 명령 틀. (replay 결과, 로그, 전체 실행 수, 판별 값들).
        앞 호출이 남긴 기록과 트리 변경은 지우고 시작한다."""
        for leftover in ("full.runs", "rerun.calls", "logs/verify.log"):
            (self.dir / leftover).unlink(missing_ok=True)
        subprocess.run(["git", "checkout", "-q", "--", "tracked"], cwd=self.tree, check=True)
        (self.dir / "full.sh").write_text(f"echo run >> {self.dir}/full.runs\n{full}\n")
        spec = SimpleNamespace(verify=f"bash {self.dir}/full.sh", verify_minutes=1, verify_retries=retries)
        cfg = SimpleNamespace(worktree=SimpleNamespace(setup=""), verify=config.VerifyConfig(FAILED_FILE, f"echo {{file}} >> {self.dir}/rerun.calls; {rerun}", 3))
        logdir = self.dir / "logs"
        logdir.mkdir(exist_ok=True)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": ""}):
            result = replay._verify(cfg, spec, self.tree, self.head, logdir, io.StringIO())
        runs, calls = (self.dir / "full.runs", self.dir / "rerun.calls")
        return (result, (logdir / "verify.log").read_text(), len(runs.read_text().splitlines()),
                calls.read_text().split() if calls.exists() else [])

    def test_triage_with_the_running_config_and_flaky_line(self):
        full = f'[ -f {self.dir}/passed ] && exit 0; touch {self.dir}/passed; echo "FAIL: test_x (test_flaky.Case.test_x)"; exit 1'
        result, log, runs, calls = self.replay(full, "true")
        self.assertEqual((result, runs, calls), ("통과", 2, ["test_flaky"]), log)
        self.assertIn("\nflaky: replay test_flaky 따로 돌려 통과, 전체 다시 통과\n", log)

    def test_tree_changed_by_triage_is_not_reverted_by_a_retry(self):
        """판별 명령이 tracked를 바꾸면 재시도의 전체 명령이 되돌리고 통과하더라도 받아들이면 안 된다. 판별이 통과하든 실패하든 같다."""
        full = 'if [ "$(cat tracked)" = original ]; then echo "FAIL: test_x (test_flaky.Case.test_x)"; exit 1; fi; echo original > tracked'
        for name, rerun in (("판별 통과", "echo changed > tracked"), ("판별 실패", "echo changed > tracked; exit 1")):
            with self.subTest(name):
                result, log, runs, calls = self.replay(full, rerun, retries=1)
                self.assertEqual((result, runs, calls), ("실패(트리 바뀜)", 1, ["test_flaky"]), log)
                self.assertIn("\n검증 재시도 안 함: 검증 중 트리가 바뀌었다\n", log)
                self.assertEqual((self.tree / "tracked").read_text(), "changed\n")


BAD = {
    'failed_file = "(test_\\\\w+)"': "`verify.failed_file`",  # rerun 없음
    'rerun = "run {file}"': "`verify.failed_file`",  # failed_file 없음
    'failed_file = "(test_"\nrerun = "run {file}"': "`verify.failed_file` 정규식",
    'failed_file = "test_\\\\w+"\nrerun = "run {file}"': "`verify.failed_file`에 그룹이 없다",
    'failed_file = "(test_\\\\w+)"\nrerun = "run file"': "`verify.rerun`에 `{file}`",
    'failed_file = "(test_\\\\w+)"\nrerun = "run {file}"\nmax_files = 0': "`verify.max_files`는 1 이상",
}


class ConfigTest(unittest.TestCase):
    T = test_config.ConfigTest
    setUp, cli = T.setUp, T.cli

    def test_section_is_off_by_default_and_not_in_init_template(self):
        cfg, problems = config.load(self.repo)
        self.assertEqual((problems, cfg.verify, cfg.verify.enabled), ([], config.VerifyConfig(), False))
        self.assertEqual(cfg.verify.max_files, 3)
        self.assertNotIn("[verify]", config.DEFAULT_CONFIG)
        self.path.write_text(test_config.CONFIG + '[verify]\nfailed_file = "^F (t\\\\w+)"\nrerun = "r {file}.py"\n')
        cfg, problems = config.load(self.repo)
        self.assertEqual((problems, cfg.verify), ([], config.VerifyConfig(r"^F (t\w+)", "r {file}.py", 3)))
        self.assertTrue(cfg.verify.enabled)
        self.path.write_text(test_config.CONFIG + '[verify]\nfailed_file = "^F (t\\\\w+)"\nrerun = "r {file}.py"\nmax_files = 1\n')
        self.assertEqual(config.load(self.repo)[0].verify.max_files, 1)

    def test_five_config_errors(self):
        for body, message in BAD.items():
            with self.subTest(body=body):
                self.path.write_text(test_config.CONFIG + "[verify]\n" + body + "\n")
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertEqual([p.level for p in problems], ["오류"], problems)
                self.assertIn(message, problems[0].message)

    def test_wrong_types_are_errors_and_unknown_keys_warnings(self):
        both = 'failed_file = "(test_\\\\w+)"\nrerun = "run {file}"\n'
        cases = {
            "verify = 1\n" + test_config.CONFIG: "`verify`는 테이블이어야 한다",
            test_config.CONFIG + '[verify]\nfailed_file = 1\nrerun = "run {file}"\n': "`verify.failed_file`는 문자열이어야 한다",
            test_config.CONFIG + '[verify]\nfailed_file = "(test_\\\\w+)"\nrerun = ["run {file}"]\n': "`verify.rerun`는 문자열이어야 한다",
            **{test_config.CONFIG + "[verify]\n" + both + f"max_files = {value}\n": "`verify.max_files`는 정수이어야 한다"
               for value in ('"3"', "true", "1.5")},
        }
        for text, message in cases.items():
            with self.subTest(text=text.replace(test_config.CONFIG, "")):
                self.path.write_text(text)
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertEqual([p.level for p in problems], ["오류"], problems)
                self.assertIn(message, problems[0].message)
        self.path.write_text(test_config.CONFIG + "[verify]\n" + both + "extra = 1\n")
        cfg, problems = config.load(self.repo)
        self.assertEqual([(p.level, p.message) for p in problems], [("경고", "알 수 없는 키 `verify.extra`")])
        self.assertEqual(cfg.verify, config.VerifyConfig(r"(test_\w+)", "run {file}", 3))

    @mock.patch("gs.check.shutil.which", return_value="/test/cli")
    def test_check_and_go_stop_on_each_error(self, _which):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        root = self.repo / ".goldstack/work/demo"
        (root / "tickets").mkdir(parents=True)
        (root / "spec.md").write_text('---\nfeature: demo\nverify: "true"\n---\n')
        (root / "tickets/01-a.md").write_text(
            '---\nid: "01"\ntitle: a\nblocked_by: []\nmodel: claude\nreviewer: codex\ntouches: ["a.py"]\n---\n')
        for body, message in BAD.items():
            for cmd in ("check", "go"):
                with self.subTest(body=body, cmd=cmd):
                    self.path.write_text(test_config.CONFIG + "[verify]\n" + body + "\n")
                    code, out, err = self.cli(cmd, "demo")
                    self.assertEqual(code, 1, out + err)
                    self.assertIn(message, err)
        self.assertFalse((root / "run").exists())


if __name__ == "__main__":
    unittest.main()
