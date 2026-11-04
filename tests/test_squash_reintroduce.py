"""squash가 되살림 기록을 보존해야 새 clone에서도 같은 revert를 다시 적용하지 않는다."""
import unittest

import test_squash
from test_go import sh


class SquashReintroduceTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = test_squash.SquashTest.G
    S = test_squash.SquashTest
    setUp, tearDown = S.setUp, S.tearDown
    go, calls, add_ticket = S.go, S.calls, S.add_ticket
    rundir, finish, lines = S.rundir, S.finish, S.lines
    someone, remote_files = S.someone, S.remote_files

    def test_restored_tickets_and_revert_marker_survive_fresh_clone(self):
        self.assertEqual(self.go("--only", "01,04")[0], 0)
        merge = self.finish()["merge_sha"]
        revert = self.someone(f"! git revert --no-edit {merge}",
                              f"git checkout HEAD -- {test_squash.REPORT}", "git revert --continue --no-edit")
        self.add_ticket("09")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        body = sh(self.remote, "git", "log", "-1", "--format=%B", self.finish()["merge_sha"])
        for tid in ("01", "04", "09"):
            self.assertIn(f"{tid} t{tid}\n", body)
            self.assertIn(f"gs-ticket: demo/{tid}", body)
        self.assertIn(f"This reverts commit {revert}.", body)

        # state와 integration 이력이 전혀 없는 새 clone에서 base 메시지만으로 판단한다.
        clone = self.repo.parent / "fresh"
        sh(self.repo.parent, "git", "clone", "-q", str(self.remote), str(clone))
        self.repo = clone
        url = "https://github.com/test/origin.git"
        sh(clone, "git", "remote", "set-url", "origin", url)
        sh(clone, "git", "config", f"url.{self.remote}.insteadOf", url)
        self.assertFalse(self.rundir.exists())
        self.add_ticket("10")
        code, out, err = self.go("--only", "01,04,09,10")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertNotIn("reintroduced", self.finish())
        self.assertEqual(self.calls(), ["01", "04", "09", "10"])
        self.assertTrue({"file_01", "file_04", "file_09", "file_10"} <= set(self.remote_files()))
        body = sh(self.remote, "git", "log", "-1", "--format=%B", self.finish()["merge_sha"])
        self.assertEqual(body, f"{test_squash.TITLE}\n\n10 t10\n\ngs-ticket: demo/10")
