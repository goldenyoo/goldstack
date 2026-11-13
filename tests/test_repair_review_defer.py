"""goldstack-v38 02: 수리 재리뷰가 그 리뷰어의 defer 지적을 판정하고, 보고서가 해소를 반영한다.

defer 지적은 재현됐지만 고칠 수 있는 파일 밖이라 고치지 않은 결함이다(review.DEFER). 수리 커밋이 그것을 해소했어도 보고서가
"재현된 미수리"로 세면 남은 high가 부풀려진다. 수리 재리뷰 프롬프트가 그 지적을 id와 함께 싣고 지적별 판정을 받는다.
DeferVerdictTest는 가짜 판단 모델·리뷰어로 수리 재리뷰를 끝까지 돌려 보고서 마무리 줄(report.remaining_line)을 본다.
RecordTest는 판정을 지적에 적고 읽는 함수를 직접 부른다(옛 state, 재리뷰 실패, 다시 본 head).
"""
import json
import sys
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_verify_repair
from test_verify_repair import BREAKS, REPAIRS

from gs import report, review, state

CLAIM = "DEFER 병합된 티켓 밖 util.py가 빈 입력에서 틀린다"
EVIDENCE = "재현: python -c 'import util; util.f(\"\")' → exit 1"
DEFERRED_FINDING = {"severity": "medium", "location": "util.py:3", "claim": CLAIM, "evidence": EVIDENCE}
REVIEWED = "수리가 util.py의 빈 입력 처리를 고친 것을 코드로 확인했다"

# 판단 모델: 첫 리뷰의 지적 중 claim에 DEFER가 있는 것은 defer, 나머지는 report로 나눈다.
JUDGE = r'''#!/bin/bash
here="$(dirname "$0")"
cat > "$here/judge.input"
if grep -q report-input.md "$here/judge.input"; then echo '남은 리뷰 지적을 확인했다.'; exit 0; fi
"$PY" - "$(grep -o '/[^ `]*findings.json' "$here/judge.input" | head -n 1)" <<'PYEOF'
import json, sys
fs = json.load(open(sys.argv[1]))["findings"]
print(json.dumps({"decisions": [{"id": f["id"], "action": "defer" if "DEFER" in f["claim"] else "report", "why": "가짜"} for f in fs]}))
PYEOF
'''


class Base(test_verify_repair.Base):
    def reviewers_answer(self, first, repair_answer):
        """첫 리뷰는 first를 내고, 수리 재리뷰는 repair_answer(JSON 글자 그대로)를 낸다. 수리 재리뷰의 프롬프트는 repair.prompt에 남는다."""
        (self.bin / "first_found.json").write_text(json.dumps({"findings": first}, ensure_ascii=False))
        (self.bin / "repair_answer.json").write_text(repair_answer)
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            cat > "$here/review.prompt"
            if grep -q '수리 커밋 diff' "$here/review.prompt"; then
              cp "$here/review.prompt" "$here/repair.prompt"; cat "$here/repair_answer.json"
            else cat "$here/first_found.json"; fi
        '''))
        (self.bin / "judge").write_text(JUDGE)
        return mock.patch.dict("os.environ", {"PY": sys.executable})

    def run_repair(self, first, repair_answer):
        self.worker(BREAKS, REPAIRS)
        with self.reviewers_answer(first, repair_answer):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ts().status, "merged")
        return out

    def repair_prompt(self):
        return (self.bin / "repair.prompt").read_text(encoding="utf-8")

    def finding(self):
        [f] = self.ts().review["findings"]
        self.assertEqual(f["action"], review.DEFER)
        return f

    def closing_line(self):
        """보고서 마무리 줄(report.remaining_line)이 끝 출력과 보고서에 나온 모습."""
        return report.remaining_line(SimpleNamespace(order=["01"], st=state.load(self.rundir, "demo")))


def answer(*verdicts, findings=()):
    return json.dumps({"verdicts": list(verdicts), "findings": list(findings)}, ensure_ascii=False)


def verdict(status, evidence=REVIEWED, id=1):
    return {"id": id, "status": status, "evidence": evidence}


class DeferVerdictTest(Base):
    def test_resolved_defer_finding_is_not_a_remaining_high(self):
        out = self.run_repair([DEFERRED_FINDING], answer(verdict("resolved")))
        f = self.finding()
        self.assertEqual((f["repair_review"], f["repair_review_evidence"]), ("resolved", REVIEWED))
        self.assertEqual(report.finding_status(f), "수정됨(수리 재리뷰 확인)")
        self.assertEqual(self.closing_line(), "")
        final = self.final_report()
        self.assertNotIn("남은 high", final)
        self.assertNotIn("재현된 미수리 결함", final)
        self.assertIn(f"{CLAIM} — 상태: 수정됨(수리 재리뷰 확인)", final)
        self.assertNotIn("남은 high", out)

    def test_unresolved_defer_finding_is_still_counted(self):
        self.run_repair([DEFERRED_FINDING], answer(verdict("unresolved", "수리는 util.py를 건드리지 않았다")))
        f = self.finding()
        self.assertEqual(f["repair_review"], "unresolved")
        self.assertEqual(report.finding_status(f), "재현된 미수리")
        self.assertEqual(self.closing_line(), "남은 high 1(재현된 미수리 1)")
        final = self.final_report()
        self.assertIn("남은 high 1(재현된 미수리 1)", final)
        self.assertIn("### 재현된 미수리 결함", final)

    def assert_still_counted(self, text):
        self.run_repair([DEFERRED_FINDING], text)
        self.assertEqual(report.finding_status(self.finding()), "재현된 미수리")
        self.assertEqual(self.closing_line(), "남은 high 1(재현된 미수리 1)")

    def test_resolved_without_evidence_is_still_counted(self):
        self.assert_still_counted(answer(verdict("resolved", "")))

    def test_no_verdict_is_still_counted(self):
        self.assert_still_counted(answer())

    def test_failed_repair_review_is_still_counted(self):
        self.assert_still_counted("판정이 아닌 글")

    def test_verdict_for_another_id_is_still_counted(self):
        self.assert_still_counted(answer(verdict("resolved", id=7)))

    def test_unreadable_verdicts_keep_the_findings_and_the_defer_count(self):
        """판정 부분이 틀려도 새 지적은 받고, defer 지적은 그대로 센다."""
        new = {"severity": "low", "location": "file_01", "claim": "이름이 모호하다", "evidence": "e"}
        self.run_repair([DEFERRED_FINDING], json.dumps({"verdicts": "resolved", "findings": [new]}, ensure_ascii=False))
        defer, added = self.ts().review["findings"]
        self.assertNotIn("repair_review", defer)
        self.assertEqual(report.finding_status(defer), "재현된 미수리")
        self.assertEqual(added["claim"], "이름이 모호하다")

    def test_prompt_lists_the_defer_finding_with_its_id_and_asks_for_a_verdict(self):
        self.run_repair([DEFERRED_FINDING], answer(verdict("resolved")))
        prompt = self.repair_prompt()
        self.assertIn(f"- id 1 [medium] util.py:3: {CLAIM}", prompt)
        self.assertIn(EVIDENCE, prompt)
        self.assertIn('"verdicts": [{"id": 1, "status": "resolved|unresolved", "evidence": "근거"}]', prompt)

    def test_without_a_defer_finding_the_prompt_has_no_defer_part(self):
        self.run_repair([], '{"findings": []}')
        prompt = self.repair_prompt()
        for word in ("defer", "verdicts", "resolved"):
            self.assertNotIn(word, prompt)
        self.assertIn('지적이 없으면 {"findings": []}.', prompt)
        # 같은 인자에 defer만 없으면 글자 그대로 같다
        self.assertEqual(review.repair_review_prompt(Path("d"), "log", Path("t"), Path("s"), Path("w"), defer=[]),
                         review.repair_review_prompt(Path("d"), "log", Path("t"), Path("s"), Path("w")))

    def test_only_the_defer_findings_of_that_reviewer_are_listed(self):
        """첫 리뷰의 report·fix 지적은 싣지 않는다."""
        taste = {"severity": "low", "location": "x", "claim": "취향 의견", "evidence": ""}
        self.worker(BREAKS, REPAIRS)
        with self.reviewers_answer([DEFERRED_FINDING, taste], answer(verdict("resolved"))):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        prompt = self.repair_prompt()
        self.assertIn(CLAIM, prompt)
        self.assertNotIn("취향 의견", prompt)


class RecordTest(unittest.TestCase):
    """review.apply_repair_review·report.finding_status를 직접 부른다."""

    def rec(self):
        return {"reviewer": "codex", "findings": [
            {"id": 1, "severity": "medium", "location": "u.py", "claim": "d", "evidence": "e", "action": "defer"},
            {"id": 2, "severity": "high", "location": "v.py", "claim": "r", "evidence": "e", "action": "report"}]}

    def res(self, verdicts=None, failed="", base="b", head="h"):
        return {"dir": "d", "base": base, "head": head, "note": "", "failed": failed, "findings": [], "defer_verdicts": verdicts or {}}

    def test_old_state_without_the_verdict_keys_counts_as_before(self):
        defer = self.rec()["findings"][0]
        self.assertEqual(report.finding_status(defer), "재현된 미수리")
        self.assertFalse(review.repair_resolved(defer))
        old_res = {k: v for k, v in self.res().items() if k != "defer_verdicts"}  # 옛 결과 모양
        rec = self.rec()
        review.apply_repair_review(rec, old_res)
        self.assertEqual(report.finding_status(rec["findings"][0]), "재현된 미수리")

    def test_resolved_is_written_only_to_defer_findings(self):
        rec = self.rec()
        review.apply_repair_review(rec, self.res({1: {"status": "resolved", "evidence": "x"}, 2: {"status": "resolved", "evidence": "x"}}))
        self.assertEqual(report.finding_status(rec["findings"][0]), "수정됨(수리 재리뷰 확인)")
        self.assertNotIn("repair_review", rec["findings"][1])
        self.assertEqual(report.finding_status(rec["findings"][1]), "보고만")

    def test_failed_review_clears_an_earlier_resolved(self):
        """병합 전 대조가 새 head를 다시 봤는데 실패하면 앞 head의 resolved를 남기지 않는다."""
        rec = self.rec()
        review.apply_repair_review(rec, self.res({1: {"status": "resolved", "evidence": "x"}}, head="h1"))
        review.apply_repair_review(rec, self.res(failed="재리뷰 실패", head="h2"))
        self.assertEqual(report.finding_status(rec["findings"][0]), "재현된 미수리")

    def test_later_unresolved_replaces_an_earlier_resolved(self):
        rec = self.rec()
        review.apply_repair_review(rec, self.res({1: {"status": "resolved", "evidence": "x"}}, head="h1"))
        review.apply_repair_review(rec, self.res({1: {"status": "unresolved", "evidence": "y"}}, head="h2"))
        self.assertEqual(report.finding_status(rec["findings"][0]), "재현된 미수리")

    def test_superseded_stays_superseded(self):
        f = {**self.rec()["findings"][0], "superseded": "h", "repair_review": "resolved", "repair_review_evidence": "x"}
        self.assertEqual(report.finding_status(f), "대체됨")


if __name__ == "__main__":
    unittest.main()
