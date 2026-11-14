"""goldstack-v40 03: 2차 재리뷰가 1차 재리뷰의 새 report 지적도 판정한다(review.is_report_check, go._to_rereview).

판정만 한다: 2차 수정 worker의 대상이 아니고, unresolved여도 병합을 막지 않는다. resolved면 보고서 상태가 "해소됨(재리뷰 확인)"이라
남은 지적·남은 high에서 빠진다. 그 지적만 가진 리뷰 기록 때문에 리뷰어를 새로 부르지 않는다.

가짜 리뷰어는 test_recheck_resolved처럼 트리를 읽어 판정한다: "<낱말> X: …" 지적은 worktree에 fixed_X가 있으면 resolved다.
new_<who>_<n>.json이 있으면 그 재리뷰가 그 지적을 새로 낸다. 가짜 판단 모델은 claim에 FIX가 있으면 fix, 아니면 report로 나눈다.
"""
import json
import unittest
from pathlib import Path

import support
import test_recheck_resolved
from test_recheck_resolved import A, B, FIXED
from test_review_target import at_call, integration_moved
from test_second_review import finding
from test_second_reviewer_rereview import set_rereview

from gs import report, review, state

# 가짜 reviewer: test_recheck_resolved.REVIEWER에 재리뷰의 새 지적(new_<who>_<n>.json)을 더했다.
# drop_<who>_<n>: 파일에 적은 id의 판정을 빼고 답한다. down_<who>: 그 값 이상의 호출이 끊긴다(up이 없는 동안).
REVIEWER = """\
here="$(dirname "$0")"
who="$GS_REVIEWER"
in="$(mktemp)"; cat > "$in"
if ! grep -q '"verdicts"' "$in"; then
  if [ -f "$here/findings_$who.json" ]; then cat "$here/findings_$who.json"; else echo '{"findings": []}'; fi
  exit 0
fi
n=$(( $(cat "$here/rereview_n_$who" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/rereview_n_$who"
echo "$who $n" >> "$here/rereview.calls"
listed="$(grep -o '/[^ `]*fix-findings\\.json' "$in" | head -n 1)"
cp "$in" "$here/rereview.prompt.$who.$n"
cp "$listed" "$here/rereview.findings.$who.$n"
if [ -f "$here/down_$who" ] && [ "$n" -ge "$(cat "$here/down_$who")" ] && [ ! -f "$here/up" ]; then
  echo '{"type":"error","message":"stream disconnected before completion: error sending request"}'; exit 1
fi
"$PY" - "$listed" "$here/drop_${who}_$n" "$here/new_${who}_$n.json" <<'PYEOF'
import json, os, sys
drop = open(sys.argv[2]).read().split() if os.path.exists(sys.argv[2]) else []
new = json.load(open(sys.argv[3]))["findings"] if os.path.exists(sys.argv[3]) else []
verdicts = []
for f in json.load(open(sys.argv[1]))["findings"]:
    if str(f["id"]) in drop:
        continue
    name = "fixed_" + f["claim"].split()[1].rstrip(":")
    there = os.path.exists(name)
    verdicts.append({"id": f["id"], "status": "resolved" if there else "unresolved",
                     "evidence": f"{name} {'있음' if there else '없음'}"})
print(json.dumps({"verdicts": verdicts, "findings": new}, ensure_ascii=False))
PYEOF
"""

# R: 1차 재리뷰가 새로 내고 판단 모델이 report로 나누는 high. Q: 첫 리뷰의 report 지적(판정 대상이 아니다). D: 두 번째 리뷰어의 fix 지적
R = finding("NOTE R: 1차 수정이 만든 새 문제", "high")
Q = finding("NOTE Q: 첫 리뷰의 보고만 지적", "medium")
D = finding("FIX D: 다른 값", "low")
RESOLVED_NOTE = report.REPORT_RESOLVED
MARK = ("고치라고 준 적 없는 보고만 지적", "이번 diff로 해소됐는지만 판정")


class Base(test_recheck_resolved.Base):
    def setUp(self):
        super().setUp()
        (self.bin / "reviewer.sh").write_text(REVIEWER)

    def new_finding(self, who, n, *items):
        """그 리뷰어의 n번째 재리뷰가 새로 낼 지적."""
        (self.bin / f"new_{who}_{n}.json").write_text(json.dumps({"findings": list(items)}, ensure_ascii=False))

    def listed(self, who, n):
        """그 호출이 받은 지적: (호출 id, claim, report_only, 원래 리뷰어)."""
        found = json.loads((self.bin / f"rereview.findings.{who}.{n}").read_text())["findings"]
        return [(f["id"], f["claim"], f.get("report_only", False), f.get("reviewer")) for f in found]

    def prompt(self, who, n):
        return (self.bin / f"rereview.prompt.{who}.{n}").read_text()

    def by_claim(self, rec, claim):
        [f] = [f for f in rec["findings"] if f["claim"] == claim["claim"]]
        return f

    def judged(self, f):
        return f["action"], f["found_round"], f["fix_round"], f.get("rereview", ""), f.get("rereview_round", 0)


class SecondRereviewTargetTest(Base):
    def run_with_r_fixed(self):
        """codex가 A·B·Q를 내고 1차 재리뷰가 R을 새로 낸다. 1차 수정은 A만, 2차 수정은 B와 R을 고친다."""
        self.findings("codex", A, B, Q)
        self.new_finding("codex", 1, R)
        self.a_fixed_first("touch fixed_R")
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assert_second_fix_got_only_b()
        self.assertNotIn("NOTE R", (self.rundir / "01/1/fix2/brief.md").read_text())  # 고칠 대상이 아니다
        return out

    def test_report_finding_of_the_first_rereview_is_a_second_target_with_a_mark(self):
        """(a) 2차 재리뷰가 R을 report_only로 받고 프롬프트에 구분 표시가 있다. 첫 리뷰의 report 지적(Q)은 대상이 아니고, 1차 재리뷰는 그대로다."""
        self.run_with_r_fixed()
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], False, None), (2, B["claim"], False, None),
                                                   (4, R["claim"], True, None)])
        for text in MARK:
            self.assertIn(text, self.prompt("codex", 2))
            self.assertNotIn(text, self.prompt("codex", 1))
        self.assertNotIn("report_only", (self.bin / "rereview.findings.codex.1").read_text())

    def test_resolved_report_finding_leaves_the_remaining(self):
        """(b) resolved 판정이 지적에 적히고 보고서 상태·남은 지적·남은 high에서 빠진다. 첫 리뷰의 report 지적은 그대로 보고만이다."""
        out = self.run_with_r_fixed()
        rec = self.ts().review
        r, q = self.by_claim(rec, R), self.by_claim(rec, Q)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.RESOLVED, 2))
        self.assertEqual(r["rereview_evidence"], "fixed_R 있음")
        self.assertEqual(self.judged(q), (review.REPORT, 0, 0, "", 0))
        self.assertEqual([f["claim"] for f in review.remaining(rec)], [Q["claim"]])
        self.assertIn("남은 리뷰 지적 1", out)
        self.assertIn(f"상태: {RESOLVED_NOTE}", self.report_line("NOTE R"))
        self.assertIn("상태: 보고만", self.report_line("NOTE Q"))
        text = self.final_report()
        self.assertIn("리뷰 지적: 수정됨 2 · 해소됨 1 · 보고만 1", text)
        self.assertNotIn("남은 high", text)  # R은 high지만 재리뷰가 해소를 확인했다

    def test_unresolved_high_report_finding_does_not_block_the_merge(self):
        """(c) R이 unresolved여도 병합을 막지 않고 수정 worker를 더 띄우지 않는다. 보고서에는 지금처럼 보고만이다."""
        self.findings("codex", A, B)
        self.new_finding("codex", 1, R)
        self.a_fixed_first()
        self.run_ok()
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        r = self.by_claim(ts.review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.UNRESOLVED, 2))
        self.assertEqual(review.final_highs(state.reviews(ts)), [])
        self.assertIn("상태: 보고만", self.report_line("NOTE R"))
        self.assertIn("남은 high 1(보고만 1)", self.final_report())

    def test_late_commit_reverting_the_second_fix_unresolves_the_report_finding(self):
        """2차 재리뷰가 R을 resolved로 본 뒤 늦은 커밋이 2차 수정을 되돌려 diff가 비면 R은 해소되지 않았다: 트리가 R을 낸 1차 재리뷰가 본 그대로다.
        재리뷰를 더 부르지 않고 unresolved로 적는다. 보고서에는 보고만이고 남은 지적이다. 병합은 막지 않는다."""
        self.findings("codex", A, B)
        self.new_finding("codex", 1, R)
        self.a_fixed_first("touch fixed_R")

        def revert(r, a):
            support.sh(a.wt, "git", "revert", "--no-edit", "HEAD")

        with at_call("_merge_stage", revert):
            self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertNotIn("fixed_R", self.files())
        rec = self.ts().review
        r = self.by_claim(rec, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.UNRESOLVED, 2))
        self.assertIn("diff가 비었다", r["rereview_evidence"])
        self.assertEqual([f["claim"] for f in review.remaining(rec)], [B["claim"], R["claim"]])
        self.assertIn("상태: 보고만", self.report_line("NOTE R"))

    def test_empty_commit_after_catch_up_keeps_the_report_verdict(self):
        """catch-up이 기준을 2차 재리뷰가 판정한 head 위로 옮긴 뒤의 빈 diff는 R의 resolved도 받은 지적처럼 유지한다."""
        self.findings("codex", A, B)
        self.new_finding("codex", 1, R)
        self.a_fixed_first("touch fixed_R")

        def empty_late_commit(r, _t):
            support.sh(self.rundir / "wt/01", "git", "commit", "-q", "--allow-empty", "-m", "empty late")

        with at_call("_catch_up", integration_moved), at_call("_verify", empty_late_commit):
            self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        rec = self.ts().review
        self.assertEqual(rec["kept_round"], 2)
        r = self.by_claim(rec, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.RESOLVED, 2))
        self.assertEqual(r["rereview_evidence"], "fixed_R 있음")
        self.assertIn(f"상태: {RESOLVED_NOTE}", self.report_line("NOTE R"))

    def test_report_finding_is_not_judged_without_a_second_rereview(self):
        """2차 수정이 없으면 2차 재리뷰도 없다. 1차 재리뷰의 새 report 지적은 지금처럼 판정 없이 보고만이다."""
        self.findings("codex", A)
        self.new_finding("codex", 1, R)
        self.plan(1, "touch fixed_A fixed_R")
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        r = self.by_claim(self.ts().review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, "", 0))
        self.assertIn("상태: 보고만", self.report_line("NOTE R"))

    def test_resume_during_the_second_rereview_picks_the_same_finding(self):
        """2차 재리뷰가 끊겨 멈췄다 이어도 R을 다시 대상으로 고른다. 고르는 값은 이 동작 전에도 state에 있던 action·found_round뿐이다."""
        self.network_limit(1)
        self.findings("codex", A, B)
        self.new_finding("codex", 1, R)
        self.a_fixed_first("touch fixed_R")
        (self.bin / "down_codex").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        raw = json.loads(state.path(self.rundir).read_text())
        [stored] = [f for f in raw["tickets"]["01"]["review"]["findings"] if f["claim"] == R["claim"]]
        self.assertEqual((stored["action"], stored["found_round"], stored["rereview"]), (review.REPORT, 1, ""))
        self.assertEqual(raw["tickets"]["01"]["network_resume"]["fix"], 2)

        (self.bin / "up").touch()
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])  # 수정 worker를 다시 띄우지 않는다
        last = int((self.bin / "rereview_n_codex").read_text())
        self.assertEqual(self.listed("codex", last)[-1], (3, R["claim"], True, None))
        r = self.by_claim(self.ts().review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.RESOLVED, 2))
        self.assertIn(f"상태: {RESOLVED_NOTE}", self.report_line("NOTE R"))


class SecondReviewerTest(Base):
    """두 번째 리뷰어(agy)의 기록에 2차 재리뷰가 판정할 것이 report 지적뿐이다: agy의 fix 지적 D는 1차 재리뷰 판정이 빠져 unchecked다."""

    def report_only_on_second(self):
        self.two_reviewers()
        self.findings("codex", A, B)
        self.findings("agy", D)
        self.new_finding("agy", 1, R)
        (self.bin / "drop_agy_1").write_text("1")  # D의 판정을 뺀다: agy 기록에 고칠 지적·다시 볼 지적이 남지 않는다
        self.a_fixed_first("touch fixed_R")

    def test_first_lends_the_report_finding_without_more_calls(self):
        """(d) first: agy의 R을 2차 재리뷰의 codex 호출에 빌려 판정하고 판정은 agy 기록의 R에 적힌다. 리뷰어 호출 수는 그대로다."""
        set_rereview(self, "first")
        self.report_only_on_second()
        out = self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 2)  # 첫 리뷰 + 1차 재리뷰
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], False, None), (2, B["claim"], False, None),
                                                   (3, R["claim"], True, "agy")])
        for text in MARK:
            self.assertIn(text, self.prompt("codex", 2))
        ts = self.ts()
        r = self.by_claim(ts.second_review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.RESOLVED, 2))
        self.assertEqual((r["rereview_evidence"], r["rereview_by"]), ("fixed_R 있음", "codex"))
        self.assertEqual(ts.review["rereviews"][-1]["lent"], [{"reviewer": "agy", "id": r["id"], "call_id": 3}])
        self.assertEqual([x["round"] for x in ts.second_review["rereviews"]], [1])
        self.assertIn("codex가 agy의 지적 1개를 함께 판정한다", out)
        line = self.report_line("NOTE R")
        self.assertIn("리뷰(agy)", line)
        self.assertIn(f"상태: {RESOLVED_NOTE}", line)
        self.assertIn(FIXED, self.report_line("FIX B"))

    def test_late_commit_reverting_the_second_fix_unresolves_the_lent_report_finding(self):
        """first: codex가 빌려 판정한 agy의 R도 늦은 커밋이 2차 수정을 되돌려 diff가 비면 unresolved다. agy 기록에는 2차 수정이 받은 지적이 없다."""
        set_rereview(self, "first")
        self.report_only_on_second()

        def revert(r, a):
            support.sh(a.wt, "git", "revert", "--no-edit", "HEAD")

        with at_call("_merge_stage", revert):
            self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        r = self.by_claim(self.ts().second_review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.UNRESOLVED, 2))
        self.assertIn("diff가 비었다", r["rereview_evidence"])
        self.assertIn("상태: 보고만", self.report_line("NOTE R"))

    def test_all_does_not_call_a_reviewer_with_only_report_findings(self):
        """all: report 지적만 가진 agy를 2차 재리뷰에 새로 부르지 않는다. R은 판정 없이 보고만이다."""
        self.report_only_on_second()
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 2)
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], False, None), (2, B["claim"], False, None)])
        r = self.by_claim(self.ts().second_review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, "", 0))
        self.assertIn("상태: 보고만", self.report_line("NOTE R"))

    def test_all_judges_the_report_finding_when_the_reviewer_is_called_anyway(self):
        """all: agy가 다른 지적(2차 수정이 받은 B)으로 불리면 그 호출이 자기 R도 판정한다. 호출 수는 R이 없을 때와 같다."""
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.new_finding("agy", 1, R)
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_B fixed_R")
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "agy 2", "codex 1", "codex 2"])
        self.assertEqual(self.listed("agy", 2), [(1, B["claim"], False, None), (2, R["claim"], True, None)])
        r = self.by_claim(self.ts().second_review, R)
        self.assertEqual(self.judged(r), (review.REPORT, 1, 0, review.RESOLVED, 2))
        self.assertNotIn("rereview_by", r)


class RuleTest(unittest.TestCase):
    """review.is_report_check·rereview_targets·report.finding_status를 state 모양으로 직접 본다."""

    def f(self, i, **kw):
        return {"id": i, "severity": "high", "location": "a", "claim": "c", "evidence": "e", **kw}

    def test_only_report_findings_of_the_first_rereview_in_the_second_round(self):
        rec = {"findings": [
            self.f(1, action=review.REPORT, found_round=1),
            self.f(2, action=review.REPORT, found_round=0),
            self.f(3, action=review.REPORT, found_round=2),
            self.f(4, action=review.REPORT, found_round=review.REPAIR_ROUND),
            self.f(5, action=review.DEFER, found_round=1),
            self.f(6, action=review.REPORT),  # 옛 state: found_round가 없다
        ]}
        self.assertEqual([f["id"] for f in review.rereview_targets(rec, 2)], [1])
        self.assertEqual(review.rereview_targets(rec, 1), [])
        self.assertEqual(review.fix_targets(rec, 2), [])

    def test_status_follows_the_verdict(self):
        base = self.f(1, action=review.REPORT, found_round=1)
        cases = [({}, "보고만"),
                 ({"rereview": review.RESOLVED, "rereview_round": 2, "rereview_evidence": "확인"}, RESOLVED_NOTE),
                 ({"rereview": review.UNRESOLVED, "rereview_round": 2}, "보고만"),
                 ({"rereview": review.UNCHECKED, "rereview_round": 2, "rereview_reason": review.REASON_FAILED}, "보고만")]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                self.assertEqual(report.finding_status({**base, **fields}), expected)
        first_review = self.f(2, action=review.REPORT, found_round=0, rereview=review.RESOLVED)
        self.assertEqual(report.finding_status(first_review), "보고만")

    def test_prompt_marks_report_findings_only_when_there_is_one(self):
        p = Path("x")
        for text in MARK:
            self.assertNotIn(text, review.rereview_prompt(p, p, p, p, p))
            self.assertIn(text, review.rereview_prompt(p, p, p, p, p, report_check=True))


if __name__ == "__main__":
    unittest.main()
