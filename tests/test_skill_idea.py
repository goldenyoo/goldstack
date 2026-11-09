"""/idea skill 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import unittest

from test_skills import SKILLS, skill_frontmatter, steps


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_idea_skill(self):
        data, body = skill_frontmatter(self.read("idea"))
        self.assertEqual(data["name"], "idea")
        self.assertEqual(data["disable-model-invocation"], "true")
        self.assertIn("/idea <한 줄>", data["description"])
        self.assertIn("templates/idea.md", body)  # 형식 원본은 플러그인 안에 있다
        template = (SKILLS / "idea" / "templates" / "idea.md").read_text(encoding="utf-8")
        for key in ("date", "severity", "source", "status", "feature", "issues"):
            self.assertIn(f"{key}:", template)
        self.assertIn("근거에 재현 명령·입력이 있으면 줄이지 않고(`…` 없이) 원문을 코드로 남긴다", template)
        self.assertNotIn("ideas/README.md", body)  # 다른 레포에는 없다
        parts = steps(body)
        self.assertIn("gs backlog", parts[1])  # 비슷한 것을 먼저 찾는다
        self.assertIn("덧붙일까", parts[2])
        for key in ("date", "severity", "source", "status", "feature", "issues"):
            self.assertIn(f"`{key}`", parts[3])
        self.assertIn("한 줄로", parts[4])
        self.assertIn("커밋하지 않는다", parts[4])
        self.assertNotIn("git commit", body)


if __name__ == "__main__":
    unittest.main()
