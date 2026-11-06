"""goldstack-v9 04: 2차 수정이 있었던 티켓의 2차 재리뷰는 앞서 resolved인 지적도 최종 커밋에서 다시 본다."""
import json
import unittest
from pathlib import Path
from unittest import mock

import support
import test_rereview
import test_review_target
from test_review_target import at_call, integration_moved, late_commit, merged_sha, stop
from test_second_review import finding

from gs import go, report, review, state

# 가짜 worker: n번째 수정 worker는 fix_<n>.sh를 worktree에서 돌리고 커밋한다. 수정을 정말 되돌릴 수 있다.
WORKER = """\
here="$(dirname "$0")"
echo "$GS_TICKET" >> "$here/calls.log"
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
  n=$(( $(cat "$here/fix.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/fix.n"
  echo "fix $GS_TICKET $n" >> "$here/fix.log"
  if [ -f "$here/fixfail_$n" ]; then echo bad > "bad$n"; git add -A; git commit -qm "bad fix $n"; exit 3; fi
  [ -f "$here/fix_$n.sh" ] && . "$here/fix_$n.sh"
  git add -A; git commit -q --allow-empty -m "fix $n"; exit 0
fi
echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
"""

# 가짜 reviewer: 판정을 미리 정하지 않고 트리를 읽는다. "FIX A: …" 지적은 fixed_A 파일이 있어야 고쳐진 것이다.
# refail_<who>_<n>: 그 호출이 실패한다. down_<who>: 그 값 이상의 호출이 끊긴다(up이 없는 동안).
# drop_<who>_<n>: 파일에 적은 id의 판정을 빼고 답한다.
# late_<who>_<n>.sh: 판정을 낸 뒤 worktree에 커밋이 생긴다(살아 남은 worker의 자손 흉내).
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
[ -f "$here/refail_${who}_$n" ] && { echo "boom $who" >&2; exit 1; }
"$PY" - "$listed" "$here/drop_${who}_$n" <<'PYEOF'
import json, os, sys
drop = open(sys.argv[2]).read().split() if os.path.exists(sys.argv[2]) else []
verdicts = []
for f in json.load(open(sys.argv[1]))["findings"]:
    if str(f["id"]) in drop:
        continue
    name = "fixed_" + f["claim"].split()[1].rstrip(":")
    there = os.path.exists(name)
    verdicts.append({"id": f["id"], "status": "resolved" if there else "unresolved",
                     "evidence": f"{name} {'있음' if there else '없음'}"})
print(json.dumps({"verdicts": verdicts, "findings": []}, ensure_ascii=False))
PYEOF
if [ -f "$here/late_${who}_$n.sh" ]; then . "$here/late_${who}_$n.sh"; git add -A; git commit -q --allow-empty -m "late $who $n"; fi
"""

A, B, C = finding("FIX A: 값이 틀렸다"), finding("FIX B: 경계값 누락", "medium"), finding("FIX C: 다른 값", "low")
FIXED, UNFIXED, UNKNOWN = "상태: 수정됨(재리뷰 확인)", "상태: 미해결", "상태: 확인 못 함"


class Base(test_rereview.Base):
    network_limit = test_review_target.Base.network_limit

    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.sh").write_text(REVIEWER)

    def plan(self, n, *commands):
        """n번째 수정 worker가 할 일."""
        (self.bin / f"fix_{n}.sh").write_text("\n".join(commands) + "\n")

    def a_fixed_first(self, *second):
        """1차 수정은 A만 고쳐 B가 남는다. 그래서 2차 수정이 돌고, 2차 수정은 B를 고치며 second를 한다."""
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_B", *second)

    def run_ok(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01"])
        return out

    def result(self, f):
        return f["fix_round"], f["rereview"], f["rereview_round"]

    def report_line(self, claim):
        [line] = [x for x in self.final_report().splitlines() if claim in x and "상태:" in x]
        return line

    def assert_second_fix_got_only_b(self):
        brief = (self.rundir / "01/1/fix2/brief.md").read_text()
        self.assertIn("FIX B", brief)
        self.assertNotIn("FIX A", brief)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])  # 수정 횟수 상한 2회 그대로다


class RevertTest(Base):
    def test_second_fix_reverting_a_makes_it_unresolved(self):
        self.findings("codex", A, B)
        self.a_fixed_first("rm fixed_A")
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assert_second_fix_got_only_b()
        self.assertNotIn("fixed_A", self.files())
        rec = self.ts().review
        a, b = rec["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual(a["rereview_evidence"], "fixed_A 없음")
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertEqual([f["claim"] for f in review.remaining(rec)], [A["claim"]])
        self.assertIn("남은 리뷰 지적 1", out)
        self.assertIn(UNFIXED, self.report_line("FIX A"))
        self.assertIn(FIXED, self.report_line("FIX B"))
        self.assertIn("리뷰 지적: 수정됨 1 · 미해결 1", self.final_report())

    def test_second_fix_keeping_a_leaves_it_fixed(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assert_second_fix_got_only_b()
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertIn("남은 리뷰 지적 0", out)
        self.assertIn(FIXED, self.report_line("FIX A"))
        self.assertIn("리뷰 지적: 수정됨 2", self.final_report())

    def test_reverted_finding_of_reviewer_without_second_targets(self):
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.a_fixed_first("rm fixed_A")
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "agy 2", "codex 1", "codex 2"])
        self.assert_second_fix_got_only_b()
        ts = self.ts()
        self.assertEqual(self.result(ts.review["findings"][0]), (1, review.UNRESOLVED, 2))
        self.assertEqual(self.result(ts.second_review["findings"][0]), (2, review.RESOLVED, 2))
        self.assertIn("리뷰(codex)", self.report_line("FIX A"))
        self.assertIn(UNFIXED, self.report_line("FIX A"))


class UncheckedTest(Base):
    def assert_not_counted_as_fixed(self, reason):
        self.assertIn(f"{UNKNOWN}({reason})", self.report_line("FIX A"))
        self.assertNotIn(FIXED, self.report_line("FIX A"))

    def test_failed_rereview_is_unchecked(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        (self.bin / "refail_codex_2").touch()
        self.run_ok()
        self.assert_second_fix_got_only_b()
        a, b = self.ts().review["findings"]
        for f in (a, b):
            self.assertEqual((f["rereview"], f["rereview_reason"], f["rereview_round"]),
                             (review.UNCHECKED, review.REASON_FAILED, 2))
        self.assert_not_counted_as_fixed(review.REASON_FAILED)
        self.assertNotIn("수정됨", self.final_report().split("리뷰 지적:")[1].splitlines()[0])

    def test_failure_of_reviewer_called_only_to_recheck_keeps_other_verdicts(self):
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.a_fixed_first()
        (self.bin / "refail_codex_2").touch()
        self.run_ok()
        ts = self.ts()
        a = ts.review["findings"][0]
        self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertEqual(ts.second_review["findings"][0]["rereview"], review.RESOLVED)
        self.assert_not_counted_as_fixed(review.REASON_FAILED)

    def test_agy_limit_is_unchecked_and_not_launched(self):
        self.limit(2)  # 첫 리뷰 + 1차 재리뷰로 다 쓴다
        self.two_reviewers()
        self.findings("agy", A)
        self.findings("codex", B)
        self.a_fixed_first()
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 2)
        ts = self.ts()
        a = ts.second_review["findings"][0]
        self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_LIMIT))
        self.assertEqual(ts.review["findings"][0]["rereview"], review.RESOLVED)
        self.assert_not_counted_as_fixed(review.REASON_LIMIT)

    def test_missing_verdict_is_unchecked(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        (self.bin / "drop_codex_2").write_text("1")  # 앞서 resolved인 A의 판정만 빠진 답이다
        self.run_ok()
        a, b = self.ts().review["findings"]
        self.assertEqual((a["rereview"], a["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertEqual(b["rereview"], review.RESOLVED)
        self.assert_not_counted_as_fixed(review.REASON_FAILED)


class NoRecheckTest(Base):
    def test_ticket_without_second_fix_keeps_rereview_calls(self):
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.plan(1, "touch fixed_A fixed_B")
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.run_state().agy_calls, 2)
        ts = self.ts()
        self.assertEqual(self.result(ts.review["findings"][0]), (1, review.RESOLVED, 1))
        self.assertEqual(self.result(ts.second_review["findings"][0]), (1, review.RESOLVED, 1))
        self.assertNotIn("recheck", (self.bin / "rereview.prompt.codex.1").read_text())
        self.assertNotIn("recheck", (self.bin / "rereview.findings.codex.1").read_text())

    def test_head_moving_twice_without_second_fix_keeps_verdict(self):
        """2차 수정이 없었던 티켓은 재확인 규칙 밖이다(spec 1-9). 판정도 호출 수도 그대로다."""
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        (self.bin / "late_codex_1.sh").write_text("touch late1\n")
        (self.bin / "late_codex_2.sh").write_text("touch late2\n")
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))

    def test_discarded_second_fix_keeps_first_verdict(self):
        self.findings("codex", A, B)
        self.a_fixed_first("rm fixed_A")
        (self.bin / "fixfail_2").touch()
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])  # 버린 수정은 최종 트리에 없다
        self.assertIn("fixed_A", self.files())
        self.assertNotIn("bad2", self.files())
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual((b["fix_round"], b["fix_attempt"], b["rereview"]), (2, review.DISCARDED, review.UNRESOLVED))
        self.assertIn(FIXED, self.report_line("FIX A"))
        self.assertIn(UNFIXED, self.report_line("FIX B"))

    def test_second_fix_that_cannot_start_keeps_first_verdict(self):
        self.limit(2)  # 구현 + 1차 수정으로 다 써서 2차 수정 worker를 띄우지 못한다
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", A, B)
        self.a_fixed_first()
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual((b["rereview"], b["fix_reason"]), (review.UNRESOLVED, review.REASON_LIMIT))

    def test_empty_second_fix_keeps_first_verdict_and_marks_only_received(self):
        self.findings("codex", A, B)
        self.plan(1, "touch fixed_A")
        self.plan(2, ":")  # 빈 커밋: 트리가 1차 재리뷰가 본 그대로다
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual(self.result(b), (2, review.UNRESOLVED, 2))
        self.assertIn("diff가 비었다", b["rereview_evidence"])

    def test_first_unchecked_and_report_findings_are_not_rechecked(self):
        self.two_reviewers()
        self.findings("codex", B)
        self.findings("agy", C, finding("설명이 짧다", "low"))
        self.plan(1, "touch unrelated")  # 아무 지적도 고치지 않는다: B는 unresolved
        self.plan(2, "touch fixed_B")
        (self.bin / "refail_agy_1").touch()
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        c, report_only = self.ts().second_review["findings"]
        self.assertEqual((c["rereview"], c["rereview_reason"], c["rereview_round"]),
                         (review.UNCHECKED, review.REASON_FAILED, 1))
        self.assertEqual((report_only["action"], report_only["rereview"]), (review.REPORT, ""))


class FinalCommitTest(Base):
    def test_commit_after_second_rereview_is_rechecked_at_new_head(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        (self.bin / "late_codex_2.sh").write_text("rm fixed_A\n")  # A가 resolved로 나온 뒤에 되돌린다
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        listed = json.loads((self.bin / "rereview.findings.codex.3").read_text())["findings"]
        self.assertEqual([(f["id"], f.get("recheck", False)) for f in listed], [(1, True), (2, False)])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertIn(UNFIXED, self.report_line("FIX A"))

    def test_head_moving_again_after_second_rereview_is_unchecked(self):
        """대조로 다시 본 뒤에도 head가 움직이면 아무도 브랜치 끝을 보지 않았다. 그 커밋은 병합에 들지 않고 판정은 수정됨으로 세지 않는다."""
        self.findings("codex", A, B)
        self.a_fixed_first()
        (self.bin / "late_codex_2.sh").write_text("touch late1\n")
        (self.bin / "late_codex_3.sh").write_text("rm fixed_A\n")
        out = self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])  # 더 부르지 않는다
        self.assert_second_fix_got_only_b()
        self.assertIn("fixed_A", self.files())  # A를 되돌린 늦은 커밋은 아무도 보지 않아 병합하지 않는다
        self.assertIn("경고: 병합 전 대조", out)
        rec = self.ts().review
        a, b = rec["findings"]
        for f in (a, b):
            self.assertEqual((f["rereview"], f["rereview_reason"], f["rereview_round"]),
                             (review.UNCHECKED, review.REASON_FAILED, 2))
        self.assertIn("재리뷰하지 못했다", a["rereview_evidence"])
        self.assertIn("fixed_A 있음", a["rereview_evidence"])  # 앞 head에서 본 근거도 남는다
        self.assertEqual(len(review.remaining(rec)), 2)
        for claim in ("FIX A", "FIX B"):
            self.assertIn(f"{UNKNOWN}({review.REASON_FAILED})", self.report_line(claim))
        self.assertNotIn("수정됨", self.final_report().split("리뷰 지적:")[1].splitlines()[0])

    def test_head_moving_again_keeps_unresolved(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        (self.bin / "late_codex_2.sh").write_text("rm fixed_A\n")
        (self.bin / "late_codex_3.sh").write_text("touch late2\n")
        self.run_ok()
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual((b["rereview"], b["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertIn(UNFIXED, self.report_line("FIX A"))

    def test_head_moving_again_unchecks_both_reviewers(self):
        self.limit(4)  # agy: 첫 리뷰 + 재리뷰 3번. 상한에 닿지 않아야 둘 다 resolved를 낸 뒤 내린다
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.a_fixed_first()
        (self.bin / "late_codex_2.sh").write_text("touch late1\n")
        (self.bin / "late_codex_3.sh").write_text("touch late2\n")
        self.run_ok()
        ts = self.ts()
        for f in (ts.review["findings"][0], ts.second_review["findings"][0]):
            self.assertEqual((f["rereview"], f["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))

    def test_abort_after_recheck_written_resumes_without_widening_second_fix(self):
        """2차 재리뷰가 A를 unresolved로 적은 뒤 끊겨도, 이어서 A를 2차 수정이 받은 지적으로 적지 않는다."""
        self.network_limit(1)
        self.findings("codex", A, B)
        self.a_fixed_first("rm fixed_A")
        (self.bin / "late_codex_2.sh").write_text("touch late\n")
        (self.bin / "down_codex").write_text("3")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        a, _ = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertTrue(self.ts().network_resume["done"])

        (self.bin / "up").touch()
        self.run_ok()
        self.assert_second_fix_got_only_b()
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertIn(UNFIXED, self.report_line("FIX A"))


class CatchUpEmptyDiffTest(Base):
    """goldstack-v19 01: catch-up이 a.base를 판정한 head 위로 옮긴다. 그 뒤의 빈 diff는 앞 판정을 뒤집지 않는다."""
    subject = test_review_target.Base.subject

    def wt(self):
        return self.rundir / "wt/01"

    def empty_late_commit(self, r, _t):
        support.sh(self.wt(), "git", "commit", "-q", "--allow-empty", "-m", "empty late")

    def assert_merged_the_empty_commit_over_the_catch_up(self):
        merged = merged_sha(self)
        self.assertEqual(self.subject(merged), "empty late")
        self.assertEqual(self.subject(f"{merged}^"), "gs: 최신 integration을 01에 합침")
        self.assertEqual(self.ts().review["reviewed_head"], merged)

    def run_with_empty_commit_after_catch_up(self):
        with at_call("_catch_up", integration_moved), at_call("_verify", self.empty_late_commit):
            return self.run_ok()

    def test_resolved_stands_and_no_second_fix(self):
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        self.run_with_empty_commit_after_catch_up()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])  # 바뀐 것이 없어 부르지 않는다
        rec = self.ts().review
        [a] = rec["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual(a["rereview_evidence"], "fixed_A 있음")
        self.assertIn("앞 판정을 유지", rec["fix"])
        self.assertIn(FIXED, self.report_line("FIX A"))
        self.assert_merged_the_empty_commit_over_the_catch_up()

    def test_second_rereview_verdicts_stand(self):
        self.findings("codex", A, B)
        self.a_fixed_first()
        self.run_with_empty_commit_after_catch_up()
        self.assert_second_fix_got_only_b()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assert_merged_the_empty_commit_over_the_catch_up()

    def test_verdicts_of_both_reviewers_stand(self):
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.plan(1, "touch fixed_A fixed_B")
        self.run_with_empty_commit_after_catch_up()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])
        ts = self.ts()
        self.assertEqual(self.result(ts.review["findings"][0]), (1, review.RESOLVED, 1))
        self.assertEqual(self.result(ts.second_review["findings"][0]), (1, review.RESOLVED, 1))

    def test_unchecked_stays_unchecked_and_sends_no_second_fix(self):
        self.findings("codex", A, B)
        self.plan(1, "touch fixed_A fixed_B")
        (self.bin / "drop_codex_1").write_text("2")  # B의 판정만 빠진 답이다: 고쳐졌는지 모른다
        self.run_with_empty_commit_after_catch_up()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual((b["rereview"], b["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertNotIn("diff가 비었다", b["rereview_evidence"])

    def test_fix_that_could_not_start_is_not_tried_again(self):
        self.limit(2)  # 구현 + 1차 수정으로 다 써서 2차 수정 worker를 띄우지 못한다
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", A, B)
        self.a_fixed_first()
        limits = []
        real = go._skip_fix

        def counted(*args, **kw):
            limits.append(args[2])
            return real(*args, **kw)

        with at_call("_catch_up", integration_moved), at_call("_verify", self.empty_late_commit), \
                mock.patch.object(go, "_skip_fix", side_effect=counted):
            self.run_ok()
        self.assertEqual(limits, [2])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual((b["rereview"], b["fix_reason"]), (review.UNRESOLVED, review.REASON_LIMIT))

    def test_resumed_look_after_catch_up_keeps_the_verdict(self):
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        with at_call("_catch_up", integration_moved), at_call("_verify", self.empty_late_commit), \
                at_call("_rereview", None, stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertEqual(self.subject(self.ts().network_resume["base"]), "gs: 최신 integration을 01에 합침")
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assert_merged_the_empty_commit_over_the_catch_up()

    def stopped_right_after_keeping_the_verdict(self):
        """빈 diff에서 판정을 유지해 저장한 직후 멈춘다. 대조는 아직 끝나지 않았다(세 번째 _moved_head가 _review_again의 것이다)."""
        with at_call("_catch_up", integration_moved), at_call("_verify", self.empty_late_commit), \
                at_call("_moved_head", None, None, stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        ts = self.ts()
        mark = ts.network_resume
        self.assertTrue(mark["reviewed_again"])
        self.assertNotIn("reviewed", mark)
        self.assertEqual(self.subject(ts.review["reviewed_head"]), "empty late")
        self.assertEqual(ts.review["findings"][0]["rereview"], review.RESOLVED)

    def test_stopped_right_after_keeping_the_verdict_keeps_it(self):
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        self.stopped_right_after_keeping_the_verdict()
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual(a["rereview_evidence"], "fixed_A 있음")
        self.assert_merged_the_empty_commit_over_the_catch_up()

    def test_another_empty_commit_while_stopped_keeps_the_verdict(self):
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        self.stopped_right_after_keeping_the_verdict()
        support.sh(self.wt(), "git", "commit", "-q", "--allow-empty", "-m", "empty later")
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual(self.subject(merged_sha(self)), "empty later")

    def test_stopped_after_the_kept_look_sends_no_second_fix(self):
        """대조가 끝나 표시가 reviewed다. 2차 수정을 못 띄운 B의 unresolved가 남았어도 다음 gs go가 띄우지 않는다. 상한은 실행마다라 이번에는 띄울 수 있다."""
        self.limit(2)  # 구현 + 1차 수정으로 다 써서 2차 수정 worker를 띄우지 못한다
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", A, B)
        self.a_fixed_first()
        with at_call("_catch_up", integration_moved), at_call("_verify", self.empty_late_commit), \
                at_call("_leave_review", None, None, stop), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertTrue(self.ts().network_resume["reviewed"])
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertEqual((b["rereview"], b["fix_reason"]), (review.UNRESOLVED, review.REASON_LIMIT))

    def test_new_verdict_after_a_kept_one_can_send_the_second_fix(self):
        """유지한 뒤 멈춘 사이 진짜 커밋이 생겼으면 대조가 그것을 판정한다. 유지 기록은 그 판정을 막지 않는다: B가 unresolved면 2차 수정으로 간다. 상한은 실행마다라 이번에는 띄울 수 있다."""
        self.limit(2)  # 구현 + 1차 수정으로 다 써서 첫 실행은 2차 수정 worker를 띄우지 못하고 병합 단계로 간다
        self.tickets(**{"01": ("agy", "codex", None, "[]")})
        self.findings("codex", A, B)
        self.a_fixed_first()
        self.stopped_right_after_keeping_the_verdict()
        late_commit("late", self.wt())(None, None)
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assert_second_fix_got_only_b()
        self.assertNotIn("kept_round", self.ts().review)

    def test_finding_without_a_verdict_is_unresolved_as_before(self):
        """버린 수정의 지적은 앞서 판정이 없다. catch-up 뒤에도 빈 diff 처리는 전과 같다."""
        self.findings("codex", A)
        (self.bin / "fixfail_1").touch()
        self.run_with_empty_commit_after_catch_up()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        self.assertEqual(self.lines("rereview.calls"), [])
        rec = self.ts().review
        [a] = rec["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 1))
        self.assertIn("diff가 비었다", a["rereview_evidence"])
        self.assertIn("비어 부르지 않았다(unresolved)", rec["fix"])

    def test_late_commit_reverting_the_fix_is_unresolved_without_catch_up(self):
        """catch-up이 없으면 빈 diff는 수정이 사라졌다는 뜻이다. resolved여도 지금처럼 뒤집고 2차 수정으로 간다."""
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_A")

        def revert(r, a):
            support.sh(a.wt, "git", "revert", "--no-edit", "HEAD")

        with at_call("_merge_stage", revert):
            self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (2, review.RESOLVED, 2))
        self.assertIn("fixed_A", self.files())

    def test_nonempty_late_commit_after_catch_up_is_rereviewed(self):
        self.findings("codex", A)
        self.plan(1, "touch fixed_A")
        with at_call("_catch_up", integration_moved), at_call("_verify", late_commit("late", self.wt())):
            self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])
        [a] = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.RESOLVED, 1))
        self.assertNotIn("앞 판정을 유지", self.ts().review["fix"])


class OldStateTest(Base):
    def test_old_state_resumes_second_rereview_and_rechecks(self):
        self.network_limit(1)
        self.findings("codex", A, B)
        self.a_fixed_first("rm fixed_A")
        (self.bin / "down_codex").write_text("2")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        # 이 기능 전의 gs가 남긴 state처럼 만든다: 재확인을 적은 흔적이 없고 2차 재리뷰가 아직 없다
        raw = json.loads(state.path(self.rundir).read_text())
        rec = raw["tickets"]["01"]["review"]
        self.assertEqual(raw["tickets"]["01"]["network_resume"]["fix"], 2)
        self.assertEqual([x["round"] for x in rec["rereviews"]], [1])
        self.assertEqual((rec["findings"][0]["rereview"], rec["findings"][0]["rereview_round"]), (review.RESOLVED, 1))
        rec.pop("reviewed_head")
        state.path(self.rundir).write_text(json.dumps(raw))

        (self.bin / "up").touch()
        self.run_ok()
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])  # 수정 worker를 다시 띄우지 않는다
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))

    def test_old_records_are_read_without_new_fields(self):
        """재리뷰 도입 전·중의 지적 모양. 빠진 값 때문에 깨지거나 재확인 대상이 되지 않는다(resolved 판정만 다시 본다)."""
        before_rereview = {"id": 1, "severity": "high", "location": "a", "claim": "c", "evidence": "e",
                           "action": "fix", "why": "w", "fix_attempt": "attempted"}
        report_only = {"id": 2, "severity": "low", "location": "a", "claim": "c", "evidence": "", "action": "report"}
        no_round = {"id": 3, "severity": "high", "location": "a", "claim": "c", "evidence": "e",
                    "action": "fix", "rereview": "resolved"}
        rereview_round_one = {**before_rereview, "id": 4, "fix_round": 1, "rereview": "unresolved", "rereview_round": 1}
        rec = {"reviewer": "codex", "findings": [before_rereview, report_only, no_round, rereview_round_one]}
        self.rundir.mkdir(parents=True)
        state.path(self.rundir).write_text(json.dumps({"feature": "demo", "tickets": {"01": {"status": "pending", "review": rec}}}))
        loaded = state.load(self.rundir, "demo").tickets["01"].review
        self.assertEqual([f["id"] for f in review.fix_targets(loaded, 2)], [4])
        self.assertEqual([f["id"] for f in review.rereview_targets(loaded, 2)], [3])
        self.assertEqual([f["id"] for f in review.rereview_targets(loaded, 1)], [4])
        self.assertEqual(report.finding_status(no_round), "수정됨(재리뷰 확인)")


class TargetsTest(unittest.TestCase):
    """2차 수정이 받는 대상(fix_targets)과 2차 재리뷰가 볼 대상(rereview_targets)은 다르다."""

    def findings(self):
        return [
            {"id": 1, "action": "fix", "fix_round": 1, "rereview": "resolved", "rereview_round": 1},  # 다시 본다
            {"id": 2, "action": "fix", "fix_round": 1, "rereview": "unresolved", "rereview_round": 1},  # 2차 대상
            {"id": 3, "action": "fix", "fix_round": 1, "rereview": "unchecked", "rereview_round": 1},  # 확인된 적 없다
            {"id": 4, "action": "report", "found_round": 1},
            {"id": 5, "action": "fix", "found_round": 1},  # 1차 재리뷰의 새 fix 지적: 2차 대상
        ]

    def ids(self, found):
        return [f["id"] for f in found]

    def test_before_second_fix(self):
        rec = {"findings": self.findings()}
        self.assertEqual(self.ids(review.fix_targets(rec, 2)), [2, 5])
        self.assertEqual(self.ids(review.rereview_targets(rec, 2)), [1])  # 받은 지적은 수정 worker가 커밋한 뒤 fix_round가 2다
        self.assertEqual(self.ids(review.fix_targets(rec, 1)), [1, 2, 3, 5])

    def test_second_round_stays_the_same_whatever_the_verdicts(self):
        for verdict in (review.RESOLVED, review.UNRESOLVED, review.UNCHECKED):
            with self.subTest(verdict=verdict):
                fs = self.findings()
                for f in (fs[1], fs[4]):
                    f["fix_round"] = 2
                for f in (fs[0], fs[1], fs[4]):
                    f.update(rereview=verdict, rereview_round=2)
                rec = {"findings": fs}
                self.assertEqual(self.ids(review.rereview_targets(rec, 2)), [1, 2, 5])
                self.assertNotIn(1, self.ids(review.fix_targets(rec, 2)))

    def test_first_round_has_no_recheck(self):
        rec = {"findings": self.findings()}
        self.assertEqual(self.ids(review.rereview_targets(rec, 1)), [1, 2, 3])
        self.assertFalse(any(review.is_recheck(f, 1) for f in rec["findings"]))

    def test_prompt_mentions_recheck_only_when_there_is_one(self):
        p = Path("x")
        self.assertNotIn("recheck", review.rereview_prompt(p, p, p, p, p))
        self.assertIn("`recheck`", review.rereview_prompt(p, p, p, p, p, recheck=True))


if __name__ == "__main__":
    unittest.main()
