"""codex sandbox가 여는 경로로 브랜치 ref를 다시 만들 수 있는가(v8 01).

실제 sandbox는 못 쓰므로 규칙을 옮겨 모델링한다: 경로는 열린 디렉터리 자신이거나 그 아래일 때만 만들 수 있다.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

import support
from gs import adapters, config

MODELS = config.ModelsConfig("judge-test", "review-test", "agy-test", "")
BRANCH = "gs/feat/01"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def creatable(path: Path, opened: list[Path]) -> bool:
    """path가 없을 때 sandbox 안에서 (부모 디렉터리부터) 만들 수 있나: 가장 위의 빠진 조상이 열린 곳 아래여야 한다."""
    top = path
    while not top.parent.exists():
        top = top.parent
    return any(top == d or d in top.parents for d in opened)


class CodexRefsTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.repo, self.wt = root / "repo", root / "wt"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i")
        git(self.repo, "branch", BRANCH)
        git(self.repo, "branch", "gs/feat/02")
        git(self.repo, "worktree", "add", "-q", str(self.wt), BRANCH)
        self.common = self.repo / ".git"
        self.opened = adapters.Codex(MODELS).writable_dirs(self.wt)  # 시작 때 gs가 하는 일

    def ref_paths(self):
        return [self.common / "refs/heads" / BRANCH, self.common / "logs/refs/heads" / BRANCH]

    def lose_ref_dirs(self):
        git(self.repo, "pack-refs", "--all", "--prune")  # loose ref를 지우면 빈 디렉터리도 지운다
        git(self.repo, "branch", "-D", "gs/feat/02")

    def test_pack_refs_removes_the_ref_directory(self):
        """재현: 옛 범위(`refs/heads/gs/feat`)만 열면 pack 뒤 ref를 만들 수 없다."""
        self.lose_ref_dirs()
        self.assertFalse((self.common / "refs/heads/gs").exists())
        narrow = [self.common / "refs/heads/gs/feat", self.common / "logs/refs/heads/gs/feat"]
        self.assertFalse(creatable(self.ref_paths()[0], narrow))

    def test_opened_dirs_can_recreate_ref_after_pack(self):
        self.lose_ref_dirs()
        for p in self.ref_paths():
            if p.parent.exists():
                continue
            self.assertTrue(creatable(p, self.opened), p)

    def test_opens_gs_root_for_refs_and_logs(self):
        self.assertIn(self.common / "refs/heads/gs", self.opened)
        self.assertIn(self.common / "logs/refs/heads/gs", self.opened)

    def test_commit_works_after_pack(self):
        """git 쪽 확인: 열린 범위 안의 디렉터리만 만들어 두면 커밋이 된다."""
        self.lose_ref_dirs()
        for d in self.opened:
            d.mkdir(parents=True, exist_ok=True)
        (self.wt / "f").write_text("x")
        git(self.wt, "add", "f")
        git(self.wt, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c")
        self.assertEqual(git(self.repo, "rev-parse", "--verify", BRANCH), git(self.wt, "rev-parse", "HEAD"))

    def test_command_still_has_no_network(self):
        inp = adapters.WorkerInput(self.wt / "b.md", self.wt, self.wt / "l")
        cmd = adapters.Codex(MODELS).command(inp)
        self.assertIn("network_access=false", cmd)
        self.assertIn(str(self.common / "refs/heads/gs"), cmd)


if __name__ == "__main__":
    unittest.main()
