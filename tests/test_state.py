"""state.json 원자적 쓰기, 잠금, 표시 함수 단위 시험."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import state
from gs.status import duration


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rundir = Path(self.tmp.name) / "run"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_and_missing(self):
        self.assertEqual(state.load(self.rundir, "f").tickets, {})
        st = state.State(feature="f", only=["01"])
        st.ticket("01").status = state.RUNNING
        st.ticket("01").attempts = 2
        state.save(self.rundir, st)
        got = state.load(self.rundir, "f")
        self.assertEqual(got.only, ["01"])
        self.assertEqual((got.tickets["01"].status, got.tickets["01"].attempts), ("running", 2))
        self.assertTrue(got.updated_at)

    def test_failed_write_keeps_old_file(self):
        st = state.State(feature="f")
        st.ticket("01").status = state.MERGED
        state.save(self.rundir, st)
        st.ticket("01").status = state.FAILED
        with mock.patch("gs.state.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                state.save(self.rundir, st)
        self.assertEqual(json.loads(state.path(self.rundir).read_text())["tickets"]["01"]["status"], "merged")
        self.assertEqual([p.name for p in self.rundir.iterdir()], ["state.json"])

    def test_unknown_keys_are_ignored(self):
        self.rundir.mkdir()
        state.path(self.rundir).write_text(json.dumps({"feature": "f", "x": 1, "tickets": {"01": {"status": "merged",
                                                                                               "y": 2}}}))
        self.assertEqual(state.load(self.rundir, "f").tickets["01"].status, "merged")

    def test_lock(self):
        self.assertIsNone(state.running_pid(self.rundir))
        with state.Lock(self.rundir):
            self.assertEqual(state.running_pid(self.rundir), os.getpid())
            with self.assertRaises(state.Locked) as cm:
                state.Lock(self.rundir).acquire()
            self.assertEqual(cm.exception.pid, os.getpid())
        self.assertIsNone(state.running_pid(self.rundir))
        with state.Lock(self.rundir):  # 다시 잡을 수 있다
            pass

    def test_running_pid_needs_held_lock(self):  # 03 ③: 죽은 gs의 pid가 다른 프로세스에 재사용된 경우
        self.rundir.mkdir()
        state.lock_path(self.rundir).write_text(f"{os.getpid()}\n")  # 살아 있는 pid지만 잠금은 아무도 안 잡았다
        self.assertIsNone(state.running_pid(self.rundir))
        with state.Lock(self.rundir):  # 잠금을 잡을 수 있다(status가 잠깐 들여다본 뒤에도)
            self.assertEqual(state.running_pid(self.rundir), os.getpid())

    def test_duration(self):
        self.assertEqual(duration(5), "5s")
        self.assertEqual(duration(125), "2m05s")
        self.assertEqual(duration(3 * 3600 + 7 * 60 + 9), "3h07m")
        self.assertEqual(duration(-3), "0s")


if __name__ == "__main__":
    unittest.main()
