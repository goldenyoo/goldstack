"""setup의 추적 변경은 복구하고 산출물은 검증 뒤 티켓 정리까지 기억한다."""
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

import support
import test_setup
from gs import setup, state
from gs.go import _drop_kept
from support import sh


class SetupRestoreTest(unittest.TestCase):
    setUp = test_setup.SetupCommandTest.setUp
    run_setup = test_setup.SetupCommandTest.run_setup

    def track(self, *names):
        for name in names:
            (self.wt / name).write_text("original\n")
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "tracked")

    def test_restores_modified_deleted_and_staged_paths_preserving_artifacts(self):
        names = ("lock.txt", "lock[1].txt", "한글 space.txt", "deleted.txt", "renamed.txt")
        self.track(*names)
        (self.wt / ".git/info/exclude").write_text("ignored/\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = self.run_setup("echo changed > lock.txt; echo changed > 'lock[1].txt'; "
                                    "echo changed > '한글 space.txt'; rm deleted.txt; "
                                    "git mv renamed.txt moved.txt; git add -u; "
                                    "mkdir ignored; echo ready > ignored/ready; "
                                    "echo ready > installed; git add installed")
        self.assertTrue(result.ok)
        for name in names:
            self.assertEqual((self.wt / name).read_text(), "original\n", name)
        self.assertEqual((self.wt / "installed").read_text(), "ready\n")
        self.assertEqual((self.wt / "ignored/ready").read_text(), "ready\n")
        self.assertTrue(all(line.startswith("?? ") for line in sh(self.wt, "git", "status", "--porcelain").splitlines()))
        self.assertIn(setup.WARNING, out.getvalue())
        for name in names:
            self.assertIn(name, self.log.read_text())
        for name in ("installed", "moved.txt"):
            self.assertNotIn(name, out.getvalue())
            self.assertNotIn(name, self.log.read_text())

    def test_staged_install_artifact_is_preserved_without_restore_warning(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = self.run_setup("echo ready > installed; git add installed")
        self.assertTrue(result.ok)
        self.assertEqual((self.wt / "installed").read_text(), "ready\n")
        self.assertIn("?? installed", sh(self.wt, "git", "status", "--porcelain"))
        self.assertNotIn(setup.WARNING, out.getvalue())
        self.assertNotIn(setup.WARNING, self.log.read_text())
        self.assertEqual(setup.warnings([self.log]), [])

    def test_failed_and_timed_out_setup_also_restore_tracked_files(self):
        self.track("lock.txt")
        for command, seconds in (("echo changed > lock.txt; exit 7", 60),
                                 ("echo changed > lock.txt; sleep 300", 0.1)):
            with self.subTest(command=command), contextlib.redirect_stdout(io.StringIO()):
                result = self.run_setup(command, seconds)
                self.assertFalse(result.ok)
                self.assertEqual((self.wt / "lock.txt").read_text(), "original\n")
                self.assertIn(setup.WARNING + "lock.txt", self.log.read_text())


class SetupTrackedTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    setUp, tearDown, go, calls, rundir = G.setUp, G.tearDown, G.go, G.calls, G.rundir
    integration, final_report, lines, remote_files = G.integration, G.final_report, G.lines, G.remote_files
    configure = test_setup.WorktreeSetupTest.configure

    def test_lock_changes_in_all_three_worktrees_do_not_fail_or_revert_or_enter_worker_commit(self):
        (self.repo / "lock.txt").write_text("original\n")
        self.configure("echo changed > lock.txt; echo ready > installed; echo secret > .env",
                       'test "$(cat lock.txt)" = original && test -f installed && test -f .env')
        worker = self.bin / "worker.sh"
        worker.write_text('test "$(cat lock.txt)" = original || exit 12\n' + worker.read_text())
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo")
        self.assertEqual(st.finish["phase"], "verified")
        self.assertNotIn("revert_sha", st.finish)
        self.assertEqual(st.tickets["01"].status, state.MERGED)
        self.assertEqual(self.calls(), ["01"])
        warning = setup.WARNING + "lock.txt"
        self.assertEqual(out.count(warning), 3)
        for log in ("integration/1/setup.log", "01/1/setup.log", "finish/setup.log"):
            self.assertIn(warning, (self.rundir / log).read_text())
        head = st.finish["head"]
        commit = sh(self.repo, "git", "log", "--format=%H", "--grep=^t01$", head)
        self.assertTrue(commit)
        self.assertEqual(sh(self.repo, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit), "file_01")
        report = self.final_report()
        row = next(line for line in report.splitlines() if line.startswith("| 01 |"))
        self.assertIn(warning, row)
        danger = report.split("## Merge Danger", 1)[1]
        self.assertIn("integration: " + warning, danger)
        self.assertIn("main: " + warning, danger)

    def install_unignored(self):
        self.configure("mkdir -p deps; echo ready > deps/ready; echo ready > installed",
                       "test -f deps/ready && test -f installed", ignored=False)
        (self.bin / "worker.sh").write_text('''\
test -f deps/ready && test -f installed || exit 12
echo "$GS_TICKET" >> "$(dirname "$0")/calls.log"
echo done > file_01
git add file_01 && git commit -qm 'worker 01'
''')

    def test_merged_ticket_with_setup_artifacts_is_removed(self):
        self.install_unignored()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("커밋 안 된 변경", out)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.kept_worktrees, [])
        self.assertFalse(Path(ts.worktree).exists())
        self.assertEqual(sh(self.repo, "git", "branch", "--list", ts.branch), "")

    def test_fix_worker_with_setup_artifacts_has_no_uncommitted_warning(self):
        self.install_unignored()
        worker = self.bin / "worker.sh"
        worker.write_text(worker.read_text().replace(
            "echo done > file_01", """\
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
  echo fixed > fixed_01; git add fixed_01; git commit -qm 'fix 01'; exit 0
fi
echo done > file_01"""))
        with support.GoTest.review_with(self, [
            {"severity": "high", "location": "file_01", "claim": "FIX: 값이 틀렸다", "evidence": "e"},
        ]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("수정 커밋 1개", out)
        self.assertNotIn("커밋 안 된 변경", out)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, state.MERGED)

    def test_drop_kept_only_ignores_remembered_artifacts_and_preserves_new_changes(self):
        self.install_unignored()
        runs = []
        with mock.patch("gs.go._cleanup_merged", side_effect=lambda r, tid: runs.append(r)):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        r = runs[-1]
        wt = Path(r.st.tickets["01"].worktree)
        self.assertTrue(setup.marker(wt).exists())
        self.assertTrue(setup.is_clean(wt))
        extra = wt / "deps/new-work"
        extra.write_text("unfinished")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(_drop_kept(r, "01", wt))
        self.assertEqual(extra.read_text(), "unfinished")
        self.assertTrue((wt / "deps/ready").exists())
        extra.unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(_drop_kept(r, "01", wt))
        self.assertFalse(wt.exists())


if __name__ == "__main__":
    unittest.main()
