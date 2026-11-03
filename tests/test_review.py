"""리뷰 형식 단위 시험: reviewer 답 읽기, 판단 모델 답 적용, 계열 검사."""
import unittest

from gs import review


class ParseTest(unittest.TestCase):
    def test_findings_from_fenced_answer(self):
        text = '설명\n```json\n{"findings": [{"severity": "HIGH", "location": "a.py:3", "claim": "c", "evidence": "e"}]}\n```\n'
        [f] = review.parse_findings(text)
        self.assertEqual((f.id, f.severity, f.location, f.claim, f.evidence, f.action), (1, "high", "a.py:3", "c", "e",
                                                                                          "report"))
        self.assertEqual(review.parse_findings('{"findings": []}'), [])

    def test_fixed_format_is_enforced(self):
        bad = ['nothing', '{"findings": {}}', '{"findings": [1]}',
               '{"findings": [{"severity": "high", "location": "a", "claim": "c"}]}',
               '{"findings": [{"severity": "nit", "location": "a", "claim": "c", "evidence": ""}]}',
               '{"findings": [{"severity": "low", "location": "a", "claim": " ", "evidence": ""}]}']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(review.ReviewError):
                review.parse_findings(text)

    def test_decisions(self):
        fs = [review.Finding(i, "high", "a", "c", ev) for i, ev in [(1, "e"), (2, ""), (3, "e"), (4, "e")]]
        review.apply_decisions('{"decisions": [{"id": 1, "action": "fix", "why": "확인함"},'
                               '{"id": 2, "action": "fix"}, {"id": 3, "action": "rewrite"}]}', fs)
        self.assertEqual([f.action for f in fs], ["fix", "report", "report", "report"])
        self.assertEqual(fs[0].why, "확인함")
        self.assertIn("근거 없음", fs[1].why)  # 근거 없는 지적은 판단 모델이 fix라 해도 report
        with self.assertRaises(review.ReviewError):
            review.apply_decisions('{"decisions": 1}', fs)

    def test_malformed_decisions_are_review_errors(self):
        # 리뷰 #3: 판단 모델의 잘못된 JSON이 TypeError로 코디네이터를 죽이지 않고 ReviewError가 된다
        bad = ['{"decisions": [{"id": [], "action": "fix"}]}', '{"decisions": [1]}',
               '{"decisions": [{"id": "1", "action": "fix"}]}', '{"decisions": [{"id": true, "action": "fix"}]}',
               '{"decisions": [{"id": 1, "action": ["fix"]}]}', '{"decisions": [{"id": 1}]}',
               '{"decisions": [{"id": 1, "action": "fix", "why": {}}]}',
               '{"decisions": [{"id": 1, "action": "fix"}, {"id": 1, "action": "report"}]}',
               "[" * 100000]
        for text in bad:
            fs = [review.Finding(1, "high", "a", "c", "e")]
            with self.subTest(text=text[:60]), self.assertRaises(review.ReviewError):
                review.apply_decisions(text, fs)
            self.assertEqual((fs[0].action, fs[0].why), ("report", ""))  # 형식이 틀리면 아무것도 적용하지 않는다

    def test_family(self):
        review.require_other_family("claude", "codex")
        with self.assertRaises(review.Refused):
            review.require_other_family("codex", "Codex")

    def test_remaining_and_fix_brief(self):
        rec = {"findings": [{"id": 1, "severity": "high", "location": "a", "claim": "c1", "evidence": "e",
                             "action": "fix", "fix_attempt": review.ATTEMPTED},
                            {"id": 2, "severity": "low", "location": "b", "claim": "c2", "evidence": "",
                             "action": "report", "fix_attempt": ""}]}
        # 리뷰 #2: 재리뷰가 없으니 수정을 시도한 fix 지적도 남은 지적이다
        self.assertEqual([f["id"] for f in review.remaining(rec)], [1, 2])
        self.assertEqual([f["id"] for f in review.fixes(rec)], [1])
        brief = review.fix_brief(review.fixes(rec))
        self.assertIn("## 리뷰 지적(고칠 것)", brief)
        self.assertIn("c1", brief)
        self.assertNotIn("c2", brief)


if __name__ == "__main__":
    unittest.main()
