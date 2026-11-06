"""/feedback skill 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import unittest

from test_skills import SKILLS


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_feedback_documents_body_file(self):
        self.assertIn("--body-file <파일>", self.read("feedback"))


if __name__ == "__main__":
    unittest.main()
