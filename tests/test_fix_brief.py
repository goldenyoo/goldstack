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


class FixBriefTouchesTest(unittest.TestCase):
    """수정 worker brief는 티켓 touches와 그중 시험 파일을 돌리라는 문장, 설명 확인 문장을 담는다(goldstack-v21 02)."""

    TOUCHES = ["src/gs/review.py", "tests/test_fix_brief.py", "docs/guide.md"]

    def test_touches_and_test_sentence(self):
        for nth in (1, 2):
            with self.subTest(nth=nth):
                text = review.fix_brief([FINDING], nth, self.TOUCHES)
                self.assertIn("이 티켓이 건드리는 파일(touches): `src/gs/review.py`, `tests/test_fix_brief.py`, `docs/guide.md`", text)
                self.assertIn("그중 시험 파일 `tests/test_fix_brief.py`을 고친 뒤 돌려 통과하는지 확인한다", text)
                self.assertNotIn("시험 파일 `src/gs/review.py`", text)

    def test_no_test_file_means_no_test_sentence(self):
        text = review.fix_brief([FINDING], 1, ["src/gs/review.py", "docs/guide.md"])
        self.assertIn("(touches): `src/gs/review.py`, `docs/guide.md`", text)
        self.assertNotIn("시험 파일", text)
        self.assertNotIn("돌려 통과하는지", text)

    def test_no_touches_means_no_touches_lines(self):
        for touches in (None, []):
            with self.subTest(touches=touches):
                text = review.fix_brief([FINDING], 1, touches)
                self.assertNotIn("touches", text)
                self.assertNotIn("시험 파일", text)

    def test_second_fix_gets_touches_too(self):
        text = review.fix_brief([FINDING], 2, self.TOUCHES)
        self.assertIn("이번이 마지막 수정이다", text)
        self.assertIn("그중 시험 파일 `tests/test_fix_brief.py`", text)

    def test_explain_rule_in_every_fix_brief(self):
        for nth in (1, 2):
            for touches in (None, self.TOUCHES):
                with self.subTest(nth=nth, touches=touches):
                    text = review.fix_brief([FINDING], nth, touches)
                    self.assertIn(review.EXPLAIN_RULE, text)
                    self.assertIn("지적이 요구하지 않은 새 동작 설명(주석·docstring·문서)은 쓰지 않는다", text)
                    self.assertIn("코드 줄을 읽어 사실인지 확인한 뒤에 쓴다", text)

    def test_repair_brief_is_unchanged(self):
        text = review.repair_brief("/x/verify.log")
        self.assertNotIn("touches", text)
        self.assertNotIn(review.EXPLAIN_RULE, text)

    def test_is_test_path(self):
        for path in ("tests/test_x.py", "tests/support.py", "test_x.py", "a/b_test.go", "hooks/register.test.tsx", "src/__tests__/a.ts"):
            with self.subTest(path=path):
                self.assertTrue(review.is_test_path(path))
        for path in ("src/gs/review.py", "docs/guide.md", "src/latest.py", "src/contest/a.py"):
            with self.subTest(path=path):
                self.assertFalse(review.is_test_path(path))


class FixBriefGoWiringTest(unittest.TestCase):
    """go.py의 두 호출(_start_fix, 네트워크로 잇는 수정)이 둘 다 티켓 touches를 넘긴다."""

    def test_both_calls_pass_touches(self):
        import re
        src = (Path(__file__).resolve().parent.parent / "src" / "gs" / "go.py").read_text(encoding="utf-8")
        calls = re.findall(r"review\.fix_brief\(([^\n]*)\)", src)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertIn("t.touches", call)


if __name__ == "__main__":
    unittest.main()
