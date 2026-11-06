"""수정·수리 worker는 전체 시험 대신 좁은 시험만 돌린다(goldstack-v12 03). 첫 구현 worker brief는 그대로다."""
import tempfile
import unittest
from pathlib import Path

from gs import review, worker
from gs.feature import Spec, Ticket

FIRST_RULE = ("- 검증 명령 `{v}`: 개발 중에는 관련 시험만 돌리고, 커밋 전에 이 명령을 한 번 돌린다. "
              "통과시켜야 한다. gs가 커밋된 내용만으로 병합 트리에서 다시 돌려 확인한다.")
NARROW_RULE = ("- 검증 명령 `{v}`: 전체 검증은 gs가 커밋된 내용만으로 병합 트리에서 돌린다. 너는 돌리지 않는다. "
               "고친 곳에 닿는 좁은 시험만 돌린다.")
RUN_ONCE = "커밋 전에 이 명령을 한 번 돌린다"
FINDING = {"id": "1", "severity": "high", "location": "a.py:1", "claim": "틀렸다", "evidence": "e"}


class FixBriefTest(unittest.TestCase):
    def briefs(self, spec_verify="full", ticket_verify=None) -> dict[str, str]:
        """첫 worker, 1차·2차 수정 worker, 수리 worker가 실제로 받는 brief(go.py가 붙이는 순서 그대로)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                            path=root / "01-t.md", body="## 목표\n하나", verify=ticket_verify)
            spec = Spec(feature="demo", verify=spec_verify, max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            out = {}
            for name, kwargs, tail in (
                    ("first", {}, ""),
                    ("fix1", {"narrow": True}, review.fix_brief([FINDING], 1)),
                    ("fix2", {"narrow": True}, review.fix_brief([FINDING], 2)),
                    ("repair", {"narrow": True}, review.repair_brief("/x/verify.log"))):
                job = worker.Job(ticket=ticket, worktree=root, rundir=root / name)
                job.rundir.mkdir()
                worker.write_brief(job, spec, "demo", "gs/demo/01", **kwargs)
                out[name] = job.brief.read_text(encoding="utf-8") + tail
            return out

    def check(self, verify, **kwargs):
        briefs = self.briefs(**kwargs)
        self.assertIn(FIRST_RULE.format(v=verify), briefs["first"])
        self.assertIn(RUN_ONCE, briefs["first"])
        for name in ("fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                self.assertNotIn(RUN_ONCE, briefs[name])
                self.assertIn(NARROW_RULE.format(v=verify), briefs[name])
        return briefs

    def test_three_briefs(self):
        briefs = self.check("full")
        self.assertIn("## 리뷰 지적(고칠 것)", briefs["fix1"])
        self.assertIn("## 검증 실패(고칠 것)", briefs["repair"])

    def test_same_with_narrow_ticket_verify(self):
        self.check("fast", ticket_verify="fast")

    def test_first_worker_brief_is_unchanged(self):
        first = self.briefs()["first"]
        self.assertIn(FIRST_RULE.format(v="full"), first)
        self.assertNotIn("좁은 시험만 돌린다.", first)
        self.assertNotIn("너는 돌리지 않는다", first)

    def test_fix_and_repair_keep_the_other_rules(self):
        briefs = self.briefs()
        for name in ("fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                for phrase in ("네트워크, localhost, 홈 디렉터리 쓰기, ps 실행이 필요한 검증 단계만",
                               "사람에게 묻지 않는다", "완료 조건이 이 티켓의 명세다"):
                    self.assertIn(phrase, briefs[name])

    def test_review_prompts_exempt_ps(self):
        p = Path("x")
        for name, text in (("review", review.review_prompt(p, p, p, p)),
                           ("rereview", review.rereview_prompt(p, p, p, p, p))):
            with self.subTest(prompt=name):
                self.assertIn("네트워크, localhost, 홈 디렉터리 쓰기, ps 실행이 필요한 단계", text)

    def test_only_the_verify_rule_differs(self):
        briefs = self.briefs()
        first = briefs["first"].splitlines()
        fix = briefs["fix1"].splitlines()[:len(first)]
        diff = [(a, b) for a, b in zip(first, fix) if a != b]
        self.assertEqual(len(diff), 1)
        self.assertTrue(diff[0][0].startswith("- 검증 명령 "))


if __name__ == "__main__":
    unittest.main()
