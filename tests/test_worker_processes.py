"""worker 손잡이는 정상 종료·종료 지연·결과 처리 오류에서도 끝내고 거둔다."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import go, worker
from gs.feature import Ticket


class WorkerProcessTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                             path=Path("01-t.md"))
        self.runner = worker.SubprocessRunner()

    def start(self, command="exec sleep 300"):
        job = worker.Job(ticket=self.ticket, worktree=self.root, rundir=self.root)
        job.script.write_text(command + "\n")
        proc = worker.Proc(job, self.runner, "test")
        self.addCleanup(proc.stop)
        return proc

    def test_finish_reaps_exited_shell(self):
        proc = self.start("exit 0")
        proc.finish(True)
        self.assertEqual(proc.handle.returncode, 0)

    def test_finish_stops_and_reaps_shell_that_does_not_exit(self):
        proc = self.start()
        proc.finish(True)
        self.assertIsNotNone(proc.handle.returncode)

    def test_stop_reaps_worker(self):
        proc = self.start()
        proc.stop()
        self.assertIsNotNone(proc.handle.returncode)

    def test_result_processing_exception_still_reaps_current_worker(self):
        proc = self.start()
        active = SimpleNamespace(t=self.ticket, proc=proc, fix=False)
        run = SimpleNamespace(feat=SimpleNamespace(spec=SimpleNamespace(max_workers=1), tickets={"01": self.ticket}),
                              repo=self.root, iwt=self.root, rundir=self.root, name="demo", order=["01"])
        with mock.patch.object(worker, "make_runner", return_value=self.runner), \
                mock.patch.object(go.git, "sha", return_value="base"), \
                mock.patch.object(go, "say"), \
                mock.patch.object(go, "_skip_blocked"), \
                mock.patch.object(go, "_frontier", return_value=["01"]), \
                mock.patch.object(go, "_start", return_value=active), \
                mock.patch.object(go, "_wait_any", return_value=("01", 0, "")), \
                mock.patch.object(go, "_finish", side_effect=RuntimeError("result processing failed")):
            with self.assertRaisesRegex(RuntimeError, "result processing failed"):
                go._loop(run)
        self.assertIsNotNone(proc.handle.returncode)


if __name__ == "__main__":
    unittest.main()
