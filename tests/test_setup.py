"""worktree 준비 명령: 실제 셸·프로세스 그룹과 로컬 원격으로 위치별 실패·재개를 확인한다."""
import json
import os
import signal
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import support
from gs import config, finish, setup, state, verify
from support import sh
from test_verify import times_out_once_ready, wait_dead


class SetupCommandTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.wt = Path(tmp.name)
        sh(self.wt, "git", "init", "-q")
        sh(self.wt, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init", "--allow-empty")
        self.log = self.wt / "attempt/setup.log"
        self.cfg = config.Config(config.GitConfig("origin", "main"), config.ModelsConfig("opus", "opus", "agy", ""),
                                 config.TimeoutsConfig(30, 10, 60), config.NotifyConfig(False))

    def run_setup(self, command, seconds=60):
        cfg = replace(self.cfg, worktree=config.WorktreeConfig(command),
                      timeouts=replace(self.cfg.timeouts, setup_minutes=seconds / 60))
        return setup.run(cfg, self.wt, self.log)

    def test_cwd_environment_output_and_exit_code(self):
        with mock.patch.dict(os.environ, {"GS_ROLE": "worker", "VIRTUAL_ENV": "/gs/venv"}):
            res = self.run_setup('test -z "$GS_ROLE" && test -z "$VIRTUAL_ENV" && echo ready > installed; '
                                 'pwd; echo stderr >&2; exit 7')
            self.assertEqual(os.environ["GS_ROLE"], "worker")
            self.assertEqual(os.environ["VIRTUAL_ENV"], "/gs/venv")
        self.assertEqual((res.code, res.timed_out, res.ok), (7, False, False))
        self.assertEqual((self.wt / "installed").read_text(), "ready\n")
        self.assertIn(str(self.wt), self.log.read_text())
        self.assertIn("stderr\n", self.log.read_text())

    def test_empty_setup_does_not_start_process_or_create_log(self):
        with mock.patch("gs.setup.subprocess.Popen") as popen:
            self.assertTrue(self.run_setup(" \n ").ok)
        popen.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_timeout_stops_children_including_sigterm_ignored(self):
        for n, trap in enumerate(("", "trap '' TERM;")):
            ready = self.wt / f"ready{n}"
            with self.subTest(trap=trap), mock.patch.object(verify, "GRACE", 0.2), times_out_once_ready(ready):
                res = self.run_setup(f"{trap} sleep 300 & echo $! > child; echo $$ > shell; touch {ready}; wait", seconds=0.2)
                pids = [int((self.wt / name).read_text()) for name in ("child", "shell")]
                try:
                    self.assertTrue(res.timed_out)
                    self.assertFalse(res.ok)
                    for pid in pids:
                        self.assertTrue(wait_dead(pid), f"준비 프로세스가 남았다: {pid}")
                    self.assertIn("시간 초과:", self.log.read_text())
                finally:
                    for pid in pids:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_timeout_uses_setup_minutes_not_verify_timeout(self):
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "0.01"}):
            self.assertTrue(self.run_setup("sleep 0.05; echo done", seconds=600).ok)

    def test_launch_error_is_a_setup_failure(self):
        with mock.patch("gs.setup.subprocess.Popen", side_effect=OSError("cannot start bash")):
            self.assertFalse(self.run_setup("true").ok)
        self.assertIn("준비 명령 실행 실패", self.log.read_text())


class WorktreeSetupTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    tearDown, go, calls, rundir = G.tearDown, G.go, G.calls, G.rundir
    integration, final_report, lines, remote_files = G.integration, G.final_report, G.lines, G.remote_files

    def setUp(self):
        self.G.setUp(self)

    def configure(self, command, verify_command=None, *, ignored=True):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('setup = ""', "setup = " + json.dumps(command)))
        # 준비 산출물은 의존성 설치와 같이 gitignore에 둔다.
        with (self.repo / ".gitignore").open("a") as stream:
            stream.write("installed\n.env\n" if ignored else ".env\n")
        if verify_command:
            path = self.repo / ".goldstack/work/demo/spec.md"
            path.write_text(path.read_text().replace("test ! -f BROKEN", verify_command))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "worktree setup")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def setup_calls(self):
        path = self.bin / "setups"
        return path.read_text().splitlines() if path.exists() else []

    @property
    def record_setup(self):
        return f'echo "$PWD" >> {self.bin / "setups"}; '

    def test_installed_files_visible_to_worker_and_all_verifies(self):
        self.configure(self.record_setup + 'test -z "$GS_ROLE" && echo ready > installed && echo secret > .env',
                       f'test -f installed && echo "$PWD" >> {self.bin / "verifies"}')
        path = self.bin / "worker.sh"
        path.write_text('test -f installed || exit 12\n' + path.read_text())
        snapshots = []
        real_save = state.save

        def observe(rundir, st):
            real_save(rundir, st)
            snapshots.append(json.loads(state.path(rundir).read_text()))

        with mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        calls = self.setup_calls()
        self.assertEqual(len(calls), 3)
        self.assertEqual([Path(c).name for c in calls], ["integration", "01", "base"])
        self.assertIn("gs-main-", calls[-1])
        self.assertEqual(len((self.bin / "verifies").read_text().splitlines()), 3)
        for path in ("01/1/setup.log", "integration/1/setup.log", "finish/setup.log"):
            self.assertTrue((self.rundir / path).is_file(), path)
            self.assertIn(path, self.final_report())
        self.assertTrue(any(p["phase"] == "setup" for s in snapshots for p in s["progress"]["running"]))

    def test_ticket_setup_failure_is_terminal_without_worker_retry_and_report_has_tail(self):
        self.configure(self.record_setup + 'case "$PWD" in */wt/01*) echo setup-boom; exit 9;; esac')
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets
        self.assertEqual((ts["01"].status, ts["01"].reason, ts["01"].attempts, ts["01"].failures),
                         (state.FAILED, "준비 실패", 1, 1))
        self.assertEqual(ts["04"].status, state.SKIPPED)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.rundir / "01/2").exists())
        self.assertFalse((self.rundir / "01/1/verify.log").exists())
        self.assertIn("setup-boom", self.final_report())
        self.assertIn("01/1/setup.log", self.final_report())
        self.assertIn("setup-boom", (self.rundir / "01/1/failure.log").read_text())

    def test_worker_retry_gets_setup_in_each_fresh_worktree(self):
        self.configure(self.record_setup + "echo ready > installed")
        path = self.bin / "worker.sh"
        path.write_text('test -f installed || exit 12\n' + path.read_text())
        code, out, err = self.go("--only", "02")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), ["02", "02"])
        self.assertEqual([Path(c).name for c in self.setup_calls()], ["integration", "02", "02-retry-1"])
        for attempt in ("1", "2"):
            self.assertIn("종료 코드: 0", (self.rundir / "02" / attempt / "setup.log").read_text())

    def test_integration_failure_does_not_launch_worker_verify_or_merge(self):
        self.configure(self.record_setup + 'echo integration-boom; exit 8')
        with mock.patch("gs.verify.run", side_effect=AssertionError("verify before setup")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "setup_failed")
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.lines("gh.log"), [])
        wt = self.rundir / "wt/integration"
        self.assertFalse(setup.marker(wt).exists())
        report = (wt / ".goldstack/work/demo/report.md").read_text()
        self.assertIn("integration-boom", report)
        self.assertIn("마무리: setup_failed", report)
        # 다음 go는 준비 실패를 재시도한다(성공 표시를 잘못 남기지 않는다).
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(len(self.setup_calls()), 2)

    def test_integration_setup_is_not_repeated_when_resuming_prepared_worktree(self):
        self.configure(self.record_setup + "echo ready > installed", 'test -f installed')
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        wt = self.rundir / "wt/integration"
        self.assertTrue(setup.marker(wt).exists())
        self.assertEqual([Path(c).name for c in self.setup_calls()], ["integration", "01"])
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual([Path(c).name for c in self.setup_calls()], ["integration", "01", "base"])
        self.assertEqual(self.calls(), ["01"])

    def test_integration_setup_failure_preserves_resumable_finish(self):
        self.configure('echo integration-boom; exit 8')
        self.assertEqual(self.go("--only", "01")[0], 1)
        wt = self.rundir / "wt/integration"
        head = sh(wt, "git", "rev-parse", "HEAD")
        for phase in (*finish.RESUME_PHASES, *finish.BASE_REPORT_PHASES):
            with self.subTest(phase=phase):
                st = state.load(self.rundir, "demo")
                previous = dict(phase=phase, outcome="기존 마무리", url="https://example.test/pr/1",
                                head=head, merge_sha=head, revert_sha=head,
                                report_result={"phase": "verified", "outcome": "검증 성공"})
                st.finish = previous.copy()
                state.save(self.rundir, st)
                with mock.patch("gs.verify.run", side_effect=AssertionError("verify before setup")), \
                        mock.patch("gs.finish.run", side_effect=AssertionError("finish before setup")):
                    code, out, err = self.go("--only", "01")
                self.assertEqual(code, 1, out + err)
                self.assertEqual(self.finish(), previous)
                self.assertFalse(setup.marker(wt).exists())
                report = (wt / ".goldstack/work/demo/report.md").read_text()
                self.assertIn("integration 준비 실패", report)
                self.assertIn("integration-boom", report)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.lines("gh.log"), [])

    def test_recreated_integration_setup_failure_resumes_pending_merge_next_go(self):
        blocked = self.bin / "setup-blocked"
        self.configure(f'test ! -f {blocked} || {{ echo integration-boom; exit 8; }}; echo ready > installed')
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        previous = self.finish()
        self.assertEqual(previous["phase"], "merge_pending")
        calls = self.lines("gh.log")
        sh(self.repo, "git", "worktree", "remove", "--force", str(self.rundir / "wt/integration"))
        blocked.touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish(), previous)
        self.assertEqual(self.lines("gh.log"), calls)

        blocked.unlink()
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(sum("pr create " in line for line in self.lines("gh.log")), 1)

    def test_base_setup_failure_never_reverts_and_next_go_rechecks_base_first(self):
        self.configure(self.record_setup + f'case "$PWD" in */gs-main-*/base) '
                       f'test -f {self.bin / "base-ready"} || {{ echo base-boom; exit 6; }};; esac; '
                       'echo ready > installed', 'test -f installed')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["outcome"]), ("base_unverified", "base 미검증(준비 실패)"))
        self.assertIsNone(f["main_ok"])
        self.assertNotIn("revert_sha", f)
        self.assertIn("file_01", self.remote_files())
        self.assertFalse((self.rundir / "finish/main-verify.log").exists())
        self.assertIn("base-boom", (self.rundir / "finish/setup.log").read_text())
        self.assertIn("base-boom", self.final_report())
        self.assertIn("마무리: base_unverified", self.final_report())
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])

        # worker·integration 검증을 반복하지 않고 미검증 base부터 회복한다.
        (self.bin / "base-ready").touch()
        events = []
        real_verify = verify.run
        real_setup = setup.run

        def prepare(cfg, wt, log):
            events.append(("setup", wt.name))
            return real_setup(cfg, wt, log)

        def validate(spec, wt, stream):
            events.append(("verify", wt.name))
            return real_verify(spec, wt, stream)

        with mock.patch("gs.setup.run", side_effect=prepare), mock.patch("gs.verify.run", side_effect=validate):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(events[:2], [("setup", "base"), ("verify", "base")])
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(sum("pr merge " in line for line in self.lines("gh.log")), 1)

    def test_empty_setup_keeps_old_execution_flow(self):
        with mock.patch("gs.setup.run", side_effect=AssertionError("empty setup should be skipped")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(list(self.rundir.glob("**/setup.log")), [])

    def test_unignored_setup_files_survive_resets_and_verify(self):
        self.configure("mkdir -p deps; echo ready > deps/ready; echo ready > installed",
                       "test -f deps/ready && test -f installed", ignored=False)
        (self.bin / "worker.sh").write_text('''\
test -f deps/ready && test -f installed || exit 9
echo "$GS_TICKET" >> "$(dirname "$0")/calls.log"
echo done > file_01
git add file_01 && git commit -qm worker
''')
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        wt = self.rundir / "wt/integration"
        # 준비 결과는 유지하지만 worker가 뒤에 만든 파일은 오염으로 판정하고 지운다.
        self.assertTrue(setup.is_clean(wt))
        extra = wt / "deps/unexpected"
        extra.touch()
        self.assertFalse(setup.is_clean(wt))
        setup.clean(wt, "-fd")
        self.assertFalse(extra.exists())
        self.assertTrue((wt / "deps/ready").exists())
        # 패턴 문자가 든 경로도 정확한 파일만 보존한다.
        special = wt / "deps/ready[1]?"
        special.touch()
        setup.remember(wt)
        similar = wt / "deps/ready1x"
        similar.touch()
        setup.clean(wt, "-fd")
        self.assertTrue(special.exists())
        self.assertFalse(similar.exists())
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")


if __name__ == "__main__":
    unittest.main()
