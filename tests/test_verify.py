"""verify 시간 제한(verify.py): 새 프로세스 그룹, SIGTERM → SIGKILL, 자손까지 끝낸다. 로그 끝의 종료 코드 줄과 끊김 판정.

끊김 시험은 실제 프로세스에 신호를 보낸다. xargs 문구는 이 맥의 실측 값이다: `printf 'a\\nb\\n' | xargs -P 2 -n 1 sh -c 'kill -TERM $$'`는
종료 코드 1로 끝나고 `xargs: sh: terminated with signal 15; aborting`을 남긴다(macOS 27.0.1, -KILL이면 signal 9). 리눅스 xargs는 재지 않아 그 시험은 이 맥에서만 돈다.

goldstack-v22 01: 표지와 stop_stale(StaleTest). 실제 sleep을 띄운 부모를 SIGKILL해 살아 남은 그룹을 끝낸다. `gs go`에서 부르는 것은 test_verify_repair.py의 StaleResumeTest가 본다.
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


# gs 대신 검증을 띄우는 부모. 시험이 이 부모만 SIGKILL한다
PARENT = """
import sys
from pathlib import Path
from types import SimpleNamespace
from gs import verify
log = Path(sys.argv[1])
with log.open("w", encoding="utf-8") as f:
    verify.run(SimpleNamespace(verify=sys.argv[2], verify_minutes=20), log.parent, f)
"""


class StaleTest(Case):
    def setUp(self):
        super().setUp()
        self.run_dir = self.dir / "feature/run"

    def rows(self):
        out = subprocess.run(["ps", "-A", "-ww", "-o", "pgid=,command="], capture_output=True).stdout.decode("utf-8", errors="replace")
        return [row.strip().split(None, 1) for row in out.split("\n") if len(row.split(None, 1)) == 2]

    def left_behind(self, log, command="sleep 300", ready=None):
        """부모가 command를 검증으로 띄우고 SIGKILL로 죽는다. 살아 남은 프로세스 그룹을 돌려준다."""
        log.parent.mkdir(parents=True, exist_ok=True)
        code = str(Path(verify.__file__).parents[1])
        parent = subprocess.Popen([sys.executable, "-c", PARENT, str(log), command], env={**os.environ, "PYTHONPATH": code},
                                  stdin=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(parent.wait)
        self.addCleanup(parent.kill)
        deadline, suffix, group = time.monotonic() + 120, " " + verify.mark(log), None
        while group is None or (ready and not ready.exists()):
            self.assertIsNone(parent.poll(), "부모가 먼저 끝났다")
            self.assertLess(time.monotonic(), deadline, "표지가 ps에 보이지 않는다")
            group = next((int(pgid) for pgid, cmd in self.rows() if cmd.endswith(suffix)), None)
            time.sleep(0.02)
        self.addCleanup(support.kill_group_quietly, group)
        os.kill(parent.pid, signal.SIGKILL)
        parent.wait()
        self.assertTrue(support.group_alive(group), "부모가 죽어도 검증은 살아 있어야 한다")
        return group

    def other_group(self, *argv):
        p = subprocess.Popen(list(argv), stdin=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(p.wait)
        self.addCleanup(support.kill_group_quietly, p.pid)
        return p.pid

    def test_group_of_a_killed_parent_ends_and_other_marks_stay(self):
        mine = self.left_behind(self.run_dir / "01/1/verify.log")
        others = {"다른 feature": self.left_behind(self.dir / "other/run/01/1/verify.log"),
                  "이름 앞부분이 같은 디렉터리": self.left_behind(self.dir / "feature/run2/01/1/verify.log"),
                  "표지 없음": self.other_group("bash", "-c", "sleep 300; exit $?"),
                  "bash가 아닌데 끝이 같은 명령": self.other_group("sh", "-c", "sleep 300; exit $?", verify.mark(self.run_dir / "01/1/verify.log"))}
        lines = verify.stop_stale(self.run_dir)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("지난 실행의 검증이 아직 돌고 있어 끝냈다", lines[0])
        self.assertIn(verify.mark(self.run_dir / "01/1/verify.log"), lines[0])
        self.assertFalse(support.group_alive(mine), "지난 검증의 그룹이 살아 있다")
        for name, group in others.items():
            self.assertTrue(support.group_alive(group), f"{name}: 건드리면 안 되는 그룹이 끝났다")

    def test_cleanup_ends_every_verify_of_the_run(self):
        # 티켓 검증과 integration 검증은 같은 worktree를 쓴다. 재개 뒤 어느 검증이 먼저 돌든 옛 검증과 겹치지 않는다
        logs = ("01/1/verify.log", "02/1/repair/verify.log", "finish/integration-verify.log")
        groups = [self.left_behind(self.run_dir / log) for log in logs]
        self.assertEqual(len(verify.stop_stale(self.run_dir)), 3)
        self.assertEqual([support.group_alive(g) for g in groups], [False] * 3)

    def test_verify_of_a_feature_inside_a_worktree_stays(self):
        # worktree도 레포 루트가 되어(feature.find_repo_root) 다른 feature의 run이 이 run 아래에 생긴다. 그 잠금은 따로라 옛 검증이 아니다
        outer = self.dir / ".goldstack/work/outer/run"
        inner = outer / "wt/01/.goldstack/work/other/run"
        mine = self.left_behind(outer / "01/1/verify.log")
        theirs = self.left_behind(inner / "01/1/verify.log")
        lines = verify.stop_stale(outer)
        self.assertEqual(len(lines), 1, lines)
        self.assertFalse(support.group_alive(mine), "지난 검증의 그룹이 살아 있다")
        self.assertTrue(support.group_alive(theirs), "worktree 안의 다른 feature 검증이 끝났다")
        self.assertEqual(len(verify.stop_stale(inner)), 1, "그 feature의 gs go는 제 검증을 찾아야 한다")
        self.assertFalse(support.group_alive(theirs))

    def test_mark_is_the_last_word_and_differs_per_verify(self):
        log = self.run_dir / "01/1/verify.log"
        group = self.left_behind(log)
        [command] = [cmd for pgid, cmd in self.rows() if int(pgid) == group and cmd.startswith("bash ")]
        self.assertTrue(command.startswith("bash -c sleep 300"), command)
        self.assertTrue(command.endswith(f" gs-verify:{log.resolve()}"), command)
        marks = {verify.mark(self.run_dir / rel) for rel in ("01/1/verify.log", "01/2/verify.log", "02/1/verify.log", "finish/main-verify.log")}
        self.assertEqual(len(marks), 4)

    def test_mark_survives_a_locale_that_garbles_paths(self):
        run_dir = self.dir / "한글 경로/run"
        group = self.left_behind(run_dir / "01/1/verify.log")
        with mock.patch.dict(os.environ, {"LC_ALL": "C"}):  # launchd·cron처럼 로캘이 없으면 macOS ps는 한글을 `M-m...`로 보인다
            lines = verify.stop_stale(run_dir)
        self.assertEqual(len(lines), 1, lines)
        self.assertFalse(support.group_alive(group))

    def test_group_ignoring_sigterm_gets_sigkill(self):
        ready = self.dir / "ready"
        group = self.left_behind(self.run_dir / "01/1/verify.log", f"trap '' TERM; sleep 300 & touch {ready}; wait", ready)
        with mock.patch.object(verify, "GRACE", 0.3), mock.patch.object(verify.os, "killpg", wraps=os.killpg) as killpg:
            lines = verify.stop_stale(self.run_dir)
        self.assertIn("끝냈다", lines[0])
        self.assertEqual([call.args[1] for call in killpg.call_args_list[:2]], [signal.SIGTERM, signal.SIGKILL])
        self.assertFalse(support.group_alive(group))

    def test_keeping_bash_keeps_the_exit_code(self):
        for command, code in (("sh -c 'exit 5'", 5), ("exit 3", 3), ("(exit 4) # 주석", 4), ("true &", 0), ("set -e; false; true", 1), ("no-such-command-xyz", 127)):
            with self.subTest(command=command):
                res, log, _ = self.run_verify(command)
                self.assertEqual((res.code, res.interrupted), (code, False), log)

    def test_single_command_killed_by_a_signal_is_still_interrupted(self):
        res, log, _ = self.run_verify("sh -c 'kill -TERM $$'")
        self.assertEqual((res.code, res.interrupted), (143, True), log)

    def test_nothing_to_stop_is_silent(self):
        with mock.patch.object(verify, "_signal") as send:
            self.assertEqual(verify.stop_stale(self.run_dir), [])
        send.assert_not_called()

    def test_rows_that_are_not_stale_verifies_are_left_alone(self):
        mine = verify.mark(self.run_dir / "01/1/verify.log")
        rows = [(os.getpgrp(), "S", f"bash -c x\\012exit $? {mine}"),  # gs 자신의 그룹
                (1, "S", f"bash -c x\\012exit $? {mine}"),
                (4242, "Z", f"bash -c x\\012exit $? {mine}"),
                (4243, "S", f"bash -c x\\012exit $? {verify.mark(self.dir / 'other/run/01/1/verify.log')}"),
                (4244, "S", f"grep x exit $? {mine}"),
                (4245, "S", f"bash -c grep {mine}"),  # 사람이나 worker가 표지를 찾는 명령
                (4246, "S", f"bash -c x\\012exit $? {verify.mark(self.run_dir / 'gs-main-x/base/.goldstack/work/other/run/finish/main-verify.log')}")]  # 임시 worktree 안의 다른 feature
        with mock.patch.object(verify, "_ps", return_value=rows), mock.patch.object(verify, "_signal") as send:
            self.assertEqual(verify.stop_stale(self.run_dir), [])
        send.assert_not_called()

    def test_ps_failure_warns_instead_of_raising(self):
        for failure in (FileNotFoundError("ps"), subprocess.TimeoutExpired("ps", 30), subprocess.CompletedProcess("ps", 1, b"", b"not allowed")):
            with self.subTest(failure=failure), mock.patch.object(verify.subprocess, "run", side_effect=[failure]):
                [line] = verify.stop_stale(self.run_dir)
            self.assertTrue(line.startswith("경고: 지난 실행의 검증을 찾지 못했다"), line)

    def test_group_that_will_not_end_warns_instead_of_raising(self):
        group = self.left_behind(self.run_dir / "01/1/verify.log")
        with mock.patch.object(verify, "GRACE", 0.05), mock.patch.object(verify, "_signal", return_value=False):
            [line] = verify.stop_stale(self.run_dir)
        self.assertTrue(line.startswith("경고: 지난 실행의 검증을 끝내지 못했다"), line)
        self.assertIn(str(group), line)
        self.assertTrue(support.group_alive(group))

    def test_ps_failing_while_ending_warns_instead_of_raising(self):
        mine = verify.mark(self.run_dir / "01/1/verify.log")
        rows = [(4242, "S", f"bash -c x\\012exit $? {mine}")]
        with mock.patch.object(verify, "_ps", side_effect=[rows, OSError("ps 없음")]), mock.patch.object(verify, "_signal", return_value=False):
            [line] = verify.stop_stale(self.run_dir)
        self.assertTrue(line.startswith("경고: 지난 실행의 검증을 끝내지 못했다"), line)
        self.assertIn("ps 없음", line)


if __name__ == "__main__":
    unittest.main()
