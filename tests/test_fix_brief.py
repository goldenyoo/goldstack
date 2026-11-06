"""모든 worker(첫·재개·수정·수리)는 계열과 상관없이 같은 좁은 시험 규칙과 기계 공유 규칙을 받는다(goldstack-v12 03, v20 08)."""
import tempfile
import unittest
from pathlib import Path

from gs import review, worker
from gs.feature import Spec, Ticket

OLD_FIRST_RULE = "개발 중에는 관련 시험만 돌리고, 커밋 전에 이 명령을 한 번 돌린다"
NARROW_RULE = ("- 검증 명령 `{v}`: 전체 검증은 gs가 커밋된 내용만으로 병합 트리에서 돌린다. 너는 돌리지 않는다. "
               "고친 곳에 닿는 좁은 시험만 돌린다.")
RUN_ONCE = "커밋 전에 이 명령을 한 번 돌린다"
MACHINE = "다른 티켓이 같은 기계에서 함께 돈다. 네가 띄운 프로세스는 그 PID로 기다리고 끝낸다"
SEE_FAIL = "그 시험이 실패하는 것을 직접 본다"
FINDING = {"id": "1", "severity": "high", "location": "a.py:1", "claim": "틀렸다", "evidence": "e"}


class FixBriefTest(unittest.TestCase):
    def briefs(self, spec_verify="full", ticket_verify=None, model="claude") -> dict[str, str]:
        """첫 worker, 재개 worker, 1차·2차 수정 worker, 수리 worker가 실제로 받는 brief(go.py가 붙이는 순서 그대로)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticket = Ticket(id="01", title="t", blocked_by=[], model=model, reviewer="codex" if model != "codex" else "claude",
                            path=root / "01-t.md", body="## 목표\n하나", verify=ticket_verify)
            spec = Spec(feature="demo", verify=spec_verify, max_workers=1, idle_minutes=20,
                        verify_minutes=20, path=root / "spec.md")
            out = {}
            for name, kwargs, tail in (
                    ("first", {}, ""),
                    ("resumed", {"resumed": True}, ""),
                    ("fix1", {}, review.fix_brief([FINDING], 1)),
                    ("fix2", {}, review.fix_brief([FINDING], 2)),
                    ("repair", {}, review.repair_brief("/x/verify.log"))):
                job = worker.Job(ticket=ticket, worktree=root, rundir=root / name)
                job.rundir.mkdir()
                worker.write_brief(job, spec, "demo", "gs/demo/01", **kwargs)
                out[name] = job.brief.read_text(encoding="utf-8") + tail
            return out

    def check(self, verify, **kwargs):
        briefs = self.briefs(**kwargs)
        for name, text in briefs.items():
            with self.subTest(brief=name):
                self.assertNotIn(RUN_ONCE, text)
                self.assertNotIn(OLD_FIRST_RULE, text)
                self.assertIn(NARROW_RULE.format(v=verify), text)
        return briefs

    def test_three_briefs(self):
        briefs = self.check("full")
        self.assertIn("## 리뷰 지적(고칠 것)", briefs["fix1"])
        self.assertIn("## 검증 실패(고칠 것)", briefs["repair"])

    def test_same_with_narrow_ticket_verify(self):
        self.check("fast", ticket_verify="fast")

    def test_every_family_gets_the_same_rule(self):
        for model in ("claude", "codex", "agy"):
            with self.subTest(model=model):
                self.check("full", model=model)

    def test_write_brief_has_no_narrow_argument(self):
        import inspect
        self.assertNotIn("narrow", inspect.signature(worker.write_brief).parameters)

    def test_every_brief_keeps_the_other_rules(self):
        for name, text in self.briefs().items():
            with self.subTest(brief=name):
                for phrase in ("네트워크, localhost, 홈 디렉터리 쓰기, ps 실행이 필요한 검증 단계만",
                               "사람에게 묻지 않는다", "완료 조건이 이 티켓의 명세다"):
                    self.assertIn(phrase, text)

    def test_review_prompts_exempt_ps(self):
        p = Path("x")
        for name, text in (("review", review.review_prompt(p, p, p, p)),
                           ("rereview", review.rereview_prompt(p, p, p, p, p))):
            with self.subTest(prompt=name):
                self.assertIn("네트워크, localhost, 홈 디렉터리 쓰기, ps 실행이 필요한 단계", text)

    def test_brief_start_is_the_same_for_every_kind(self):
        briefs = self.briefs()
        first = briefs["first"].splitlines()
        for name in ("fix1", "fix2", "repair"):
            with self.subTest(brief=name):
                self.assertEqual(briefs[name].splitlines()[:len(first)], first)

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

    def test_every_worker_brief_tells_to_handle_only_own_processes(self):
        for model in ("claude", "codex", "agy"):
            for ticket_verify in (None, "fast"):
                for name, text in self.briefs(model=model, ticket_verify=ticket_verify).items():
                    with self.subTest(model=model, ticket_verify=ticket_verify, brief=name):
                        self.assertIn(MACHINE, text)
                        self.assertIn(worker.MACHINE_RULE, text)
                        self.assertEqual(text.count(MACHINE), 1)

    def test_brief_does_not_clash_with_codex_note(self):
        from gs import adapters
        first = self.briefs(model="codex")["first"]
        self.assertNotIn("이 명령을 한 번 돌린다", first)
        self.assertNotIn("통과시켜야 한다", first)
        self.assertIn("좁은 시험", adapters.Codex.NOTE)

    def test_resumed_brief_follows_the_same_rule(self):
        for model in ("codex", "claude", "agy"):
            with self.subTest(model=model):
                text = self.briefs(model=model)["resumed"]
                self.assertIn(NARROW_RULE.format(v="full"), text)
                self.assertIn(worker.NETWORK_RESUME, text)


if __name__ == "__main__":
    unittest.main()
