"""/go skill 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import unittest

from test_skills import SKILLS, steps


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_go_retro_step_and_overnight_skips_it(self):
        go = self.read("go")
        step5 = steps(go)[5]
        for text in ("retro/SKILL.md", "subagent", "후보만", "파일은 쓰지 않게", "번호 붙여", "고른 것만",
                     "고르지 않으면 아무것도 쓰지 않는다", "다시 부르지 않고", "/retro <feature>", "결과와 종료는 그대로"):
            self.assertIn(text, step5)
        self.assertIn("중간은 실행 중", go)
        overnight = self.read("overnight")
        self.assertIn("5단계(회고)는 따르지 않는다", overnight)
        self.assertIn("회고: /retro a, /retro b", overnight)
        self.assertIn("`/retro <feature>` 권고", overnight)

    def test_go_uses_f_and_reads_this_runs_report(self):
        go = self.read("go")
        self.assertNotIn("$ARGUMENTS", go.partition("\n1. ")[2])  # 단계 안은 `<f>`만 쓴다
        self.assertNotIn("매번", go)
        step4 = steps(go)[4]
        integration = step4.index("git show gs/<f>/integration:")
        fetched = step4.index("git fetch <remote> <base>")
        self.assertLess(integration, fetched)
        self.assertLess(fetched, step4.index("git show <remote>/<base>:"))
        self.assertIn("작업 트리의 파일은 읽지 않는다", step4)
        self.assertIn("옛 판", step4)  # 재실행 때 옛 보고서를 막는다
        self.assertIn("`■ integration 준비 실패`가 있으면", step4)  # 준비 실패는 보고서를 커밋하지 않아 integration 판이 옛 판이다
        self.assertEqual(sorted(steps(go)), [1, 2, 3, 4, 5])

    def test_go_summary_shows_remaining_high_line(self):
        step4 = steps(self.read("go"))[4]
        self.assertIn("`■ 남은 high …`", step4)
        self.assertIn("종료 코드는 그대로", step4)


if __name__ == "__main__":
    unittest.main()
