"""병합·squash 본문의 gs-ticket 줄은 feature와 티켓 id 전체로 비교한다."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gs import finish, git, go
import support


class TicketTrailerTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            self.git("config", key, value)
        self.commit("init")
        self.git("branch", "base")
        self.r = SimpleNamespace(repo=self.repo, iwt=self.repo, name="f", base_ref="base", st=SimpleNamespace(finish={}))

    def git(self, *args):
        return support.sh(self.repo, "git", *args)

    def commit(self, message):
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def merge(self, message):
        self.git("checkout", "-qb", "ticket")
        self.commit("worker")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "ticket", "-m", message)
        self.git("branch", "-D", "ticket")
        return self.git("rev-parse", "HEAD")

    def test_merge_ticket_id_is_exact(self):
        self.merge("Merge 010\n\ngs-ticket: f/010")
        self.assertFalse(go._already_merged(self.r, "01"))
        self.assertTrue(go._already_merged(self.r, "010"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"010"})

    def test_prose_in_ordinary_commit_is_not_a_trailer(self):
        sha = self.commit("worker\n\n본문에서 gs-ticket: f/02 표시를 설명한다.")
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), set())
        self.assertFalse(finish._feature_merge(self.r, sha))

    def test_worker_trailer_is_ignored_after_merge(self):
        self.git("checkout", "-qb", "worker")
        worker = self.commit("worker\n\ngs-ticket: f/02")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "worker", "-m", "Merge 01\n\ngs-ticket: f/01")
        self.assertTrue(go._already_merged(self.r, "01"))
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"01"})
        self.assertFalse(finish._feature_merge(self.r, worker))
        self.r.st.finish.update(merge_head="HEAD", url="https://example.test/pull/1")
        self.r.feat = SimpleNamespace(tickets={})
        self.assertNotIn("gs-ticket: f/02", finish._squash_message(self.r)[1])

    def test_ordinary_standalone_trailer_is_ignored(self):
        self.commit("worker\n\ngs-ticket: f/02")
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), set())

    def test_subject_is_not_a_body_trailer(self):
        sha = self.commit("gs-ticket: f/02")
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertFalse(finish._feature_merge(self.r, sha))

    def test_indented_body_line_is_not_a_trailer(self):
        self.commit("worker\n\n    gs-ticket: f/02")
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), set())

    def test_feature_prefix_is_exact(self):
        sha = self.merge("Merge 01\n\ngs-ticket: f2/01")
        self.assertFalse(go._already_merged(self.r, "01"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), set())
        self.r.name = "f2"
        self.assertTrue(go._already_merged(self.r, "01"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"01"})
        # base의 PR 병합 판정도 같은 본문 파서를 쓴다.
        self.git("branch", "feature", sha)
        self.git("reset", "--hard", f"{sha}^1")
        self.git("merge", "-q", "--no-ff", "feature", "-m", "Merge feature")
        base_merge = self.git("rev-parse", "HEAD")
        self.assertTrue(finish._feature_merge(self.r, base_merge))
        self.r.name = "f"
        self.assertFalse(finish._feature_merge(self.r, base_merge))
        self.assertFalse(finish._feature_merge(self.r, sha))

    def test_squash_body_trailers_are_preserved(self):
        sha = self.commit("feature squash\n\n01 구현\n010 구현\n\ngs-ticket: f/01\ngs-ticket: f/010\t \n"
                          "gs-ticket: f2/02")
        self.git("branch", "-f", "base", sha)
        self.assertTrue(go._already_merged(self.r, "01"))
        self.assertTrue(go._already_merged(self.r, "010"))
        self.assertFalse(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"01", "010"})
        self.assertTrue(finish._feature_merge(self.r, sha))
        self.r.name = "other"
        self.assertFalse(finish._feature_merge(self.r, sha))

    def test_ticket_merge_remains_visible_after_base_merge(self):
        self.merge("Merge 01\n\ngs-ticket: f/01")
        self.git("branch", "feature")
        self.git("checkout", "-q", "base")
        self.git("merge", "-q", "--no-ff", "feature", "-m", "Merge feature PR")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--ff-only", "base")
        self.assertTrue(go._already_merged(self.r, "01"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"01"})

    def test_squash_imported_from_base_second_parent(self):
        self.commit("integration")
        self.git("checkout", "-q", "base")
        self.commit("feature squash\n\ngs-ticket: f/02")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "base", "-m", "Merge base")
        self.assertTrue(go._already_merged(self.r, "02"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), {"02"})

    def test_feature_metacharacters_are_literal(self):
        self.commit("squash\n\ngs-ticket: fX/01")
        self.r.name = "f."
        self.assertFalse(go._already_merged(self.r, "01"))
        self.assertEqual(finish._trailers(self.r, "HEAD"), set())
        sha = self.commit("squash\n\ngs-ticket: f./02")
        self.git("branch", "-f", "base", sha)
        self.assertTrue(go._already_merged(self.r, "02"))
        self.assertTrue(finish._feature_merge(self.r, sha))

    def test_new_merge_scan_ignores_squash_and_other_feature(self):
        anchor = self.git("rev-parse", "HEAD")
        self.commit("squash\n\ngs-ticket: f/01")
        self.merge("Merge other\n\ngs-ticket: f2/02")
        self.assertEqual(git.ticket_trailers(self.repo, "f", f"{anchor}..HEAD", merges_only=True), set())
        self.merge("Merge 010\n\ngs-ticket: f/010")
        self.assertEqual(git.ticket_trailers(self.repo, "f", f"{anchor}..HEAD", merges_only=True), {"010"})
