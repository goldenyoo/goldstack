"""worker의 push 차단 환경에서도 임시 레포 시험은 독립적으로 돈다."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from gs import worker
from support import isolate_git_env


REPO = Path(__file__).resolve().parents[1]


class TestEnvironmentTest(unittest.TestCase):
    def test_isolation_removes_guard_variables_and_restores_parent(self):
        guarded = {
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.name", "GIT_CONFIG_VALUE_0": "worker",
            "GIT_CONFIG_KEY_leftover": "unused", "GIT_CONFIG_VALUE_leftover": "unused",
            "GH_TOKEN": worker.GH_BLOCKED, "GIT_CONFIG_NOSYSTEM": "1", "GS_TEST_KEEP": "keep",
        }
        with mock.patch.dict(os.environ, guarded):
            before = dict(os.environ)
            fixture = unittest.TestCase()
            try:
                isolate_git_env(fixture)
                for name in guarded:
                    if name not in ("GIT_CONFIG_NOSYSTEM", "GS_TEST_KEEP"):
                        self.assertNotIn(name, os.environ)
                self.assertEqual(os.environ["GIT_CONFIG_NOSYSTEM"], "1")
                self.assertEqual(os.environ["GS_TEST_KEEP"], "keep")
            finally:
                fixture.doCleanups()
            self.assertEqual(dict(os.environ), before)

    def test_representative_tests_under_worker_guard_exports(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(REPO / "src"), str(REPO / "tests"),
                                            env.get("PYTHONPATH", "")])
        tests = [
            "test_go.GoTest.test_worker_cannot_push",
            "test_go.GoTest.test_worker_cannot_push_with_pushurl",
            "test_adapters.AgyGoAndCheckTest.test_go_runs_agy_through_adapter",
            "test_migrate.MigrateTest.test_moves_with_git_mv_creates_config_and_replaces_ignore_line",
            "test_check.CheckTest.test_ok",
            "test_config.InitTest.test_remote_head_branch_is_detected",
        ]
        cp = subprocess.run(["bash", "-c", worker.guard_exports(REPO) + '\nexec "$@"', "guarded-tests",
                             sys.executable, "-m", "unittest", *tests], cwd=REPO, env=env,
                            capture_output=True, text=True, timeout=120)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)


if __name__ == "__main__":
    unittest.main()
