"""goldstack-v36 03: 수정 한도를 다 쓴 뒤 마지막 재리뷰(2차 재리뷰·수리 재리뷰)에 high가 남으면 병합하지 않고 티켓 실패다(spec 1-6·1-7·3-2).

가짜 리뷰어는 support.GoTest 계열의 것을 쓴다: 2차 재리뷰는 test_rereview의 리뷰어(회차마다 답 파일), 수리 재리뷰는 test_verify_repair의 리뷰어.
재시도 worker는 brief의 `## 지난 시도 실패 요약`으로 알아보고, clean_retry가 있으면 첫 리뷰 지적 파일을 지워 다음 시도가 깨끗하게 병합되게 한다.
재개 시험은 결과를 처음 저장한 직후(state.save)나 결과만 남은 state(재개의 reviewed·REPAIR_VERIFY)에서 gs를 멈추고 다시 gs go를 돈다.
"""
import unittest
from unittest import mock

import support
import test_rereview
import test_verify_repair
from test_review_target import at_call, late_commit
from test_second_review import finding
from test_verify_repair import BREAKS, GOOD, REPAIRS

from gs import go, review, state

RETRY = """\
if grep -q '^## 지난 시도 실패 요약' "$GS_BRIEF"; then
  cp "$GS_BRIEF" "$here/retry_brief"
  [ -f "$here/clean_retry" ] && rm -f "$here"/findings_*.json
fi
"""
CALLS = 'echo "$GS_TICKET" >> "$here/calls.log"\n'
assert test_rereview.WORKER.count(CALLS) == 1
WORKER = test_rereview.WORKER.replace(CALLS, CALLS + RETRY)

# 실패 이유에는 앞 200자만 싣는다(review.FINAL_HIGH_CLAIM_CHARS). 전문은 failure.log에 들어가야 한다
LONG_CLAIM = "회귀: 2차 수정이 1차 수정에서 막던 우회를 다시 열었다. " + "자세한 경로 설명 " * 30 + "끝문장"
EVIDENCE = "GS_ROLE=worker로 hook.decide를 불러 `gs child -- git push`가 통과하는 것을 재현했다"
NEW_HIGH = finding(LONG_CLAIM, "high", EVIDENCE)


def blocked_save(test, pick):
    """state.save를 감싼다: pick(state)이 처음 참인 저장을 마친 직후 gs가 죽는다(KeyboardInterrupt)."""
    real, seen = state.save, []

    def save(rundir, st):
        real(rundir, st)
        if not seen and pick(st):
            seen.append(1)
            raise KeyboardInterrupt

    return mock.patch.object(state, "save", side_effect=save)


def recording(name, *fields):
    """go.<name>(r, x, …)을 감싼다. x(Active 또는 Reviewing)의 (시도 번호, *fields)를 부를 때마다 적는다. (patch, 적은 목록)."""
    real, seen = getattr(go, name), []

    def wrapper(r, x, *rest, **kw):
        a = getattr(x, "a", x)
        seen.append((go._attempt_dir(a).name, *(getattr(a, f) for f in fields)))
        return real(r, x, *rest, **kw)

    return mock.patch.object(go, name, side_effect=wrapper), seen


def has_final_high(st):
    return bool(review.final_highs(state.reviews(st.tickets["01"]))) if "01" in st.tickets else False


def again_saved(st):
    """병합 전 대조로 다시 부른 2차 재리뷰(1차 + 2차 + 2차 다시, 재리뷰 세 번)의 결과에 남은 high가 있는 저장."""
    return has_final_high(st) and len((st.tickets["01"].review or {}).get("rereviews", [])) == 3


def late_during_second_rereview():
    """2차 재리뷰의 결과를 반영하기 직전에 티켓 worktree에 늦은 커밋이 생긴다(살아 남은 worker 자손 흉내). 1차 재리뷰는 그대로다."""
    commit = late_commit("late")
    return at_call("_apply_rereviews", None, lambda r, a, *_: commit(r, a))


class SecondRereviewBase(test_rereview.Base):
    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(WORKER)

    def second_rereview(self, *new, verdict=("resolved", "A 고침")):
        """1차 재리뷰가 A를 미해결로 봐 2차 수정이 돌고, 2차 재리뷰는 A에 verdict를 내고 new를 새로 낸다."""
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")])
        self.answer("codex", 2, [(1, *verdict)], list(new))

    def worker_tiers(self):
        return [(p["attempt"], p["tier"]) for p in self.ts().phases if p["phase"] == "worker"]

    def assert_not_merged_and_retried(self, out, reason):
        """첫 시도는 병합되지 않고 실패 1로 재시도해 다음 시도가 병합됐다."""
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.merged(), ["01"])
        self.assertNotIn("fix2_01", self.files())  # 첫 시도의 2차 수정은 병합되지 않았다
        self.assertEqual(self.worker_tiers(), [(1, "medium"), (2, "large")])  # 실패처럼 등급을 올렸다
        self.assertIn(f"[01] 실패: {reason}", out)
        self.assertIn("한 번 재시도", out)
        self.assertEqual(ts.failed_worktrees, [str(self.rundir / "wt/01")])
        self.assertIn("## 지난 시도 실패 요약", (self.bin / "retry_brief").read_text())


class SecondRereviewHighTest(SecondRereviewBase):
    def test_new_high_is_not_merged_and_the_ticket_is_retried(self):
        self.second_rereview(NEW_HIGH)
        (self.bin / "clean_retry").touch()
        leave, left = recording("_leave_review", "fix")
        merge, merging = recording("_merge_stage", "fix")
        with leave, merge:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        # 실패를 적으면 그 시도의 리뷰 흐름이 끝난다: 2차 재리뷰 뒤로 리뷰 단계를 떠나거나 병합 단계로 가지 않는다
        self.assertEqual(left, [("1", 0), ("1", 1), ("2", 0)])
        self.assertEqual(merging, [("2", 0)])
        reason = f"남은 high: file_01 {LONG_CLAIM[:review.FINAL_HIGH_CLAIM_CHARS]}…"
        self.assert_not_merged_and_retried(out, reason)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2"])  # 세 번째 수정은 없다
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertFalse((self.rundir / "01/1/rereview2-codex/findings.json").exists())  # 판단 모델을 더 부르지 않았다
        # 실패 요약 입력(failure.log)에 그 high 지적 전문이 들어간다
        log = (self.rundir / "01/1/fix2/failure.log").read_text()
        self.assertIn(f"실패 이유: {reason}", log)
        self.assertIn(f"## {self.rundir / '01/1/fix2' / review.FINAL_HIGH_FILE} (", log)
        self.assertIn(LONG_CLAIM, log)
        self.assertIn(EVIDENCE, log)
        self.assertIn("2차 재리뷰의 새 지적", log)
        self.assertIn(str(self.rundir / "01/1/fix2/failure.log"), (self.bin / "retry_brief").read_text())
        # 실패한 시도의 지적은 보존된다. 그 high는 2차 재리뷰가 판단 모델 없이 report로 적은 그대로다
        [prior] = self.ts().prior_findings
        high = prior["findings"][-1]
        self.assertEqual((high["found_round"], high["action"], high["severity"]), (2, review.REPORT, "high"))
        self.assertIn("병합하지 않고", high["why"])

    def test_retry_with_a_new_high_again_fails_the_ticket(self):
        self.second_rereview(NEW_HIGH)
        self.answer("codex", 3, [(1, "unresolved", "그대로다")])
        self.answer("codex", 4, [(1, "resolved", "A 고침")], [finding("또 다른 회귀", "high", "재현")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 2, 2))
        self.assertEqual(self.merged(), [])
        self.assertEqual(ts.reason, "남은 high: file_01 또 다른 회귀")
        self.assertEqual(ts.network_resume, {})
        self.assertEqual(self.lines("fix.log"), ["fix 01 1", "fix 01 2", "fix 01 3", "fix 01 4"])

    def test_dependent_ticket_is_blocked_like_any_failure(self):
        """support.GoTest의 04는 01에 막힌다. 다른 리뷰 단계 실패처럼 04는 시작하지 않는다."""
        self.second_rereview(NEW_HIGH)
        self.answer("codex", 3, [(1, "unresolved", "그대로다")])
        self.answer("codex", 4, [(1, "resolved", "A 고침")], [NEW_HIGH])
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.ts().status, "failed")
        self.assertEqual(self.merged(), [])
        self.assertNotEqual(self.ts("04").status, "merged")
        self.assertNotIn("04", self.calls())

    def test_several_highs_name_the_first_and_count_the_rest(self):
        self.two_reviewers()
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.findings("agy", finding("FIX B: 경계값 누락", "medium"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")])
        self.answer("agy", 1, [(1, "resolved", "고침")])
        self.answer("codex", 2, [(1, "unresolved", "또 그대로다")], [finding("새 회귀", "high", "재현")])
        self.answer("agy", 2, [(1, "resolved", "그대로 고쳐져 있다")], [finding("agy가 본 회귀", "high", "재현")])
        (self.bin / "clean_retry").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        # 새 high가 먼저, 미해결 high가 뒤다. 리뷰어 하나라도 내면 센다
        self.assert_not_merged_and_retried(out, "남은 high: file_01 새 회귀 외 2개")
        text = (self.rundir / "01/1/fix2" / review.FINAL_HIGH_FILE).read_text()
        for line in ("새 회귀", "agy가 본 회귀", "FIX A: 값이 틀렸다", "또 그대로다", "## 3. codex · 2차 재리뷰가 미해결로 판정한 지적"):
            self.assertIn(line, text)


class UnresolvedHighTest(SecondRereviewBase):
    def test_unresolved_high_is_not_merged_and_the_ticket_is_retried(self):
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        (self.bin / "clean_retry").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_not_merged_and_retried(out, "남은 high: file_01 FIX A: 값이 틀렸다 (미해결)")
        log = (self.rundir / "01/1/fix2/failure.log").read_text()
        self.assertIn("2차 재리뷰가 미해결로 판정한 지적", log)
        self.assertIn("2차 재리뷰 판정 근거: 또 그대로다", log)

    def test_retry_unresolved_again_fails_the_ticket(self):
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        self.answer("codex", 3, [(1, "unresolved", "그대로다")])
        self.answer("codex", 4, [(1, "unresolved", "끝내 그대로다")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.reason), ("failed", 2, "남은 high: file_01 FIX A: 값이 틀렸다 (미해결)"))
        self.assertEqual(self.merged(), [])

    def test_resolved_high_found_unresolved_on_the_recheck_counts(self):
        """1차 재리뷰가 resolved로 본 high를 2차 재리뷰가 최종 커밋에서 다시 보고 unresolved로 판정했다(2차 수정이 되돌렸다)."""
        self.findings("codex", finding("FIX A: 값이 틀렸다"), finding("FIX B: 경계값", "medium"))
        self.answer("codex", 1, [(1, "resolved", "A 고침"), (2, "unresolved", "B 그대로")])
        self.answer("codex", 2, [(1, "unresolved", "2차 수정이 A를 되돌렸다"), (2, "resolved", "B 고침")])
        (self.bin / "clean_retry").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_not_merged_and_retried(out, "남은 high: file_01 FIX A: 값이 틀렸다 (미해결)")

    def test_unchecked_high_is_merged(self):
        self.second_rereview()
        (self.bin / "rereview_codex_2.json").unlink()  # 2차 재리뷰의 답이 형식에 맞지 않는다: unchecked(재리뷰 실패)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("fix2_01", self.files())
        [a] = ts.review["findings"]
        self.assertEqual((a["severity"], a["rereview"], a["rereview_round"]), ("high", review.UNCHECKED, 2))
        self.assertNotIn("남은 high:", out)

    def test_unresolved_high_of_the_first_rereview_without_a_second_rereview_is_merged(self):
        """2차 수정이 실패해 2차 재리뷰가 없었다. 1차 재리뷰의 미해결은 이 판정에 들지 않는다."""
        self.second_rereview()
        (self.bin / "fixfail_2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.ts().status, self.ts().failures), ("merged", 0))
        self.assertEqual(self.lines("rereview.calls"), ["codex 1"])


class ReportOnlyTest(SecondRereviewBase):
    def test_medium_and_low_of_the_second_rereview_are_report_only_as_before(self):
        self.second_rereview(finding("이름이 모호하다", "medium"), finding("오타", "low"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("fix2_01", self.files())
        self.assertIn("남은 리뷰 지적 2", out)
        self.assertEqual([(f["found_round"], f["action"], f["why"]) for f in ts.review["findings"][1:]],
                         [(2, review.REPORT, "2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다")] * 2)

    def test_high_reported_by_the_judge_in_earlier_rounds_is_report_only_as_before(self):
        """첫 리뷰와 1차 재리뷰에서 판단 모델이 report로 나눈 high는 지금처럼 보고만이다(첫 리뷰 분류는 범위 밖)."""
        self.findings("codex", finding("FIX A: 값이 틀렸다"), finding("첫 리뷰의 high", "high"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")], [finding("1차 재리뷰의 high", "high")])
        self.answer("codex", 2, [(1, "resolved", "고침")])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures), ("merged", 0))
        self.assertEqual([(f["claim"], f["action"]) for f in ts.review["findings"]],
                         [("FIX A: 값이 틀렸다", "fix"), ("첫 리뷰의 high", review.REPORT), ("1차 재리뷰의 high", review.REPORT)])
        self.assertIn("남은 리뷰 지적 2", out)


class SecondRereviewResumeTest(SecondRereviewBase):
    def test_stopped_right_after_the_results_are_saved(self):
        self.second_rereview(NEW_HIGH)
        (self.bin / "clean_retry").touch()
        with blocked_save(self, has_final_high), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])  # 끝난 재리뷰를 다시 부르지 않는다
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertNotIn("fix2_01", self.files())

    def test_results_left_with_the_reviewed_mark_are_not_merged(self):
        """판정 없이 결과만 저장하고 리뷰 단계를 끝낸 state(옛 gs와 같다)에서 멈췄다. 다음 gs go가 reviewed로 이어도 병합하지 않는다."""
        self.second_rereview(NEW_HIGH)
        (self.bin / "clean_retry").touch()
        real = go._leave_review

        def leave(r, rv, active, runner):
            if rv.a.fix == 2:
                raise KeyboardInterrupt
            return real(r, rv, active, runner)

        with mock.patch.object(go, "_final_high", return_value=None), mock.patch.object(go, "_leave_review", side_effect=leave), \
                self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        ts = self.ts()
        self.assertTrue(ts.network_resume["reviewed"])
        self.assertEqual((ts.status, ts.failures), ("running", 0))
        self.assertTrue(review.final_highs(state.reviews(ts)))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("지난 리뷰는 끝났다", out)
        self.assertIn("[01] 실패: 남은 high: file_01", out)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertNotIn("fix2_01", self.files())
        self.assertIn(EVIDENCE, (self.rundir / "01/1/fix2/failure.log").read_text())

    def test_unresolved_high_saved_before_a_stop_is_not_rereviewed(self):
        """2차 재리뷰가 A를 unresolved로 적고 저장한 직후 멈췄다. 다음 gs go는 리뷰부터 잇지만 같은 head의 리뷰어를 다시 부르지 않는다:
        다시 부른 재리뷰가 실패하면(여기선 답 파일이 없다) unresolved가 unchecked로 덮여 병합된다."""
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        (self.bin / "clean_retry").touch()
        with blocked_save(self, has_final_high), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.network_resume["fix"]), ("running", 0, 2))
        self.assertFalse(ts.network_resume.get("reviewed"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("리뷰부터 잇는다", out)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertIn("[01] 실패: 남은 high: file_01 FIX A: 값이 틀렸다 (미해결)", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertNotIn("fix2_01", self.files())

    def test_stopped_after_the_check_again_saved_its_results(self):
        """병합 전 대조로 다시 부른 2차 재리뷰가 결과를 저장한 직후 멈췄다(reviewed_again). 다음 gs go는 그 head를 다시 부르지 않는다."""
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        self.answer("codex", 3, [(1, "unresolved", "늦은 커밋도 고치지 않았다")])
        (self.bin / "clean_retry").touch()
        with late_during_second_rereview(), blocked_save(self, again_saved), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertTrue(self.ts().network_resume["reviewed_again"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assertIn("[01] 실패: 남은 high: file_01 FIX A: 값이 틀렸다 (미해결)", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertNotIn("late", self.files())


class SecondRereviewLateCommitTest(SecondRereviewBase):
    def test_late_commit_is_checked_before_the_judgment(self):
        """2차 재리뷰 도중 생긴 늦은 커밋이 A를 고쳤다. 병합 전 대조가 그 head에서 다시 본 판정(resolved)으로 정하고 병합한다."""
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        self.answer("codex", 3, [(1, "resolved", "늦은 커밋이 고쳤다")])
        with late_during_second_rereview():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("late", self.files())
        [a] = ts.review["findings"]
        self.assertEqual((a["rereview"], a["rereview_round"], a["rereview_evidence"]), (review.RESOLVED, 2, "늦은 커밋이 고쳤다"))
        self.assertNotIn("남은 high:", out)

    def test_late_commit_that_leaves_the_high_fails_after_the_check(self):
        self.second_rereview(verdict=("unresolved", "또 그대로다"))
        self.answer("codex", 3, [(1, "unresolved", "늦은 커밋도 고치지 않았다")])
        (self.bin / "clean_retry").touch()
        with late_during_second_rereview():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        self.assert_not_merged_and_retried(out, "남은 high: file_01 FIX A: 값이 틀렸다 (미해결)")
        self.assertIn("늦은 커밋도 고치지 않았다", (self.rundir / "01/1/fix2/failure.log").read_text())


class RepairReviewBase(test_verify_repair.Base):
    reviewer = test_verify_repair.RepairReviewTest.reviewer

    def repair_commit_merged(self):
        return "repair 01" in self.integration("log", "--format=%s", "gs/demo/integration")


class RepairReviewHighTest(RepairReviewBase):
    def test_high_of_the_repair_review_is_not_merged_and_the_ticket_is_retried(self):
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        self.reviewer(NEW_HIGH)
        leave, left = recording("_leave_review", "repair")
        merge, merging = recording("_merge_stage", "repair")
        with leave, merge:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        # 수리 재리뷰 뒤로 리뷰 단계를 떠나 다시 검증(REPAIR_VERIFY)으로 가지 않는다
        self.assertEqual(left, [("1", ""), ("1", go.REPAIR_SEAT), ("2", "")])
        self.assertEqual(merging, [("1", ""), ("2", "")])
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertFalse(self.repair_commit_merged())
        reason = f"남은 high: file_01 {LONG_CLAIM[:review.FINAL_HIGH_CLAIM_CHARS]}…"
        self.assertIn(f"[01] 실패: {reason}", out)
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])  # 수리 뒤 다시 검증하지 않았다
        tiers = [(p["attempt"], p["phase"], p["tier"]) for p in ts.phases if p["phase"] in ("worker", "repair")]
        self.assertEqual(tiers, [(1, "worker", "medium"), (1, "repair", "medium"), (2, "worker", "large")])
        [rec] = ts.repairs
        self.assertEqual((rec["worker"], rec["result"], rec["detail"]), ("커밋 1개", state.REPAIR_FAILED, reason))
        log = (self.rundir / "01/1/repair/failure.log").read_text()
        self.assertIn(LONG_CLAIM, log)
        self.assertIn(EVIDENCE, log)
        self.assertIn("수리 재리뷰의 새 지적", log)
        self.assertIn("## 지난 시도 실패 요약", (self.rundir / "01/2/brief.md").read_text())
        [prior] = ts.prior_findings
        self.assertEqual([(f["found_round"], f["action"]) for f in prior["findings"]], [(review.REPAIR_ROUND, review.REPORT)])
        self.assertIn("[01] 수리 재리뷰: 지적 1개(high 1: 병합하지 않는다) (codex)", out)

    def test_repair_review_high_again_fails_the_ticket(self):
        self.worker(BREAKS, REPAIRS)
        self.reviewer(finding("수리가 시험을 지웠다", "high", "재현"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 2, 2))
        self.assertEqual(ts.reason, "남은 high: file_01 수리가 시험을 지웠다")
        self.assertEqual(self.merged(), [])
        self.assertEqual([r["result"] for r in ts.repairs], [state.REPAIR_FAILED] * 2)
        self.assertIn("수리 재리뷰: 지적 1개(high 1: 병합하지 않는다)", ts.review["fix"])

    def test_medium_of_the_repair_review_is_report_only_as_before(self):
        self.worker(BREAKS, REPAIRS)
        self.reviewer(finding("이름이 모호하다", "medium"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertTrue(self.repair_commit_merged())
        self.assertIn("수리 재리뷰: 지적 1개(보고만)", ts.review["fix"])


class RepairReviewResumeTest(RepairReviewBase):
    def test_stopped_right_after_the_results_are_saved(self):
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        self.reviewer(NEW_HIGH)
        with blocked_save(self, has_final_high), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertFalse(self.repair_commit_merged())
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])  # 첫 리뷰, 수리 재리뷰, 새 시도의 첫 리뷰. 수리 재리뷰를 다시 부르지 않는다

    def test_results_left_with_the_verify_mark_are_not_merged(self):
        """판정 없이 결과만 저장하고 다시 검증(REPAIR_VERIFY) 차례에서 멈춘 state(옛 gs와 같다). 다음 gs go가 다시 검증부터 이어도 병합하지 않는다."""
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        self.reviewer(NEW_HIGH)
        with mock.patch.object(go, "_final_high", return_value=None):
            self.stop_at_verify()
        ts = self.ts()
        self.assertEqual((ts.network_resume["repair"], ts.network_resume["done"], ts.failures), (go.REPAIR_VERIFY, True, 0))
        self.assertTrue(review.final_highs(state.reviews(ts)))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("다시 검증부터", out)
        self.assertIn("[01] 실패: 남은 high: file_01", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertFalse(self.repair_commit_merged())
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])  # 수리 재리뷰를 다시 부르지 않는다
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_FAILED)
        self.assertIn(EVIDENCE, (self.rundir / "01/1/repair/failure.log").read_text())

    def test_late_commit_while_stopped_is_rereviewed_before_the_judgment(self):
        """다시 검증 차례(REPAIR_VERIFY)에서 멈춘 사이 늦은 커밋이 생겼다. 병합 단계는 남은 high로 바로 실패시키지 않고 먼저 그 커밋을 재리뷰로 보낸다."""
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        self.reviewer(NEW_HIGH)
        with mock.patch.object(go, "_final_high", return_value=None):
            self.stop_at_verify()
        wt = self.rundir / "wt/01"
        (wt / "late").write_text("late\n")
        support.sh(wt, "git", "add", "-A")
        support.sh(wt, "git", "commit", "-qm", "late")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("마지막으로 리뷰한 head와 달라 다시 리뷰한다", out)
        # 첫 리뷰, 수리 재리뷰, 늦은 커밋의 수리 재리뷰, 새 시도의 첫 리뷰
        self.assertEqual(self.reviewers(), ["codex"] * 4)
        self.assertIn("[01] 실패: 남은 high: file_01", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertFalse(self.repair_commit_merged())


class FormatTest(unittest.TestCase):
    """review.final_highs·final_high_reason: 어떤 high를 세고 이유를 어떻게 적나."""

    def f(self, i, severity="high", found_round=0, rereview="", rereview_round=0, action=review.REPORT, claim=None):
        return {"id": i, "severity": severity, "location": f"a.py:{i}", "claim": claim or f"지적 {i}", "evidence": "e",
                "action": action, "found_round": found_round, "rereview": rereview, "rereview_round": rereview_round}

    def test_what_counts(self):
        counted = [self.f(1, found_round=2), self.f(2, found_round=review.REPAIR_ROUND),
                   self.f(3, action="fix", rereview=review.UNRESOLVED, rereview_round=2)]
        ignored = [self.f(4, "medium", found_round=2), self.f(5, "low", found_round=review.REPAIR_ROUND),
                   self.f(6, action="fix", rereview=review.UNCHECKED, rereview_round=2),
                   self.f(7, action="fix", rereview=review.UNRESOLVED, rereview_round=1),
                   self.f(8, found_round=0), self.f(9, found_round=1), self.f(10, action=review.DEFER),
                   self.f(11, "medium", action="fix", rereview=review.UNRESOLVED, rereview_round=2),
                   self.f(12, action="fix", rereview=review.RESOLVED, rereview_round=2)]
        rec = {"reviewer": "codex", "findings": [*ignored, *counted]}
        self.assertEqual([f["id"] for _, f in review.final_highs([rec])], [1, 2, 3])
        self.assertEqual(review.final_highs([{"reviewer": "codex", "findings": ignored}]), [])

    def test_any_reviewer_counts_and_new_highs_come_first(self):
        codex = {"reviewer": "codex", "findings": [self.f(1, action="fix", rereview=review.UNRESOLVED, rereview_round=2)]}
        agy = {"reviewer": "agy", "findings": [self.f(2, found_round=2)]}
        self.assertEqual([(rec["reviewer"], f["id"]) for rec, f in review.final_highs([codex, agy])], [("agy", 2), ("codex", 1)])

    def test_old_records_without_new_fields_count_nothing(self):
        self.assertEqual(review.final_highs([{"reviewer": "codex", "dir": "d", "findings": [
            {"id": 1, "severity": "high", "location": "a", "claim": "c", "evidence": "e", "action": "report"}]}]), [])
        self.assertEqual(review.final_highs([{"reviewer": "codex"}]), [])

    def test_reason(self):
        rec = {"reviewer": "codex"}
        new, unresolved = self.f(1, found_round=2), self.f(2, action="fix", rereview=review.UNRESOLVED, rereview_round=2)
        self.assertEqual(review.final_high_reason([(rec, new)]), "남은 high: a.py:1 지적 1")
        self.assertEqual(review.final_high_reason([(rec, unresolved)]), "남은 high: a.py:2 지적 2 (미해결)")
        self.assertEqual(review.final_high_reason([(rec, new), (rec, unresolved)]), "남은 high: a.py:1 지적 1 외 1개")
        self.assertEqual(review.final_high_reason([(rec, unresolved), (rec, unresolved)]), "남은 high: a.py:2 지적 2 외 1개 (미해결)")
        long = self.f(3, found_round=2, claim="줄\n바꿈  " + "가" * 300)
        self.assertEqual(review.final_high_reason([(rec, long)]),
                         "남은 high: a.py:3 " + ("줄 바꿈 " + "가" * 300)[:review.FINAL_HIGH_CLAIM_CHARS] + "…")
        self.assertEqual(review.final_high_reason([(rec, {**new, "location": ""})]), "남은 high: 지적 1")

    def test_second_fix_brief_says_a_remaining_high_is_not_merged(self):
        text = review.fix_brief([{"id": 1, "severity": "high", "location": "a.py:1", "claim": "c", "evidence": "e"}], 2)
        self.assertNotIn("남은 지적은 미해결로 병합된다", text)
        self.assertIn("high 지적이 미해결로 남거나 새로 나오면 이 시도는 병합되지 않고 티켓 실패가 된다", text)
        self.assertNotIn("티켓 실패", review.fix_brief([{"id": 1, "severity": "high", "location": "a.py:1", "claim": "c", "evidence": "e"}], 1))

    def test_why_of_the_rounds_without_the_judge(self):
        high, medium = review.Finding(1, "high", "a", "c", "e"), review.Finding(2, "medium", "a", "c", "e")
        self.assertIn("병합하지 않고 티켓 실패", review._final_why(high))
        self.assertEqual(review._final_why(medium), "더 고치지 않고 보고만 한다")


if __name__ == "__main__":
    unittest.main()
