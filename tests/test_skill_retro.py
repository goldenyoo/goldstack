"""/retro skill 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import unittest

from test_skills import SKILLS, skill_frontmatter, steps


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_retro_reads_feature_run(self):
        data, body = skill_frontmatter(self.read("retro"))
        self.assertIn("feature", data["description"])
        for source in ("report.md", "run/state.json", "worker.log", "`review`", "`fix`", "grill 기록",
                       ".goldstack/work/*/report.md", "~/.claude/usage-data/report-*.html"):
            self.assertIn(source, body)
        self.assertIn("`run/`이 없으면", body)
        self.assertIn("`[반복]`", body)
        self.assertIn("idea/SKILL.md", body)  # 고른 후보는 /idea 형식으로
        self.assertTrue((SKILLS / "idea" / "SKILL.md").is_file())

    def test_retro_scopes_write_ban_and_narrows_style_read(self):
        _, body = skill_frontmatter(self.read("retro"))
        self.assertLessEqual(len(body.split()), 850)
        intro = body.partition("## 단계")[0]
        for text in ("개선 대상(코드·문서·설정)과 아이디어 파일을 바꾸지 않는다", "`run/retro-log.md`는 만들어도 된다"):
            self.assertIn(text, intro)
        self.assertNotIn("아무 파일도", body)
        self.assertEqual(body.count("writing-for-agents/SKILL.md"), 1)
        self.assertIn("문서(skill, `CLAUDE.md`, docs)를 고치는 후보가 있을 때만", body)
        step5 = steps(self.read("go"))[5]
        self.assertIn("개선 대상과 아이디어 파일은 쓰지 않게", step5)
        self.assertIn("`run/retro-log.md`는 만들어도 된다", step5)
        self.assertIn("`retro/SKILL.md` 4단계대로", step5)  # retro의 고른 후보 다루기 단계 번호
        self.assertTrue(body.partition("\n4. ")[2].startswith("고른 후보를 다룬다"))

    def test_retro_agy_call_has_no_permission_flag(self):
        body = self.read("retro")
        self.assertIn('agy -p "<프롬프트>" --sandbox --disable-slash-commands --model "$model"', body)
        self.assertNotIn("--dangerously-skip-permissions", body)
        self.assertNotIn("읽기 전용으로 만든다", body)
        self.assertIn("자동 거부", body)
        self.assertIn("`no output produced`", body)
        guide = (SKILLS.parent / "docs" / "guide.md").read_text(encoding="utf-8")
        self.assertNotIn("--dangerously-skip-permissions --disable", guide)
        self.assertIn("`no output produced`", guide)

    def test_retro_can_file_issue(self):
        body = self.read("retro")
        for text in ("issue로 올리기", 'gs feedback --body-file', "증상·근거·제안", "초안 전체를 보이고 확인받는다", "레포 이름·파일 이름을 넣지 않는다"):
            self.assertIn(text, body)


if __name__ == "__main__":
    unittest.main()
