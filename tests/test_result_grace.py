"""성공 result 뒤 끝나지 않는 worker의 유예 정리(goldstack-v35 06, issue #65).

가짜 worker는 커밋하고 끝 이벤트를 쓴 뒤 자식 `sleep`을 백그라운드로 띄우고 기다린다. 유예는 시험에서 GRACE초로 줄인다.
"""
import json
import os
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from support import FAKE_HERDR, alive, kill_quietly
from gs import config, go, state, streamfmt, worker

GRACE = 0.2  # 시험의 유예(초)
HANG = 37  # 정리되지 않으면 자식이 이만큼 남는다(idle 시간 초과 IDLE_SECONDS보다 길다)
SHORT = 0.8  # 정리하지 않아야 하는 시험의 자식. 스스로 끝나 worker도 끝난다


def result(is_error: bool) -> str:
    return json.dumps({"type": "result", "subtype": "error_during_execution" if is_error else "success",
                       "is_error": is_error, "result": "끝"})


def worker_script(end: str, child: float, orphan: bool = False) -> str:
    """커밋 → 끝 이벤트 → 자식 sleep을 띄우고 기다린다. 자식 pid는 child.pid에 남긴다.

    orphan이면 기다리지 않고 먼저 끝난다: 고아가 된 자식(PPID 1)이 stdout을 쥐고 있어 run.sh의 파이프가 끝나지 않는다.
    """
    return textwrap.dedent(f'''\
        here="$(dirname "$0")"
        echo "$GS_TICKET" >> "$here/calls.log"
        echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        echo '{end}'
        sleep {child} &
        echo $! > "$here/child.pid"
        {"exit 0" if orphan else "wait"}
    ''')


class ResultGraceGoTest(support.GoTest):
    def run_go(self, end: str, child: float, runner: str = "subprocess", grace: float | None = GRACE, orphan: bool = False):
        (self.bin / "worker.sh").write_text(worker_script(end, child, orphan))
        env = {"GS_RUNNER": runner}
        if runner == "herdr":
            path = self.bin / "herdr"
            path.write_text("#!/bin/bash\n" + FAKE_HERDR)
            path.chmod(0o755)
            env.update(HERDR_BIN_PATH=str(path), HERDR_SESSION="t", HERDR_WORKSPACE_ID="w1")
        patches = [mock.patch.dict(os.environ, env), mock.patch("gs.go._idle_seconds", return_value=support.IDLE_SECONDS),
                   mock.patch.object(worker, "POLL_SECONDS", 0.05)]
        if grace is not None:
            patches.append(mock.patch("gs.go._result_grace", return_value=grace))
        for p in patches:
            p.start()
        try:
            code, out, err = self.go("--only", "01")
        finally:
            for p in reversed(patches):
                p.stop()
        pid_file = self.bin / "child.pid"
        if pid_file.exists():
            self.addCleanup(kill_quietly, int(pid_file.read_text()))
        return code, out, err

    @property
    def attempt(self) -> Path:
        return self.rundir / "01" / "1"

    def assert_cleaned_and_reviewed(self, runner: str, orphan: bool = False):
        code, out, err = self.run_go(result(False), HANG, runner, orphan=orphan)
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"[01] result 뒤 {GRACE:g}초 지나도 끝나지 않아 정리: 남은 프로세스 ", out)
        self.assertNotIn("시간 초과", out)
        child = int((self.bin / "child.pid").read_text())
        self.assertFalse(alive(child), "정리했는데 자식 sleep이 살아 있다")
        listed = (self.attempt / worker.LEFTOVER_PROCS).read_text().splitlines()
        self.assertEqual(listed[0], "PID PPID STAT COMMAND")
        self.assertIn(f"sleep {HANG}", "\n".join(listed))
        self.assertTrue(any(line.split()[0] == str(child) for line in listed[1:]), listed)
        n = int(out.split("남은 프로세스 ", 1)[1].split("개", 1)[0])
        self.assertEqual(n, len(listed) - 1)
        self.assertEqual((self.attempt / "exit").read_text().strip(), "0")
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertTrue(ts.review, "리뷰로 넘어가지 않았다")
        self.assertTrue(self.lines("review.calls"), "리뷰어를 부르지 않았다")
        self.assertEqual(self.calls(), ["01"])  # 재시도 없음
        self.assertEqual(self.merged(), ["01"])
        # 소요 시간은 정리한 때까지다: 자식이 스스로 끝날 때(HANG초)가 아니다
        rec = next(x for x in state.load(self.rundir, "demo").metrics["workers"] if x["dir"] == str(self.attempt))
        self.assertIsNotNone(rec["seconds"])
        self.assertLess(rec["seconds"], HANG)
        return out

    def test_success_result_then_hang_is_cleaned_after_grace_and_reviewed(self):
        self.assert_cleaned_and_reviewed("subprocess")

    def test_orphaned_child_holding_the_pipe_is_listed_and_cleaned(self):
        """worker는 끝났는데 고아가 된 자식(PPID 1)이 stdout을 쥐고 있어 run.sh가 끝나지 않는다. 부모 관계로는 못 찾고 그룹으로 찾는다."""
        self.assert_cleaned_and_reviewed("subprocess", orphan=True)

    def test_herdr_runner_cleans_the_same_way(self):
        self.assert_cleaned_and_reviewed("herdr")
        cmds = (self.bin / "herdr.log").read_text().splitlines()
        self.assertIn("pane close w1:p1", cmds)  # 성공한 worker처럼 pane을 닫는다

    def test_error_result_is_not_cleaned(self):
        code, out, err = self.run_go(result(True), SHORT)
        self.assertEqual(code, 0, out + err)  # 자식이 끝나 worker도 종료 0으로 끝났다
        self.assertNotIn("result 뒤", out)
        self.assertFalse((self.attempt / worker.LEFTOVER_PROCS).exists())

    def test_zero_grace_keeps_current_behavior(self):
        path = self.repo / config.CONFIG_PATH
        text = path.read_text()
        self.assertIn("result_grace_seconds = 60\n", text)
        path.write_text(text.replace("result_grace_seconds = 60\n", "result_grace_seconds = 0\n"))
        code, out, err = self.run_go(result(False), SHORT, grace=None)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("result 뒤", out)
        self.assertFalse((self.attempt / worker.LEFTOVER_PROCS).exists())


class TreeTest(unittest.TestCase):
    """worker._tree: run.sh 명령줄 → 자손, 그리고 그룹 리더면 그 그룹(고아 포함)."""
    SCRIPT = Path("/r/01/1/run.sh")

    def tree(self, table, mine: int = 9):
        with mock.patch.object(worker.os, "getpid", return_value=9), mock.patch.object(worker.os, "getpgrp", return_value=mine):
            return sorted(worker._tree(table, self.SCRIPT))

    def test_leader_group_brings_orphans_and_setsid_descendants(self):
        table = {
            9: (1, 9, "S", "python -m gs.cli go"),  # gs
            100: (9, 100, "S", f"bash {self.SCRIPT}"),  # run.sh: 그룹 리더
            101: (100, 100, "S", f"bash {self.SCRIPT}"),  # 서브셸
            102: (100, 100, "S", "tee -a worker.log"),
            200: (1, 100, "S", "sleep 37"),  # 부모가 먼저 끝난 자식
            201: (200, 100, "Z", "(sh)"),
            300: (101, 300, "Ss", "nohup poll"),  # setsid로 떼어 낸 자손
            301: (1, 300, "S", "sleep 99"),
            400: (1, 400, "S", "sleep 5"),  # 상관없는 프로세스
            500: (9, 9, "S", "bash /r/02/1/run.sh"),  # 다른 시도
            501: (1, 9, "S", "sleep 7"),  # gs 그룹의 고아
        }
        self.assertEqual(self.tree(table), [100, 101, 102, 200, 201, 300, 301])
        self.assertEqual(self.tree(table, mine=100), [100, 101, 102, 300, 301])  # gs 자신의 그룹은 넣지 않는다

    def test_group_of_a_root_that_is_not_its_leader_is_not_taken(self):
        table = {
            9: (1, 9, "S", "python -m gs.cli go"),
            800: (1, 800, "Ss", "-zsh"),  # pane 셸: 작업마다 그룹을 나누지 않으면 run.sh가 이 그룹에 든다
            801: (800, 800, "S", f"bash {self.SCRIPT}"),
            802: (801, 800, "S", "tee -a worker.log"),
            803: (1, 800, "S", "sleep 37"),
            900: (9, 9, "S", f"bash {self.SCRIPT}"),  # gs 그룹 안의 run.sh
            901: (1, 9, "S", "sleep 7"),
        }
        self.assertEqual(self.tree(table), [801, 802, 900])


class ResultWatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.log = self.tmp / "worker.log"

    def write(self, *lines: str, newline: bool = True):
        with self.log.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if newline else ""))

    def test_claude_result_is_success_only_when_is_error_false(self):
        for is_error, found in ((False, True), (True, False), (None, False)):
            with self.subTest(is_error=is_error):
                self.log.unlink(missing_ok=True)
                ev = {"type": "result", "result": "끝"}
                if is_error is not None:
                    ev["is_error"] = is_error
                self.write("not json", json.dumps({"type": "assistant"}), json.dumps(ev))
                self.assertEqual(streamfmt.ResultWatch(self.log).success_end(), ev if found else None)

    def test_codex_turn_completed_is_success_and_agy_is_not_judged(self):
        done = {"type": "turn.completed"}
        cases = ((done, done), ({"type": "turn.failed", "error": "x"}, None),
                 ({"event": "result", "result": {"status": "SUCCESS"}}, None), ({"type": "item.completed"}, None))
        for ev, found in cases:
            with self.subTest(ev=ev):
                self.log.unlink(missing_ok=True)
                self.write(json.dumps(ev))
                self.assertEqual(streamfmt.ResultWatch(self.log).success_end(), found)

    def test_reads_on_from_last_complete_line_and_latest_end_wins(self):
        watch = streamfmt.ResultWatch(self.log)
        self.assertIsNone(watch.success_end())  # 로그가 아직 없다
        line = result(False)
        self.write(line[:10], newline=False)
        self.assertIsNone(watch.success_end())  # 다 쓰지 않은 줄은 다음에 읽는다
        self.write(line[10:])
        self.assertEqual(watch.success_end(), json.loads(line))
        self.write(json.dumps({"type": "assistant"}))
        self.assertEqual(watch.success_end(), json.loads(line))  # 끝이 아닌 줄은 판정을 바꾸지 않는다
        self.write(result(True))
        self.assertIsNone(watch.success_end())  # 마지막 끝 이벤트가 실패다


class ResultClockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        job = SimpleNamespace(log=self.tmp / "worker.log")
        self.a = go.Active(t=None, proc=SimpleNamespace(job=job), branch="b", wt=self.tmp, base="0")
        self.log = job.log

    def test_clock_starts_at_first_success_and_does_not_restart_when_log_grows(self):
        self.log.write_text(json.dumps({"type": "assistant"}) + "\n")
        self.assertIsNone(self.a.result_seconds())
        self.assertIsNone(self.a.result_at)
        with self.log.open("a") as f:
            f.write(result(False) + "\n")
        self.assertIsNotNone(self.a.result_seconds())
        first = self.a.result_at
        self.assertIsNotNone(first)
        time.sleep(0.02)
        with self.log.open("a") as f:
            f.write(json.dumps({"type": "assistant"}) + "\n" + result(False) + "\n")
        waited = self.a.result_seconds()
        self.assertEqual(self.a.result_at, first)
        self.assertGreaterEqual(waited, 0.02)

    def test_failure_end_clears_the_clock_and_a_new_success_starts_it_again(self):
        clock = [100.0]
        with mock.patch.object(go.time, "monotonic", lambda: clock[0]):
            with self.log.open("a") as f:
                f.write(result(False) + "\n")
            self.assertEqual(self.a.result_seconds(), 0)
            clock[0] = 150.0
            with self.log.open("a") as f:
                f.write(result(True) + "\n")
            self.assertIsNone(self.a.result_seconds())
            self.assertIsNone(self.a.result_at)
            clock[0] = 200.0
            with self.log.open("a") as f:
                f.write(result(False) + "\n")
            self.assertEqual(self.a.result_seconds(), 0)  # 취소된 첫 성공(100)부터 재지 않는다
            clock[0] = 205.0
            self.assertEqual(self.a.result_seconds(), 5)

    def test_grace_comes_from_config(self):
        r = SimpleNamespace(cfg=SimpleNamespace(timeouts=config.TimeoutsConfig(30, 10, 60, result_grace_seconds=7)))
        self.assertEqual(go._result_grace(r), 7)


if __name__ == "__main__":
    unittest.main()
