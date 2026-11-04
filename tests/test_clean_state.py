"""수동 정리가 state의 경로도 비우며 완료한 feature를 다시 만들지 않는지 확인한다."""
import unittest
from unittest import mock

import test_clean
import test_go
from gs import git, state


class CleanStateTest(unittest.TestCase):
    BASE, REMOTE = "trunk", "upstream"
    G = test_go.GoTest
    setUp, tearDown, go, rundir, parallel = G.setUp, G.tearDown, G.go, G.rundir, G.parallel
    clean = test_clean.CleanTest.clean
    prepare = test_clean.CleanTest.prepare
    assert_integration_removed = test_clean.CleanTest.assert_integration_removed

    def clean_kept_feature(self, phase):
        if phase == "reverted":
            self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        (self.bin / "worker.sh").write_text(test_go.FAKE_WORKER + '\necho dirty > pending.txt\n')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0 if phase == "verified" else 1, out + err)
        st = state.load(self.rundir, "demo")
        self.assertEqual(st.finish["phase"], phase)
        self.assertEqual(st.tickets["01"].kept_worktrees, [str(self.rundir / "wt/01")])
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        cleaned = state.load(self.rundir, "demo")
        self.assertEqual(cleaned.tickets["01"].kept_worktrees, [])
        self.assertEqual(cleaned.tickets["01"].worktree, "")
        self.assertEqual(cleaned.finish, st.finish)
        self.assert_integration_removed()
        real_run = git.run

        def no_recreation(repo, *args, **kw):
            self.assertNotEqual(args[:2], ("worktree", "add"))
            self.assertFalse(args[:2] == ("push", self.REMOTE) and "--delete" not in args)
            return real_run(repo, *args, **kw)

        with mock.patch.object(git, "run", side_effect=no_recreation):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0 if phase == "verified" else 1, out + err)
        self.assertIn("이미 끝남", out)
        self.assert_integration_removed()

    def test_clean_kept_verified_feature_stays_finished(self):
        self.clean_kept_feature("verified")

    def test_clean_kept_reverted_feature_stays_finished(self):
        self.clean_kept_feature("reverted")

    def test_clean_updates_all_tickets_and_path_lists_but_keeps_evidence(self):
        self.prepare()
        st = state.load(self.rundir, "demo")
        outside = self.repo / "other-worktree"
        outside.mkdir()
        gone = self.rundir / "wt/already-gone"
        for tid, path in (("01", self.rundir / "wt/01"), ("outside-scope", self.rundir / "wt/01-retry-2")):
            ts = st.ticket(tid)
            ts.worktree = str(path)
            ts.kept_worktrees = [str(path), str(gone), str(outside)]
            ts.failed_worktrees = [str(path), str(gone), str(outside)]
            ts.reason, ts.log = "preserved failure", "preserved.log"
        state.save(self.rundir, st)
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        for ts in state.load(self.rundir, "demo").tickets.values():
            self.assertEqual(ts.worktree, "")
            self.assertEqual(ts.kept_worktrees, [str(outside)])
            self.assertEqual(ts.failed_worktrees, [str(outside)])
            self.assertEqual((ts.reason, ts.log), ("preserved failure", "preserved.log"))
        self.assertTrue(outside.exists())

    def test_partial_cleanup_keeps_failed_path_in_state(self):
        self.prepare()
        st = state.load(self.rundir, "demo")
        failed, removed = self.rundir / "wt/01", self.rundir / "wt/01-retry-2"
        ts = st.ticket("01")
        ts.worktree = str(failed)
        ts.kept_worktrees = ts.failed_worktrees = [str(failed), str(removed)]
        state.save(self.rundir, st)
        real_remove = git.remove_worktree

        def fail(repo, path):
            if path == failed:
                raise git.GitError("worktree removal denied")
            return real_remove(repo, path)

        with mock.patch.object(git, "remove_worktree", side_effect=fail):
            code, out, err = self.clean()
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.worktree, str(failed))
        self.assertEqual(ts.kept_worktrees, [str(failed)])
        self.assertEqual(ts.failed_worktrees, [str(failed)])
        self.assertTrue(failed.exists())
        self.assertFalse(removed.exists())
        self.assertEqual(self.clean()[0], 0)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [])

    def test_cleanup_unlinks_symlink_without_pruning_target_record(self):
        state.save(self.rundir, state.State(feature="demo", finish={"phase": "verified"}))
        outside = self.repo / "outside"
        outside.mkdir()
        link = self.rundir / "wt/link"
        link.parent.mkdir()
        link.symlink_to(outside, target_is_directory=True)
        st = state.load(self.rundir, "demo")
        st.ticket("01").kept_worktrees = [str(link), str(outside)]
        state.save(self.rundir, st)
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [str(outside)])
        self.assertTrue(outside.is_dir())


if __name__ == "__main__":
    unittest.main()
