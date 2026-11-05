"""worker의 push 차단 환경에서도 임시 레포 시험은 독립적으로 돈다."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import worker
import support
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
            "test_go_execution.GoExecutionTest.test_worker_cannot_push",
            "test_go_execution.GoExecutionTest.test_worker_cannot_push_with_pushurl",
            "test_adapters.AgyGoAndCheckTest.test_go_runs_agy_through_adapter",
            "test_migrate.MigrateTest.test_moves_with_git_mv_creates_config_and_replaces_ignore_line",
            "test_check.CheckTest.test_ok",
            "test_config.InitTest.test_remote_head_branch_is_detected",
        ]
        cp = subprocess.run(["bash", "-c", worker.guard_exports(REPO) + '\nexec "$@"', "guarded-tests",
                             sys.executable, "-m", "unittest", *tests], cwd=REPO, env=env,
                            capture_output=True, text=True, timeout=120)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)


class GitShimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shim = self.root / "shim" / "git"
        self.real = self.root / "real" / "git"
        for path in (self.shim, self.real):
            path.parent.mkdir()
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.xcrun = self.root / "xbin"
        self.xcrun.mkdir()

    def path(self, with_xcrun=True):
        return os.pathsep.join([str(self.shim.parent)] + ([str(self.xcrun)] if with_xcrun else []))

    def fake_xcrun(self, body):
        script = self.xcrun / "xcrun"
        script.write_text("#!/bin/sh\n" + body)
        script.chmod(0o755)

    def test_shim_with_xcrun_gives_real_git_and_link_dir_has_only_git(self):
        self.fake_xcrun(f'echo "{self.real}"\n')
        real = support.real_git_for_shim(self.path(), shim=str(self.shim))
        self.assertEqual(real, str(self.real))
        link = support.link_real_git(real, parent=self.root)
        self.addCleanup(shutil.rmtree, link, ignore_errors=True)
        self.assertEqual(os.listdir(link), ["git"])
        self.assertEqual(os.path.realpath(os.path.join(link, "git")), os.path.realpath(self.real))

    def test_no_xcrun_changes_nothing(self):
        self.assertIsNone(support.real_git_for_shim(self.path(with_xcrun=False), shim=str(self.shim)))

    def test_failing_xcrun_changes_nothing(self):
        self.fake_xcrun("exit 1\n")
        self.assertIsNone(support.real_git_for_shim(self.path(), shim=str(self.shim)))

    def test_git_that_is_not_the_shim_changes_nothing(self):
        self.fake_xcrun(f'echo "{self.real}"\n')
        self.assertIsNone(support.real_git_for_shim(self.path(), shim=str(self.real)))

    def test_import_prepends_only_the_link_dir(self):
        link = support._shim_dir
        if link is None:
            self.skipTest("Apple git shim이 아니다")
        self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], link)
        self.assertEqual(os.listdir(link), ["git"])


if __name__ == "__main__":
    unittest.main()
