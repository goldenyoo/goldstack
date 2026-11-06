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
SEE_FAIL = "그 시험이 실패하는 것을 직접 본다"
FINDING = {"id": "1", "severity": "high", "location": "a.py:1", "claim": "틀렸다", "evidence": "e"}


class FixBriefTest(unittest.TestCase):
    def briefs(self, spec_verify="full", ticket_verify=None, model="claude") -> dict[str, str]:
        """첫 worker, 1차·2차 수정 worker, 수리 worker가 실제로 받는 brief(go.py가 붙이는 순서 그대로)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model=model, reviewer="codex" if model != "codex" else "claude",
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

    def test_every_worker_brief_asks_to_see_the_new_test_fail(self):
        for model in ("claude", "codex", "agy"):
            briefs = self.briefs(model=model)
            for name, text in briefs.items():
                with self.subTest(model=model, brief=name):
                    self.assertIn(SEE_FAIL, text)
                    self.assertIn(worker.SEE_FAIL_RULE, text)
                    self.assertIn("본 실패(시험 이름과 실패 메시지)를 마지막 메시지에 적는다", text)
                    self.assertIn("복구한 뒤 커밋", text)
                    self.assertIn("문서 티켓에는 해당하지 않는다", text)

    def test_codex_first_worker_runs_narrow_tests_only(self):
        briefs = self.briefs(model="codex")
        for name in ("first", "fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                self.assertNotIn(RUN_ONCE, briefs[name])
                self.assertNotIn(FIRST_RULE.format(v="full"), briefs[name])
                self.assertIn(NARROW_RULE.format(v="full"), briefs[name])

    def test_non_codex_first_worker_keeps_full_verify(self):
        for model in ("claude", "agy"):
            with self.subTest(model=model):
                first = self.briefs(model=model)["first"]
                self.assertIn(FIRST_RULE.format(v="full"), first)
                self.assertNotIn(NARROW_RULE.format(v="full"), first)

    def test_codex_first_brief_does_not_clash_with_codex_note(self):
        from gs import adapters
        first = self.briefs(model="codex")["first"]
        self.assertNotIn("이 명령을 한 번 돌린다", first)
        self.assertNotIn("통과시켜야 한다", first)
        self.assertIn("좁은 시험", adapters.Codex.NOTE)

    def test_resumed_brief_follows_the_same_rule(self):
        for model, rule in (("codex", NARROW_RULE), ("claude", FIRST_RULE)):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                ticket = Ticket(id="01", title="t", blocked_by=[], model=model, reviewer="x",
                                path=root / "01-t.md", body="목표")
                spec = Spec(feature="demo", verify="full", max_workers=1, idle_minutes=20,
                            verify_minutes=20, path=root / "spec.md")
                job = worker.Job(ticket=ticket, worktree=root, rundir=root)
                worker.write_brief(job, spec, "demo", "gs/demo/01", resumed=True)
                text = job.brief.read_text(encoding="utf-8")
                self.assertIn(rule.format(v="full"), text)
                self.assertIn(worker.NETWORK_RESUME, text)
                self.assertIn(SEE_FAIL, text)

    def test_rereview_prompt_does_not_get_the_rule(self):
        p = Path("x")
        for text in (review.review_prompt(p, p, p, p), review.rereview_prompt(p, p, p, p, p)):
            self.assertNotIn(SEE_FAIL, text)
            self.assertNotIn("고친 코드만 잠깐 되돌려", text)


if __name__ == "__main__":
    unittest.main()
