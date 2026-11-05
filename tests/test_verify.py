"""verify 시간 제한(verify.py): 새 프로세스 그룹, SIGTERM → SIGKILL, 자손까지 끝낸다."""
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import verify


def alive(pid):
    """좀비는 죽은 것으로 본다."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def times_out_once_ready(ready: Path):
    """`bash -c` 명령의 시간 제한을 실제 시간 대신 "명령이 준비됐다"로 정한다.

    짧은 제한(1초)이면 부하에서 bash가 pid 파일을 쓰기도 전에 시간이 끝나 시험이 흔들린다. 명령이 할 일을 마치고 `ready` 파일을 만든다.
    그 파일이 생기고도 명령이 안 끝났으면 시간 초과다. 시간 초과 뒤 정리(SIGTERM→SIGKILL, 자손 종료)는 실제 코드가 한다.
    """
    class ReadyPopen(subprocess.Popen):
        def wait(self, timeout=None):
            if timeout is None or self.args[0] != "bash":
                return super().wait(timeout)
            give_up = time.monotonic() + 120  # 명령이 끝내 준비되지 못해도 시험이 영영 서지 않게. 그때는 단정이 실패한다
            while True:
                try:
                    return super().wait(0.05)
                except subprocess.TimeoutExpired:
                    if ready.exists() or time.monotonic() > give_up:
                        raise

    return mock.patch.object(subprocess, "Popen", ReadyPopen)


def wait_dead(pid, seconds=30.0):
    """부모(bash)가 죽은 뒤 고아는 init이 거둔다. 잠깐 기다려 본다."""
    deadline = time.monotonic() + seconds
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not alive(pid)


class VerifyTest(unittest.TestCase):
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
        return res, log.read_text(encoding="utf-8"), time.monotonic() - start

    def pid(self, name):
        pid = int((self.dir / name).read_text().strip())
        self.pids.append(pid)
        return pid

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
        self.assertEqual(log, "hi\n")
        res, log, _ = self.run_verify("echo ok")
        self.assertTrue(res.ok)
        self.assertNotIn("시간 초과", log)

    def test_timeout_kills_background_children(self):
        with times_out_once_ready(self.dir / "ready"), mock.patch.object(verify, "GRACE", 60), \
                mock.patch.object(verify.os, "killpg", wraps=os.killpg) as killpg:  # 부하로 SIGTERM이 늦어도 SIGKILL로 넘어가지 않게
            res, log, _ = self.run_verify(f"sleep 300 & echo $! > {self.dir / 'bg'}; echo $$ > {self.dir / 'sh'}; "
                                          f"echo started; touch {self.dir / 'ready'}; sleep 300", env={"GS_VERIFY_TIMEOUT": "1"})
        self.assertTrue(res.timed_out)
        self.assertFalse(res.ok)
        self.assertNotIn(signal.SIGKILL, [call.args[1] for call in killpg.call_args_list])  # SIGTERM으로 끝나 SIGKILL까지 가지 않았다
        self.assertTrue(wait_dead(self.pid("bg")), "백그라운드 자식이 살아 있다")
        self.assertTrue(wait_dead(self.pid("sh")))
        self.assertIn("started\n", log)
        self.assertTrue(log.endswith("\n시간 초과: 0.02분\n"), log)

    def test_timeout_sigkills_group_ignoring_sigterm(self):
        with times_out_once_ready(self.dir / "ready"), mock.patch.object(verify, "GRACE", 0.3), \
                mock.patch.object(verify.os, "killpg", wraps=os.killpg) as killpg:
            res, log, _ = self.run_verify(f"trap '' TERM; sleep 300 & echo $! > {self.dir / 'bg'}; touch {self.dir / 'ready'}; sleep 300",
                                          env={"GS_VERIFY_TIMEOUT": "0.5"})
        self.assertTrue(res.timed_out)
        signals = [call.args[1] for call in killpg.call_args_list]
        self.assertIn(signal.SIGKILL, signals)  # SIGTERM을 무시해 SIGKILL까지 갔다
        self.assertLess(signals.index(signal.SIGTERM), signals.index(signal.SIGKILL))
        self.assertTrue(wait_dead(self.pid("bg")), "SIGTERM을 무시한 자식이 살아 있다")
        self.assertTrue(log.endswith("시간 초과: 0.01분\n"), log)


if __name__ == "__main__":
    unittest.main()
