"""/adopt skill 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import unittest

from test_skills import SKILLS


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_adopt_asks_feedback_once(self):
        body = self.read("adopt")
        for text in ("[feedback]", "`mode`", "`detail`", "`auto`", "`draft`", "`off`", "`errors`", "`minimal`",
                     "다시 묻지 않는다", "gs feedback send", "사람이 고른 것이 아니니 묻는다", "개인 프로젝트는 `auto` + `errors`", "회사 레포는 `off` 또는 `minimal`"):
            self.assertIn(text, body)


if __name__ == "__main__":
    unittest.main()
