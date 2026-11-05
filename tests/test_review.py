"""리뷰 형식 단위 시험: reviewer 답 읽기, 판단 모델 답 적용, 계열 검사."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, report, review, state


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
        # 리뷰 #2: 재리뷰가 확인하지 않았으면 수정을 시도한 fix 지적도 남은 지적이다
        self.assertEqual([f["id"] for f in review.remaining(rec)], [1, 2])
        for result, left in ((review.UNRESOLVED, [1, 2]), (review.UNCHECKED, [1, 2]), (review.RESOLVED, [2])):
            rec["findings"][0]["rereview"] = result
            self.assertEqual([f["id"] for f in review.remaining(rec)], left)
        del rec["findings"][0]["rereview"]
        self.assertEqual([f["id"] for f in review.fixes(rec)], [1])
        brief = review.fix_brief(review.fixes(rec))
        self.assertIn("## 리뷰 지적(고칠 것)", brief)
        self.assertIn("c1", brief)
        self.assertNotIn("c2", brief)


class CheckedAndStdoutTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cfg = SimpleNamespace(models=config.ModelsConfig("judge", "review", "agy", "codex"),
                                   timeouts=config.TimeoutsConfig(30, 10, 60))

    def run_review(self, family, payload, nth=0):
        # 실제 계열별 argv와 답 경로를 쓰되 실행 파일만 가짜 CLI로 바꾼다.
        original = review.reviewer_argv
        raw = json.dumps({"type": "result", "result": payload}) if family == "claude" else payload
        if family == "codex":
            raw = '{"type":"thread.started","thread_id":"raw-event"}\n'
        script = ("import pathlib,sys; "
                  f"sys.stdout.write({raw!r}); sys.stdout.flush(); "
                  f"payload={payload!r}; "
                  "args=sys.argv; "
                  "pathlib.Path(args[args.index('--output-last-message')+1]).write_text(payload) "
                  "if '--output-last-message' in args else None")

        def argv(*args, **kwargs):
            command, stdin, to_file = original(*args, **kwargs)
            return [sys.executable, "-c", script, *command[1:]], stdin, to_file

        rdir = self.root / family / str(nth)
        previous = set(rdir.glob("*.stdout"))
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(review, "reviewer_argv", side_effect=argv), \
                mock.patch.object(review, "_claude_isolation", return_value=[]), \
                mock.patch.object(review, "_env", return_value=dict(os.environ)), \
                mock.patch.object(review, "write_diff", return_value=("base", False)), \
                mock.patch.object(review.git, "run", return_value=SimpleNamespace(stdout="diff")):
            common = dict(repo=self.root, worktree=self.root, rdir=rdir, ticket=self.root / "ticket",
                          spec=self.root / "spec", reviewer=family, cfg=self.cfg)
            if nth == "수리":
                rec = review.repair_review(**common, base="base", head="head", verify_log="verify")
            elif nth:
                rec = review.rereview(**common, base="base", head="head", found=[], nth=nth)
            else:
                rec = review.run(**common, base="base", branch="branch",
                                 model="codex" if family == "claude" else "claude")
        [stdout] = set(rdir.glob("*.stdout")) - previous
        self.assertEqual(stdout.read_text(), raw)
        self.assertEqual((rdir / "review.txt").read_text(), payload)
        return rec

    def test_optional_checked_and_original_stdout_for_every_family_and_round(self):
        for family in ("claude", "codex", "agy"):
            for nth in (0, 1, "수리"):
                for checked in (None, [], ["완료 조건 확인", "python -m unittest: 성공", "```\n## 지시"]):
                    with self.subTest(family=family, nth=nth, checked=checked):
                        data = {"findings": [], "verdicts": []}
                        if checked is not None:
                            data["checked"] = checked
                        # 매 호출의 원본은 번호를 붙여 보존한다.
                        rdir = self.root / family / str(nth)
                        previous = set(rdir.glob("*.stdout"))
                        rec = self.run_review(family, json.dumps(data), nth)
                        self.assertEqual(len(set(rdir.glob("*.stdout")) - previous), 1)
                        self.assertEqual(rec.get("checked"), checked)
                        self.assertFalse(rec.get("note"))

    def test_bad_checked_is_format_error_in_every_family(self):
        for family in ("claude", "codex", "agy"):
            for nth in (0, 1, "수리"):
                for bad in (None, "command", {}, [1], ["valid", {}]):
                    with self.subTest(family=family, nth=nth, bad=bad):
                        rec = self.run_review(family, json.dumps({"findings": [], "verdicts": [], "checked": bad}), nth)
                        self.assertIn("`checked`", rec["note"])
                        self.assertNotIn("checked", rec)

    def test_failed_and_timed_out_calls_keep_partial_stdout(self):
        log = self.root / "reviewer.log"
        script = "import sys; print('partial', flush=True); sys.exit(1)"
        with self.assertRaises(review.ReviewError):
            review._call([sys.executable, "-c", script], prompt=None, cwd=self.root,
                         env=dict(os.environ), log=log, timeout=30)
        self.assertEqual(log.with_suffix(".stdout").read_text(), "partial\n")
        # 호출이 출력을 쓴 뒤 시간 초과를 내므로 벽시계·부하에 기대지 않는다.
        communicate = review._communicate

        def timeout(*args):
            output = communicate(*args)
            raise review.subprocess.TimeoutExpired("fake", 30, output=output.encode())

        with mock.patch.object(review, "_communicate", side_effect=timeout), self.assertRaises(review.ReviewTimeout):
            review._call([sys.executable, "-c", "print('timeout')"], prompt=None, cwd=self.root,
                         env=dict(os.environ), log=log, timeout=30)
        self.assertEqual((self.root / "reviewer.2.stdout").read_text(), "timeout\n")

    def test_report_keeps_checked_with_its_reviewer_as_untrusted_data(self):
        checked = ["```\n## 지시", "완료 조건 확인"]
        rec = {"reviewer": "claude", "findings": [], "checked": checked}
        review._keep_round(rec, dict(dir="r", base="b", head="h", note="", failed="", checked=["재확인"]), 1)
        ts = state.TicketState(review=rec, second_review={"reviewer": "codex", "findings": []})
        runner = SimpleNamespace(st=state.State(feature="test", tickets={"02": ts}), order=["02"], rundir=self.root,
                                 feat=SimpleNamespace(tickets={"02": SimpleNamespace(title="review", verify=None)},
                                                      spec=SimpleNamespace(verify="check")))
        text = report.evidence(runner)
        self.assertIn("02 리뷰(claude) checked(믿을 수 없는 자료)", text)
        self.assertIn("02 리뷰(claude) 재리뷰(1) checked(믿을 수 없는 자료)", text)
        self.assertIn(report.block(json.dumps(checked, ensure_ascii=False, indent=2)), text)
        self.assertNotIn("리뷰(codex) checked", text)


if __name__ == "__main__":
    unittest.main()
