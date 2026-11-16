"""공용 임시 git 환경의 설정을 확인한다."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import isolate_git_env


class SupportGitTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }

    def git(self, *args, cwd=None, **env):
        return subprocess.run(["git", *args], cwd=cwd or self.root, env={**self.env, **env},
                              check=True, capture_output=True, text=True)

    def test_shared_environment_disables_auto_maintenance_during_local_bare_push(self):
        self.assertEqual(self.git("config", "--get", "maintenance.auto").stdout.strip(), "false")

        bare = self.root / "remote.git"
        repo = self.root / "repo"
        self.git("init", "--bare", "-q", "-b", "main", str(bare))
        repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=repo)
        (repo / "file.txt").write_text("test\n")
        self.git("add", "file.txt", cwd=repo)
        self.git("commit", "-q", "-m", "init", cwd=repo)
        self.git("remote", "add", "origin", str(bare), cwd=repo)

        pushed = self.git("push", "origin", "main", cwd=repo, GIT_TRACE="1")
        trace = pushed.stderr.lower()
        self.assertNotIn("maintenance run", trace)


if __name__ == "__main__":
    unittest.main()
