"""상태 값은 네 번 묻던 구현과 같고, git 프로세스 수는 줄어야 한다."""
from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from gs import git, go, setup


def old_tree_state(wt):
    def get(*args):
        cp = git.run(wt, *args, check=False)
        return cp.stdout.strip() if cp.returncode == 0 else ""
    return (get("rev-parse", "-q", "--verify", "HEAD"), get("symbolic-ref", "-q", "HEAD"),
            get("rev-parse", "-q", "--verify", "MERGE_HEAD"), get("write-tree"))


class GitQueriesTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.wt = self.root / "main"
        self.wt.mkdir()
        git.run(self.wt, "init", "-q", "-b", "main")
        git.run(self.wt, "config", "user.name", "test")
        git.run(self.wt, "config", "user.email", "test@example.test")

    def commit(self, text="base"):
        (self.wt / "file").write_text(text)
        git.run(self.wt, "add", "file")
        git.run(self.wt, "commit", "-qm", text)

    def linked(self):
        self.commit()
        wt = self.root / "linked worktree"
        git.run(self.wt, "worktree", "add", "-q", "-b", "linked", str(wt))
        return wt

    def assert_marker(self, wt):
        expected = Path(git.out(wt, "rev-parse", "--absolute-git-dir")) / "gs-setup-done"
        with mock.patch.object(git, "run", wraps=git.run) as run:
            self.assertEqual(setup.marker(wt), expected)
        self.assertEqual(run.call_count, 0)

    def test_marker_without_git(self):
        self.assert_marker(self.wt)
        linked = self.linked()
        self.assert_marker(linked)
        gitdir = Path(git.out(linked, "rev-parse", "--absolute-git-dir"))
        (linked / ".git").write_text(f"gitdir: {os.path.relpath(gitdir, linked)}\n")
        self.assert_marker(linked)
        with contextlib.chdir(self.root):
            self.assert_marker(Path("main"))
            self.assert_marker(Path("linked worktree"))

    def test_marker_falls_back_for_unreadable_git_file(self):
        linked = self.linked()
        expected = Path(git.out(linked, "rev-parse", "--absolute-git-dir")) / "gs-setup-done"
        for error in (PermissionError("denied"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(Path, "read_text", side_effect=error), \
                    mock.patch.object(git, "run", wraps=git.run) as run:
                self.assertEqual(setup.marker(linked), expected)
                self.assertEqual(run.call_count, 1)

    def test_marker_falls_back_for_missing_or_malformed_git_file(self):
        linked = self.linked()
        for text in ("", "gitdir:", "gitdir: \n", "not gitdir: /tmp/foo\n",
                     "gitdir: /tmp/foo\nextra\n", "gitdir: /tmp/foo\0\n"):
            (linked / ".git").write_text(text)
            with self.subTest(text=text), mock.patch.object(git, "run", wraps=git.run) as run:
                with self.assertRaises(git.GitError):
                    setup.marker(linked)
                self.assertEqual(run.call_count, 1)
        (linked / ".git").unlink()
        with mock.patch.object(git, "run", wraps=git.run) as run:
            with self.assertRaises(git.GitError):
                setup.marker(linked)
            self.assertEqual(run.call_count, 1)

    def assert_tree_state(self, wt=None):
        wt = wt or self.wt
        expected = old_tree_state(wt)
        with mock.patch.object(git, "run", wraps=git.run) as run:
            self.assertEqual(go._tree_state(wt), expected)
        self.assertLessEqual(run.call_count, 2)
        return expected

    def test_tree_state_on_branch(self):
        self.commit()
        (self.wt / "file").write_text("staged")
        git.run(self.wt, "add", "file")
        head, branch, merge, tree = self.assert_tree_state()
        self.assertTrue(head)
        self.assertEqual(branch, "refs/heads/main")
        self.assertEqual(merge, "")
        self.assertNotEqual(tree, git.out(self.wt, "rev-parse", "HEAD^{tree}"))

    def test_tree_state_detached(self):
        self.commit()
        git.run(self.wt, "checkout", "--detach", "-q")
        head, branch, merge, tree = self.assert_tree_state()
        self.assertTrue(head and tree)
        self.assertEqual((branch, merge), ("", ""))

    def test_tree_state_conflict(self):
        self.commit()
        git.run(self.wt, "checkout", "-qb", "other")
        self.commit("other")
        other = git.out(self.wt, "rev-parse", "HEAD")
        git.run(self.wt, "checkout", "-q", "main")
        self.commit("main")
        self.assertEqual(git.run(self.wt, "merge", "other", check=False).returncode, 1)
        head, branch, merge, tree = self.assert_tree_state()
        self.assertTrue(head)
        self.assertEqual(branch, "refs/heads/main")
        self.assertEqual(merge, other)
        self.assertEqual(tree, "")

    def test_tree_state_unborn(self):
        head, branch, merge, tree = self.assert_tree_state()
        self.assertEqual((head, branch, merge), ("", "refs/heads/main", ""))
        self.assertTrue(tree)

    def test_tree_state_unborn_ref_path_collision(self):
        self.commit()
        git.run(self.wt, "branch", "topic/child")
        for branch in ("refs/heads/topic", "refs/heads/main/child"):
            with self.subTest(branch=branch):
                git.run(self.wt, "symbolic-ref", "HEAD", branch)
                head, actual_branch, merge, tree = self.assert_tree_state()
                self.assertEqual((head, actual_branch, merge), ("", branch, ""))
                self.assertTrue(tree)

    def reftable(self):
        self.wt = self.root / "reftable"
        self.wt.mkdir()
        result = git.run(self.wt, "init", "-q", "-b", "main", "--ref-format=reftable", check=False)
        if result.returncode and "unknown option" in result.stderr and "ref-format" in result.stderr:
            self.skipTest("이 Git은 reftable을 지원하지 않는다")
        self.assertEqual(result.returncode, 0, result.stderr)
        git.run(self.wt, "config", "user.name", "test")
        git.run(self.wt, "config", "user.email", "test@example.test")

    def test_tree_state_reftable(self):
        self.reftable()
        self.test_tree_state_on_branch()
        linked = self.root / "reftable linked"
        git.run(self.wt, "worktree", "add", "-q", "-b", "linked", str(linked))
        self.assertEqual(self.assert_tree_state(linked)[1], "refs/heads/linked")
        git.run(self.wt, "update-ref", "refs/worktree/topic", "HEAD")
        git.run(self.wt, "symbolic-ref", "HEAD", "refs/worktree/topic")
        self.assertEqual(self.assert_tree_state()[1], "refs/worktree/topic")
        git.run(self.wt, "checkout", "--detach", "-q")
        self.assertEqual(self.assert_tree_state()[1], "")

    def test_tree_state_reftable_conflict(self):
        self.reftable()
        self.test_tree_state_conflict()

    def test_tree_state_reftable_unborn(self):
        self.reftable()
        for staged in (False, True):
            with self.subTest(staged=staged):
                if staged:
                    (self.wt / "file").write_text("staged")
                    git.run(self.wt, "add", "file")
                expected = old_tree_state(self.wt)
                with mock.patch.object(git, "run", wraps=git.run) as run:
                    self.assertEqual(go._tree_state(self.wt), expected)
                self.assertLessEqual(run.call_count, 3)
                self.assertEqual(expected[:3], ("", "refs/heads/main", ""))

    def test_tree_state_reftable_symbolic_ref_failure(self):
        self.reftable()
        head, _, merge, tree = old_tree_state(self.wt)
        original = git.run

        def run(wt, *args, **kwargs):
            if args[:1] == ("symbolic-ref",):
                return subprocess.CompletedProcess(args, 1, "", "unreadable")
            return original(wt, *args, **kwargs)

        with mock.patch.object(git, "run", side_effect=run) as calls:
            self.assertEqual(go._tree_state(self.wt), (head, "", merge, tree))
        self.assertLessEqual(calls.call_count, 3)

    def test_tree_state_merge_path_unreadable(self):
        self.test_tree_state_conflict()
        exists = Path.exists

        def check(path):
            if path.name == "MERGE_HEAD":
                raise PermissionError("denied")
            return exists(path)

        with mock.patch.object(Path, "exists", check):
            self.assert_tree_state()

    def test_tree_state_linked_and_packed_refs(self):
        linked = self.linked()
        git.run(self.wt, "pack-refs", "--all")
        self.assert_tree_state(linked)

    def test_tree_state_symbolic_chain(self):
        git.run(self.wt, "symbolic-ref", "HEAD", "refs/heads/alias")
        git.run(self.wt, "symbolic-ref", "refs/heads/alias", "refs/heads/main")
        self.assertEqual(self.assert_tree_state()[1], "refs/heads/main")
        self.commit()
        self.assertEqual(self.assert_tree_state()[1], "refs/heads/main")
        git.run(self.wt, "symbolic-ref", "refs/heads/main", "refs/heads/alias")
        self.assert_tree_state()

    def test_tree_state_worktree_local_symbolic_ref(self):
        linked = self.linked()
        git.run(linked, "update-ref", "refs/worktree/topic", "HEAD")
        git.run(linked, "symbolic-ref", "HEAD", "refs/worktree/topic")
        self.assertEqual(self.assert_tree_state(linked)[1], "refs/worktree/topic")

    def test_tree_state_outside_repo(self):
        self.assertEqual(self.assert_tree_state(self.root), ("", "", "", ""))

    def test_tree_state_unreadable_branch_fallback(self):
        self.commit()
        head, _, merge, tree = old_tree_state(self.wt)
        for error in (PermissionError("denied"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(Path, "read_text", side_effect=error), \
                    mock.patch.object(git, "run", wraps=git.run) as run:
                branch = "refs/heads/main" if isinstance(error, OSError) else ""
                self.assertEqual(go._tree_state(self.wt), (head, branch, merge, tree))
                self.assertLessEqual(run.call_count, 2)
        git.run(self.wt, "checkout", "--detach", "-q")
        with mock.patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            self.assert_tree_state()


if __name__ == "__main__":
    unittest.main()
