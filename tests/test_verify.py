"""verify 시간 제한(verify.py): 새 프로세스 그룹, SIGTERM → SIGKILL, 자손까지 끝낸다. 로그 끝의 종료 코드 줄과 끊김 판정.

끊김 시험은 실제 프로세스에 신호를 보낸다. xargs 문구는 이 맥의 실측 값이다: `printf 'a\\nb\\n' | xargs -P 2 -n 1 sh -c 'kill -TERM $$'`는
종료 코드 1로 끝나고 `xargs: sh: terminated with signal 15; aborting`을 남긴다(macOS 27.0.1, -KILL이면 signal 9). 리눅스 xargs는 재지 않아 그 시험은 이 맥에서만 돈다.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import verify


def alive(pid):
    """좀비는 죽은 것으로 본다."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def wait_dead(pid, seconds=30.0):
    """부모(bash)가 죽은 뒤 고아는 init이 거둔다. 잠깐 기다려 본다."""
    deadline = time.monotonic() + seconds
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not alive(pid)


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pids = []

    def tearDown(self):
        for pid in self.pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.tmp.cleanup()

    def run_verify(self, command, minutes=20, env=None):
        spec = SimpleNamespace(verify=command, verify_minutes=minutes)
        log = self.dir / "verify.log"
        with mock.patch.dict(os.environ, env or {}), log.open("w", encoding="utf-8") as f:
            start = time.monotonic()
            res = verify.run(spec, self.dir, f)
        return res, log.read_text(encoding="utf-8", errors="replace"), time.monotonic() - start

    def pid(self, name):
        pid = int((self.dir / name).read_text().strip())
        self.pids.append(pid)
        return pid


class VerifyTest(Case):
    def test_limit_from_env_or_spec(self):
        spec = SimpleNamespace(verify_minutes=3)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "2"}):
            self.assertEqual(verify.limit_seconds(spec), 2)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": ""}):
            self.assertEqual(verify.limit_seconds(spec), 180)
        self.assertEqual((verify.minutes(180), verify.minutes(1), verify.minutes(90)), ("3", "0.02", "1.5"))

    def test_in_time_keeps_output_and_code(self):
        res, log, _ = self.run_verify("echo hi; exit 3")
        self.assertEqual((res.code, res.timed_out, res.ok), (3, False, False))
        self.assertEqual(log, "hi\n\n종료 코드: 3\n")
        res, log, _ = self.run_verify("echo ok")
        self.assertTrue(res.ok)
        self.assertNotIn("시간 초과", log)
        self.assertEqual(log, "ok\n\n종료 코드: 0\n")

    def test_launch_failure_also_ends_with_the_exit_code(self):
        spec = SimpleNamespace(verify="true", verify_minutes=1)
        log = self.dir / "verify.log"
        with log.open("w", encoding="utf-8") as f:
            res = verify.run(spec, self.dir / "no-such-directory", f)
        self.assertEqual((res.code, res.ok, res.interrupted), (1, False, False))
        self.assertIn("검증 명령 실행 실패", log.read_text())
        self.assertTrue(log.read_text().endswith("\n종료 코드: 1\n"), log.read_text())

    def test_timeout_kills_background_children(self):
        with support.times_out_once_ready(self.dir / "ready"), mock.patch.object(verify, "GRACE", 60), \
                mock.patch.object(verify.os, "killpg", wraps=os.killpg) as killpg:  # 부하로 SIGTERM이 늦어도 SIGKILL로 넘어가지 않게
            res, log, _ = self.run_verify(f"sleep 300 & echo $! > {self.dir / 'bg'}; echo $$ > {self.dir / 'sh'}; "
                                          f"echo started; touch {self.dir / 'ready'}; sleep 300", env={"GS_VERIFY_TIMEOUT": "1"})
        self.assertTrue(res.timed_out)
        self.assertFalse(res.ok)
        self.assertFalse(res.interrupted)
        self.assertNotIn(signal.SIGKILL, [call.args[1] for call in killpg.call_args_list])  # SIGTERM으로 끝나 SIGKILL까지 가지 않았다
        self.assertTrue(wait_dead(self.pid("bg")), "백그라운드 자식이 살아 있다")
        self.assertTrue(wait_dead(self.pid("sh")))
        self.assertIn("started\n", log)
        self.assertEqual(res.code, -signal.SIGTERM)
        self.assertTrue(log.endswith("\n시간 초과: 0.02분\n\n종료 코드: -15\n"), log)

    def test_timeout_sigkills_group_ignoring_sigterm(self):
        with support.times_out_once_ready(self.dir / "ready"), mock.patch.object(verify, "GRACE", 0.3), \
                mock.patch.object(verify.os, "killpg", wraps=os.killpg) as killpg:
            res, log, _ = self.run_verify(f"trap '' TERM; sleep 300 & echo $! > {self.dir / 'bg'}; touch {self.dir / 'ready'}; sleep 300",
                                          env={"GS_VERIFY_TIMEOUT": "0.5"})
        self.assertTrue(res.timed_out)
        signals = [call.args[1] for call in killpg.call_args_list]
        self.assertIn(signal.SIGKILL, signals)  # SIGTERM을 무시해 SIGKILL까지 갔다
        self.assertLess(signals.index(signal.SIGTERM), signals.index(signal.SIGKILL))
        self.assertTrue(wait_dead(self.pid("bg")), "SIGTERM을 무시한 자식이 살아 있다")
        self.assertEqual(res.code, -signal.SIGKILL)
        self.assertTrue(log.endswith("\n시간 초과: 0.01분\n\n종료 코드: -9\n"), log)
        self.assertFalse(res.interrupted)


# 자식이 신호로 죽고 bash는 이어서 그 종료 코드로 끝난다. `;` 뒤에 명령이 있어 bash가 자식을 exec로 대신하지 않는다
CHILD_TERM = "sh -c 'kill -TERM $$'; exit $?"
CHILD_KILL = "sh -c 'kill -KILL $$'; exit $?"
XARGS_LINE = "xargs: sleep: terminated with signal 15; aborting"  # 이 맥의 실측(spec §6). 맨 위 docstring


class InterruptedTest(Case):
    def assert_interrupted(self, command, code):
        res, log, _ = self.run_verify(command)
        self.assertEqual((res.code, res.interrupted, res.timed_out, res.ok), (code, True, False, False), log)
        self.assertTrue(log.endswith(f"\n종료 코드: {code}\n"), log)
        return log

    def assert_not_interrupted(self, command, code):
        res, log, _ = self.run_verify(command)
        self.assertEqual((res.code, res.interrupted), (code, False), log)
        self.assertTrue(log.endswith(f"\n종료 코드: {code}\n"), log)

    def test_bash_killed_by_a_signal_has_a_negative_code(self):
        self.assert_interrupted("kill -TERM $$", -15)
        self.assert_interrupted("kill -KILL $$", -9)

    def test_child_killed_by_a_signal_has_a_code_above_128(self):
        self.assert_interrupted(CHILD_TERM, 143)
        self.assert_interrupted(CHILD_KILL, 137)

    def test_code_boundary_is_128(self):
        self.assert_not_interrupted("exit 1", 1)
        self.assert_not_interrupted("exit 128", 128)
        self.assert_interrupted("exit 129", 129)

    def test_xargs_line_with_code_1(self):
        log = self.assert_interrupted(f"{CHILD_TERM.split(';')[0]}; echo '{XARGS_LINE}' >&2; exit 1", 1)
        self.assertIn(XARGS_LINE, log)

    def test_killed_by_signal_line_with_code_1(self):
        self.assert_interrupted(f"{CHILD_KILL.split(';')[0]}; echo 'killed by signal 9'; exit 1", 1)

    def test_real_xargs_of_this_mac(self):
        if sys.platform != "darwin":
            self.skipTest("xargs 문구는 macOS에서만 쟀다. 리눅스 xargs는 재지 않았다")
        for sig, number in (("TERM", 15), ("KILL", 9)):
            log = self.assert_interrupted(f"printf 'a\\nb\\n' | xargs -P 2 -n 1 sh -c 'kill -{sig} $$'", 1)
            self.assertIn(f"xargs: sh: terminated with signal {number}; aborting\n", log)

    def test_children_are_ended_when_xargs_itself_is_killed(self):
        # 자식 하나가 xargs를 죽인다. xargs가 없으니 다른 자식을 기다리지 않고 남겨 둔다
        job = self.dir / "job.sh"
        job.write_text(f'if [ "$1" = a ]; then echo $$ > "{self.dir}/sibling"; touch "{self.dir}/ready"; exec sleep 300; fi\n'
                       f'until [ -f "{self.dir}/ready" ]; do sleep 0.01; done\nkill -TERM $PPID\n')
        self.assert_interrupted(f"printf 'a\\nb\\n' | xargs -P 2 -n 1 sh {job}", 143)
        self.assertTrue(wait_dead(self.pid("sibling")), "xargs가 죽은 뒤 남은 자식이 살아 있다")

    def test_rest_of_the_group_is_ended(self):
        # 다시 검증과 같은 트리를 함께 쓰지 않고, 로그 끝 뒤에 이어 쓰지 않는다
        self.assert_interrupted(f"sleep 300 & echo $! > {self.dir / 'bg'}; kill -TERM $$", -15)
        self.assertTrue(wait_dead(self.pid("bg")), "bash가 죽은 뒤 남은 자식이 살아 있다")
        self.assert_interrupted(f"sleep 300 & echo $! > {self.dir / 'bg2'}; echo '{XARGS_LINE}'; exit 1", 1)
        self.assertTrue(wait_dead(self.pid("bg2")), "종료 코드 1로 끊긴 뒤 남은 자식이 살아 있다")

    def test_line_must_start_with_the_form(self):
        for line in (f"note: {XARGS_LINE}", f"  {XARGS_LINE}", "was killed by signal 9", " killed by signal 9",
                     "killed by signal", "xargs: sleep: terminated with signal"):
            with self.subTest(line=line):
                self.assert_not_interrupted(f"echo '{line}'; exit 1", 1)

    def test_passing_run_is_not_interrupted_whatever_it_prints(self):
        res, log, _ = self.run_verify(f"echo '{XARGS_LINE}'; echo 'killed by signal 9'")
        self.assertEqual((res.ok, res.interrupted), (True, False), log)

    def test_timeout_is_not_interrupted_whatever_it_printed(self):
        with support.times_out_once_ready(self.dir / "ready"):
            res, log, _ = self.run_verify(f"echo 'killed by signal 9'; touch {self.dir / 'ready'}; sleep 300", env={"GS_VERIFY_TIMEOUT": "1"})
        self.assertEqual((res.timed_out, res.interrupted), (True, False), log)

    def test_output_that_is_not_utf8_still_reads(self):
        self.assert_interrupted(r"printf '\377\nkilled by signal 9\n'; exit 1", 1)

    def test_what_gs_wrote_before_the_run_does_not_count(self):
        spec = SimpleNamespace(verify="exit 1", verify_minutes=1)
        log = self.dir / "verify.log"
        with log.open("w", encoding="utf-8") as f:
            f.write(f"$ {XARGS_LINE}\nkilled by signal 9\n")  # 여러 줄 명령을 그대로 적은 머리말
            res = verify.run(spec, self.dir, f)
        self.assertEqual((res.code, res.interrupted), (1, False))

    def test_earlier_run_in_an_appended_log_does_not_count(self):
        spec = SimpleNamespace(verify="exit 1", verify_minutes=1)
        log = self.dir / "verify.log"
        log.write_text(f"{XARGS_LINE}\n\n종료 코드: 1\n", encoding="utf-8")
        with log.open("a", encoding="utf-8") as f:
            res = verify.run(spec, self.dir, f)
        self.assertEqual((res.code, res.interrupted), (1, False))
        self.assertIn(XARGS_LINE, log.read_text())

    def retries(self, first, second):
        """첫 실행은 first, 재시도는 second를 돈다."""
        script = self.dir / "retry.sh"
        script.write_text(f'if [ ! -f "{self.dir}/ran" ]; then touch "{self.dir}/ran"; {first}; else {second}; fi\n')
        spec = SimpleNamespace(verify=f"bash {script}", verify_minutes=1, verify_retries=1)
        log = self.dir / "verify.log"
        with log.open("w", encoding="utf-8") as f:
            res = verify.run(spec, self.dir, f)
        return res, log.read_text()

    def test_earlier_retry_does_not_count(self):
        res, log = self.retries(f"echo '{XARGS_LINE}'; exit 1", "exit 1")
        self.assertEqual((res.code, res.retries, res.interrupted), (1, 1, False), log)
        self.assertIn(XARGS_LINE, log)
        self.assertEqual(log.count("\n종료 코드: 1\n"), 2, log)

    def test_only_the_last_retry_counts(self):
        res, log = self.retries("exit 1", f"echo '{XARGS_LINE}'; exit 1")
        self.assertEqual((res.code, res.retries, res.interrupted), (1, 1, True), log)
        res, log = self.retries("kill -TERM $$", "exit 1")  # ran이 남아 첫 분기를 지나지 않는다
        self.assertEqual((res.code, res.retries, res.interrupted), (1, 1, False), log)

    def test_retry_that_passes_is_not_interrupted(self):
        res, log = self.retries("kill -TERM $$", "exit 0")
        self.assertEqual((res.ok, res.retries, res.interrupted), (True, 1, False), log)
        self.assertTrue(log.endswith("\n종료 코드: 0\n"), log)


if __name__ == "__main__":
    unittest.main()
