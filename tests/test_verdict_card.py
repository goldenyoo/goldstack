"""판정 카드: 코드를 읽지 않고 승인·보류·되돌리기를 고른다.

state에 있는 사실만 적고, 없는 사실은 확인 불가다. 경로와 코드 인용은 카드에 넣지 않는다.
"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import go, report, review, state


SHA = "abcdef0123456789abcdef0123456789abcdef01"


def finding(claim, **kw):
    base = {"id": 1, "severity": "low", "location": "src/app.py:3", "claim": claim,
            "evidence": "EVIDENCE-TOKEN", "action": review.REPORT, "why": "src/app.py 를 보라"}
    base.update(kw)
    return base


class VerdictCardTest(unittest.TestCase):
    def run_of(self, phase="verified", tickets=None, finish=None, validations=None, reviews=None, **kw):
        st = state.State(feature="demo")
        st.finish = {"phase": phase, "url": "https://example.com/pr/1", "main_ok": True, "integration_ok": True,
                     "merge_sha": SHA}
        if finish:
            st.finish.update(finish)
        if validations is None:
            validations = [{"label": "integration", "result": "passed"}, {"label": "main", "result": "passed"}]
        if validations is not False:
            st.metrics["validations"] = validations
        tickets = tickets or [("01", "온도 로그를 파일로 보낸다", state.MERGED)]
        reviews = reviews or {}
        order, feat_tickets = [], {}
        for tid, title, status in tickets:
            order.append(tid)
            ts = st.ticket(tid)
            ts.status = status
            if "reason" in kw:
                ts.reason = kw.pop("reason") if tid == tickets[0][0] else ts.reason
            feat_tickets[tid] = SimpleNamespace(title=title, touches=kw.get("touches", {}).get(tid, []))
            if tid in reviews:
                ts.review = reviews[tid]
            elif status == state.MERGED:
                ts.review = {"reviewer": "codex", "findings": []}
        rundir = Path("/nonexistent-gs-verdict-card")
        spec = SimpleNamespace(verify="true")
        r = SimpleNamespace(st=st, name="demo", order=order, base="main", no_merge=False, prior=set(),
                            rundir=rundir, remote="origin", base_ref="origin/main",
                            feat=SimpleNamespace(tickets=feat_tickets, spec=spec))
        for key, value in kw.items():
            if key != "touches":
                setattr(r, key, value)
        return r

    def card(self, **kw):
        return report.verdict_card(self.run_of(**kw))

    def test_accept_when_work_landed_and_checks_are_clean(self):
        text = self.card()
        self.assertIn("결론: 승인 — 할 일 1개가 모두 기준 브랜치에 들어갔다.", text)
        self.assertIn("기준 브랜치에 들어감 · 01 온도 로그를 파일로 보낸다", text)
        self.assertIn("시험: 통과 2 · 실패 0", text)
        self.assertIn("한데 모은 시험(할 일을 모두 모은 뒤의 확인): 통과", text)
        self.assertIn("기준 브랜치 시험: 통과", text)
        self.assertIn("원격 검사(변경 요청에 붙은 자동 확인): 확인 불가", text)
        self.assertIn("검토자: 남긴 문제 없음", text)
        self.assertIn(f"넣은 기록(병합 커밋, 앞 8자) {SHA[:8]}", text)
        self.assertIn("물어볼 것: 없음", text)
        self.assertNotIn("EVIDENCE-TOKEN", text)
        self.assertLessEqual(len(text.splitlines()), 40)

    def test_missing_validation_rows_still_accept_when_gates_passed(self):
        text = self.card(validations=False)
        self.assertIn("결론: 승인 —", text)
        self.assertIn("시험: 확인 불가", text)

    def test_hold_quotes_a_plain_remark_and_not_a_path(self):
        text = self.card(reviews={"01": {"reviewer": "codex", "findings": [finding("안내 문장이 빠졌다")]}})
        self.assertIn("결론: 보류 —", text)
        self.assertIn("검토자가 남긴 문제가 1건 있다", text)
        self.assertIn("「안내 문장이 빠졌다」", text)
        self.assertNotIn("src/app.py", text)
        self.assertNotIn("EVIDENCE-TOKEN", text)
        self.assertIn("(예 / 아니오)", text)

    def test_code_remark_is_not_quoted(self):
        text = self.card(reviews={"01": {"reviewer": "codex", "findings": [
            finding("src/app.py:3 이 분기가 빠졌다")]}})
        self.assertIn("결론: 보류 —", text)
        self.assertIn("내용을 확인하지 않고 쓸까?", text)
        self.assertNotIn("src/app.py", text)
        self.assertNotIn("EVIDENCE-TOKEN", text)
        self.assertNotIn("이 분기가 빠졌다", text)

    def test_plain_failure_reason_is_kept_and_path_reason_is_dropped(self):
        plain = self.card(tickets=[("01", "알림을 띄운다", state.FAILED)],
                          reviews={}, finish={"main_ok": None, "integration_ok": False, "phase": "not_merged"})
        plain_state = self.run_of(tickets=[("01", "알림을 띄운다", state.FAILED)], reviews={},
                                   finish={"phase": "not_merged", "main_ok": None, "integration_ok": False,
                                           "merge_sha": ""})
        plain_state.st.ticket("01").reason = "화면이 멈추었다"
        code_state = self.run_of(tickets=[("01", "알림을 띄운다", state.FAILED)], reviews={},
                                  finish={"phase": "not_merged", "main_ok": None, "integration_ok": False,
                                          "merge_sha": ""})
        code_state.st.ticket("01").reason = "src/app.py:1 failed"
        self.assertIn("화면이 멈추었다", report.verdict_card(plain_state))
        code = report.verdict_card(code_state)
        self.assertNotIn("src/app.py", code)
        self.assertIn("실패해서 안 들어감", code)
        self.assertIn("결론: 보류 —", plain)

    def test_base_failure_recommends_rollback_with_a_yes_no_question(self):
        text = self.card(phase="main_failed", finish={"main_ok": False})
        self.assertIn("결론: 되돌리기 —", text)
        self.assertIn("기준 브랜치 시험이 실패했다", text)
        self.assertIn("1. 이 변경을 되돌릴까? (예 / 아니오)", text)
        self.assertNotIn("결론: 승인", text)

    def test_already_reverted_does_not_ask_to_roll_back_again(self):
        text = self.card(phase="reverted", finish={"main_ok": False, "revert_sha": SHA})
        self.assertIn("결론: 되돌리기 — 기준 브랜치 시험이 실패해 이미 되돌렸다.", text)
        self.assertIn(f"이미 되돌렸다. 되돌린 기록(앞 8자): {SHA[:8]}", text)
        self.assertIn("물어볼 것: 없음", text)
        self.assertNotIn("되돌릴까?", text)

    def test_only_run_does_not_read_an_old_verified_finish_as_landed(self):
        text = self.card(no_merge=True)
        self.assertIn("결론: 보류 —", text)
        self.assertIn("기준 브랜치에 넣지 않았다", text)
        self.assertIn("모음에 들어감 · 01 온도 로그를 파일로 보낸다", text)
        self.assertIn("모음 = 고른 일을 한데 모아 둔 곳", text)
        self.assertNotIn("기준 브랜치에 들어감", text)
        self.assertIn("1. 이 결과를 기준 브랜치에 넣는 다음 실행을 할까? (예 / 아니오)", text)

    def test_abort_holds_even_if_the_recorded_phase_is_verified(self):
        r = self.run_of()
        r.st.network["aborted"] = "connection reset"
        text = report.verdict_card(r)
        self.assertIn("결론: 보류 — 네트워크가 끊겨 중간에 멈췄다.", text)
        r.st.network["kind"] = "sandbox"
        self.assertIn("작업을 가둔 경계가 깨져 중간에 멈췄다", report.verdict_card(r))

    def test_revert_closing_can_accept(self):
        text = self.card(phase="revert_closing")
        self.assertIn("결론: 승인 —", text)
        self.assertIn("되돌리려던 요청을 닫는 일만 남았다", text)

    def test_failed_remote_check_holds_and_names_the_check(self):
        text = self.card(phase="checks_failed", finish={
            "checks": [{"name": "build", "bucket": "pass"}, {"name": "test", "bucket": "fail"}]})
        self.assertIn("결론: 보류 —", text)
        self.assertIn("원격 검사(변경 요청에 붙은 자동 확인): 통과 1 · 실패 1(test)", text)
        self.assertIn("실패한 원격 검사를 그대로 두고 넣을까?", text)

    def test_latest_failure_holds_even_when_phase_says_verified(self):
        text = self.card(validations=[{"label": "main", "result": "failed"}, {"label": "main", "result": "passed"},
                                       {"label": "integration", "result": "failed"}])
        self.assertIn("결론: 보류 —", text)
        self.assertIn("마지막이 통과가 아닌 항목 1개", text)
        self.assertNotIn("결론: 승인", text)

    def test_earlier_failure_is_shown_but_does_not_block_accept(self):
        text = self.card(validations=[{"label": "main", "result": "failed"}, {"label": "main", "result": "passed"},
                                       {"label": "integration", "result": "passed"}])
        self.assertIn("결론: 승인 —", text)
        self.assertIn("항목마다 마지막 결과는 통과", text)
        self.assertIn("통과가 아닌 것이 1건 있다", text)

    def test_skipped_bundle_test_is_explained_without_the_raw_reason(self):
        text = self.card(finish={"integration_skipped": "abc123 전체 검증과 같은 트리"})
        self.assertIn("결론: 승인 —", text)
        self.assertIn("한데 모은 시험(할 일을 모두 모은 뒤의 확인): 건너뜀(이미 통과한 시험과 같은 내용이라 다시 돌리지 않음)", text)
        self.assertNotIn("abc123", text)
        self.assertNotIn("같은 트리", text)

    def test_waiting_for_merge_asks_a_yes_no_question(self):
        text = self.card(phase="merge_pending", finish={"merge_sha": ""})
        self.assertIn("결론: 보류 —", text)
        self.assertIn("변경 요청 승인을 기다리는 중", text)
        self.assertIn("1. 이 변경 요청을 기준 브랜치에 넣을까? (예 / 아니오)", text)
        self.assertIn("모음에 들어감", text)

    def test_partial_landing_asks_whether_the_rest_can_wait(self):
        text = self.card(tickets=[("01", "온도 로그를 파일로 보낸다", state.MERGED),
                                   ("02", "사용 안내를 갱신한다", state.FAILED)])
        self.assertIn("할 일 2개 중 1개만 들어갔다", text)
        self.assertIn("들어가지 않은 일을 다음으로 미루고, 들어간 일만 써도 되나?", text)
        self.assertIn("사용 안내를 갱신한다", text)

    def test_skipped_review_holds(self):
        text = self.card(reviews={"01": {"reviewer": "codex", "note": review.LIMIT + ": 상한", "findings": []}})
        self.assertIn("결론: 보류 —", text)
        self.assertIn("검토를 끝내지 못한 일 01", text)
        self.assertIn("검토 없이 쓸까?", text)
        self.assertNotIn(review.LIMIT, text)

    def test_unknown_phase_token_is_not_printed(self):
        text = self.card(phase="zzphase", finish={"main_ok": None, "integration_ok": None})
        self.assertNotIn("zzphase", text)
        self.assertIn("확인 불가", text)
        self.assertIn("결론: 보류 —", text)

    def test_at_most_three_questions(self):
        r = self.run_of(tickets=[("01", "온도 로그를 파일로 보낸다", state.MERGED),
                                  ("02", "사용 안내를 갱신한다", state.FAILED)],
                        reviews={"01": {"reviewer": "codex", "findings": [finding("안내 문장이 빠졌다")]}},
                        finish={"checks": [{"name": "test", "bucket": "fail"}]})
        r.st.ticket("01").isolation_warnings = ["경계 밖"]
        r.st.ticket("01").kept_worktrees = ["/tmp/wt"]
        text = report.verdict_card(r)
        self.assertLessEqual(sum(line[:2].rstrip(".").isdigit() and line[1] == "." for line in text.splitlines()), 3)
        self.assertNotIn("4. ", text)
        self.assertNotIn("/tmp/wt", text)
        self.assertIn("넣지 않은 수정이 작업 폴더에 1곳", text)

    def test_many_tickets_stay_on_one_screen(self):
        tickets = [(f"{i:02d}", f"할 일 {i} 온도를 남긴다", state.MERGED) for i in range(1, 13)]
        text = self.card(tickets=tickets)
        self.assertIn("외 7건도 기준 브랜치에 들어감", text)
        self.assertLessEqual(len(text.splitlines()), 40)
        self.assertIn("결론: 승인 —", text)

    def test_empty_run_says_unknown_and_holds(self):
        text = report.verdict_card(SimpleNamespace())
        self.assertIn("결론: 보류 —", text)
        self.assertIn("확인 불가", text)
        self.assertNotIn("결론: 승인", text)

    def test_report_places_the_card_before_the_summary(self):
        r = self.run_of()
        text = report._render(r, "모델 요약", 0)
        self.assertLess(text.index("## 판정 카드"), text.index("## Summary"))
        self.assertIn("## 판정 카드\n", text.split("## Summary", 1)[0])
        self.assertIn("모델 요약", text.split("## Summary", 1)[1])

    def test_go_summary_prints_the_card_after_the_pr_line(self):
        r = self.run_of()
        with mock.patch.object(go, "say") as say:
            go._summary(r, "https://example.com/pr/1")
        lines = [call.args[0] for call in say.call_args_list]
        self.assertTrue(lines[-2].startswith("■ PR:"))
        self.assertTrue(lines[-1].startswith("## 판정 카드"))
        self.assertIn("결론: 승인 —", lines[-1])
        r.no_merge = True
        with mock.patch.object(go, "say") as say:
            go._summary(r, None)
        only = [call.args[0] for call in say.call_args_list]
        self.assertTrue(only[-1].startswith("## 판정 카드"))
        self.assertIn("결론: 보류 —", only[-1])
        self.assertNotIn("결론: 승인", only[-1])


if __name__ == "__main__":
    unittest.main()
