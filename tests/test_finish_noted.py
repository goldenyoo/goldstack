"""goldstack-v19 03: `finish._noted`는 글자가 아니라 이번 `finish.run`이 처리한 예외로 판단한다."""
import unittest
from types import SimpleNamespace
from unittest import mock

from gs import feedback, finish, git


def fake_run(**finish_fields):
    st = SimpleNamespace(finish=dict(finish_fields), finish_errors=[])
    return SimpleNamespace(st=st, save=lambda: None)


class NotedTest(unittest.TestCase):
    def test_same_text_left_by_an_earlier_run_is_noted_again(self):
        r = fake_run(phase="preparing", outcome="integration 검증 중", error="gh pr create: broken")
        r.st.finish_errors = ["gh pr create: broken"]
        with mock.patch("gs.finish._run", side_effect=git.GitError("gh pr create: broken")):
            with self.assertRaises(git.GitError):
                finish.run(r)
        self.assertEqual(r.st.finish["outcome"], f"{feedback.FINISH_FAILED}: gh pr create: broken")
        self.assertEqual(r.st.finish["error"], "gh pr create: broken")
        self.assertEqual(r.st.finish_errors, ["gh pr create: broken"])  # 중복 없음

    def test_a_later_failure_does_not_replace_the_cause(self):
        r = fake_run(phase="preparing", outcome="integration 검증 중")

        def run(r_, cleanup):
            try:
                raise git.GitError("cause")
            except git.GitError as e:
                finish._note_failure(r_, e)
                try:
                    raise git.GitError("report broke")  # 보고서 갱신 실패(원인의 context를 가진다)
                except git.GitError as later:
                    raise later from None
        with mock.patch("gs.finish._run", side_effect=run):
            with self.assertRaises(git.GitError):
                finish.run(r)
        self.assertEqual(r.st.finish["error"], "cause")
        self.assertEqual(r.st.finish_errors, ["cause"])

    def test_noted_follows_the_context_chain(self):
        r = fake_run()
        try:
            try:
                raise git.GitError("a")
            except git.GitError as e:
                finish._note_failure(r, e)
                raise git.GitError("b") from e
        except git.GitError as wrapped:
            self.assertTrue(finish._noted(r, wrapped))
        self.assertFalse(finish._noted(r, git.GitError("a")))  # 글자가 같아도 처리하지 않은 예외다


if __name__ == "__main__":
    unittest.main()
