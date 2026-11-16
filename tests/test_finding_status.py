"""지적의 최종 상태·집계·Summary 입력과 재리뷰·2차 수정 진행 표시."""
import io
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_rereview
import test_second_review

from gs import config, go, report, review, state, status


def finding(claim="지적", **kw):
    return asdict(review.Finding(id=1, severity="high", location="a.py:1", claim=claim,
                                 evidence="원래 근거", action=review.FIX, why="판단 근거", **kw))


class FindingStatusTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        rundir = repo / ".goldstack/work/demo/run"
        rundir.mkdir(parents=True)
        st = state.State(feature="demo", finish={"phase": "verified", "url": "https://example.com/pr/1"})
        st.ticket("01").status = state.MERGED
        self.r = SimpleNamespace(st=st, name="demo", order=["01"], repo=repo, iwt=repo,
                                 rundir=rundir, base="main", base_ref="origin/main", remote="origin",
                                 cfg=config.Config(config.GitConfig("origin", "main"),
                                                   config.ModelsConfig("opus", "opus", "agy", "codex"),
                                                   config.TimeoutsConfig(30, 30, 60), config.NotifyConfig(False)),
                                 feat=SimpleNamespace(
                                     tickets={"01": SimpleNamespace(title="티켓")},
                                     spec=SimpleNamespace(verify="true", path=repo / "spec.md")))

    def test_statuses_and_precedence(self):
        cases = [
            ({"rereview": review.RESOLVED}, "수정됨(재리뷰 확인)"),
            ({"rereview": review.UNRESOLVED, "fix_round": 2}, "미해결"),
            ({"rereview": review.UNRESOLVED, "fix_reason": "한도"}, "미해결"),
            ({"rereview": review.UNRESOLVED, "fix_attempt": review.DISCARDED,
              "fix_reason": "수정 worker 실패"}, "미해결"),
            ({"action": review.REPORT}, "보고만"),
            ({"found_round": 2}, "보고만"),
            ({"action": review.REPORT, "found_round": 1, "rereview": review.RESOLVED, "rereview_round": 2},
             report.REPORT_RESOLVED),
            ({"action": review.REPORT, "found_round": 1, "rereview": review.UNRESOLVED, "rereview_round": 2}, "보고만"),
            ({"fix_reason": "한도"}, "수정 못 함(한도)"),
            ({"fix_attempt": review.DISCARDED, "fix_reason": "수정 worker 실패: 종료 코드 3"},
             "수정 못 함(수정 worker 실패: 종료 코드 3)"),
            ({"fix_reason": "띄우지 못함: 오류"}, "수정 못 함(띄우지 못함: 오류)"),
            ({"fix_attempt": review.DISCARDED}, "수정 못 함(수정 버림)"),
            ({"rereview": review.UNCHECKED, "rereview_reason": "시간 초과"}, "확인 못 함(시간 초과)"),
            ({"rereview": review.UNCHECKED, "rereview_reason": "한도"}, "확인 못 함(한도)"),
            ({"rereview": review.UNCHECKED, "rereview_reason": "재리뷰 실패"}, "확인 못 함(재리뷰 실패)"),
            ({"fix_attempt": review.ATTEMPTED}, "확인 못 함(재리뷰 없음)"),
            ({}, "수정 못 함(수정 기록 없음)"),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                self.assertEqual(report.finding_status({**finding(), **fields}), expected)

    def five_statuses(self):
        ts = self.r.st.ticket("01")
        ts.review = {"reviewer": "codex", "findings": [
            finding("해결된 지적", rereview=review.RESOLVED, rereview_evidence="커밋으로 확인"),
            finding("남은 오류", rereview=review.UNRESOLVED, fix_round=2),
            {**finding("문서 제안"), "action": review.REPORT},
        ], "fix": "수정 커밋 1개(fix 지적 1, 2): 재리뷰로 확인한다 / 재리뷰 1차: resolved 1 · unresolved 1"}
        ts.second_review = {"reviewer": "agy", "findings": [
            finding("못 고친 오류", fix_reason="한도"),
            finding("확인 안 된 오류", rereview=review.UNCHECKED, rereview_reason="시간 초과"),
        ]}

    def test_every_finding_has_status_and_counts_follow_finish_line(self):
        self.five_statuses()
        text = report._render(self.r, "변경 요약", 0)
        expected = "리뷰 지적: 수정됨 1 · 미해결 1 · 보고만 1 · 수정 못 함 1 · 확인 못 함 1"
        remaining = "남은 high 4(보고만 1 · 미해결 1 · 수정 못 함 1 · 확인 못 함 1)"
        self.assertIn(f"{report.status_line(self.r)} · {remaining}\n{expected}\n\n## Evidence", text)
        lines = [line for line in text.splitlines() if " — 상태: " in line]
        self.assertEqual(len(lines), 5)
        for line, label in zip(lines, ("수정됨(재리뷰 확인)", "미해결", "보고만", "수정 못 함(한도)", "확인 못 함(시간 초과)")):
            self.assertTrue(line.endswith(f" — 상태: {label}"), line)
        self.assertIn("재리뷰 근거: 커밋으로 확인", text)
        self.assertNotIn("재리뷰 없음", text)

    def test_counts_omit_zero_empty_reviews_and_outside_scope(self):
        self.assertEqual(report.finding_counts(self.r), "")
        self.assertNotIn("리뷰 지적:", report._render(self.r, "요약", 0))
        self.r.st.ticket("01").review = {"reviewer": "codex", "findings": [
            finding(rereview=review.RESOLVED), finding(rereview=review.RESOLVED)]}
        self.r.st.ticket("outside").review = {"findings": [finding(fix_reason="한도")]}
        self.assertEqual(report.finding_counts(self.r), "리뷰 지적: 수정됨 2")

    def partial_run(self):
        r = self.r
        r.no_merge, r.prior = False, set()
        r.order = ["01", "02", "03", "04"]
        for tid in r.order:
            r.st.ticket(tid).status = state.MERGED if tid != "04" else state.FAILED
            r.feat.tickets[tid] = SimpleNamespace(title="티켓")
        r.st.ticket("01").review = {"findings": [finding(rereview=review.UNRESOLVED)]}
        r.st.ticket("04").second_review = {"findings": [finding(rereview=review.UNRESOLVED) | {"severity": "low"}]}
        r.st.ticket("outside").review = {"findings": [finding(rereview=review.UNRESOLVED)]}
        return r

    def test_partial_verified_report_and_go_summary_show_same_counts(self):
        r = self.partial_run()
        prefix = "마무리: verified · 티켓 3/4 병합 · 미해결 2"
        self.assertIn("\n" + prefix + " · PR ", report._render(r, "요약", 0))
        self.assertEqual(report.finding_counts(r), "리뷰 지적: 미해결 2")
        self.assertIn("■ " + prefix, self.run_summary(go._summary, r, None))
        # 실제 실행은 phase와 별도로 사람용 outcome 문장을 저장한다.
        r.st.finish["outcome"] = "integration·main 검증 통과, PR 병합 완료"
        self.assertIn("■ 마무리: integration·main 검증 통과, PR 병합 완료 · 티켓 3/4 병합 · 미해결 2",
                      self.run_summary(go._summary, r, None))
        self.assertEqual(r.st.finish["phase"], "verified")

    def test_verified_suffix_counts_deferred_but_not_resolved_or_superseded(self):
        r = self.partial_run()
        deferred = finding() | {"action": review.DEFER, "severity": "low"}
        r.st.ticket("02").review = {"findings": [deferred, deferred | {"superseded": True},
            deferred | {"repair_review": review.RESOLVED, "repair_review_evidence": "수리 확인"}]}
        suffix = " · 티켓 3/4 병합 · 미해결 2 · 재현된 미수리 1"
        self.assertTrue(report.status_line(r).startswith("마무리: verified" + suffix + " · PR "))
        self.assertIn("■ 마무리: verified" + suffix, self.run_summary(go._summary, r, None))
        self.assertEqual(report.finding_counts(r), "리뷰 지적: 수정됨 1 · 미해결 2 · 재현된 미수리 1 · 대체됨 1")

    def test_verified_suffix_each_condition_and_finished_run(self):
        r = self.partial_run()
        for tid in r.order:
            r.st.ticket(tid).review = {}
            r.st.ticket(tid).second_review = {}
        pr = " · PR https://example.com/pr/1 병합 · main 검증 통과"
        self.assertEqual(report.status_line(r), "마무리: verified · 티켓 3/4 병합" + pr)
        r.st.ticket("04").status = state.MERGED
        self.assertEqual(report.status_line(r), "마무리: verified" + pr)
        self.assertIn("■ 마무리: verified", self.run_summary(go._summary, r, None))
        for fields, label in (({"rereview": review.UNRESOLVED}, "미해결"), ({"action": review.DEFER}, "재현된 미수리")):
            with self.subTest(label=label):
                r.st.ticket("01").review = {"findings": [finding() | fields]}
                self.assertEqual(report.status_line(r), f"마무리: verified · {label} 1" + pr)
                self.assertIn(f"■ 마무리: verified · {label} 1", self.run_summary(go._summary, r, None))

    def test_other_phases_do_not_gain_verified_suffix(self):
        r = self.partial_run()
        r.st.ticket("02").review = {"findings": [finding() | {"action": review.DEFER}]}
        for phase, detail in (("not_merged", "integration 검증 실패"), ("preparing", "병합 전")):
            with self.subTest(phase=phase):
                r.st.finish["phase"] = phase
                self.assertEqual(report.status_line(r), f"마무리: {phase} · {detail}")
                self.assertIn(f"■ 마무리: {phase}", self.run_summary(go._summary, r, None))

    def test_summary_prompt_and_facts_distinguish_resolved_from_remaining(self):
        self.five_statuses()
        with mock.patch.object(report.git, "out", return_value="a.py | 1 +"), \
                mock.patch.object(review, "_call", return_value="요약") as call:
            self.assertEqual(report.summarize(self.r), "요약")
        prompt = call.call_args.kwargs["prompt"]
        self.assertIn("수정됨(재리뷰 확인)은 해결된 지적이므로 남은 위험에 넣지 마라", prompt)
        self.assertIn("미해결·보고만·수정 못 함·확인 못 함은 남은 지적", prompt)
        facts = (self.r.rundir / "finish/report-input.md").read_text()
        self.assertIn("해결된 지적 — 상태: 수정됨(재리뷰 확인)", facts)
        self.assertIn("남은 오류 — 상태: 미해결", facts)
        self.assertIn("확인 안 된 오류 — 상태: 확인 못 함(시간 초과)", facts)
        self.assertNotIn("### 남은 리뷰 지적", facts)

    def test_remaining_line_counts_only_high_with_remaining_status(self):
        self.assertEqual(report.remaining_line(self.r), "")
        self.five_statuses()
        # 수정됨 high는 빼고, medium·low는 세지 않는다
        ts = self.r.st.ticket("01")
        ts.review["findings"].append(finding("중간", rereview=review.UNRESOLVED) | {"severity": "medium"})
        self.assertEqual(report.remaining_line(self.r), "남은 high 4(보고만 1 · 미해결 1 · 수정 못 함 1 · 확인 못 함 1)")
        ts.review = {"findings": [finding(rereview=review.RESOLVED)]}
        ts.second_review = {}
        self.assertEqual(report.remaining_line(self.r), "")

    def test_report_finding_resolved_by_the_second_rereview_is_not_remaining(self):
        """goldstack-v40 03: 1차 재리뷰의 새 report high를 2차 재리뷰가 resolved로 판정하면 해소됨이고 남은 high·남은 지적에서 빠진다."""
        new = {**finding("1차 재리뷰의 새 문제"), "action": review.REPORT, "found_round": 1}
        resolved = {**new, "rereview": review.RESOLVED, "rereview_round": 2, "rereview_evidence": "코드에서 확인"}
        unresolved = {**new, "id": 2, "claim": "그대로인 문제", "rereview": review.UNRESOLVED, "rereview_round": 2}
        ts = self.r.st.ticket("01")
        ts.review = {"reviewer": "codex", "findings": [resolved, unresolved]}
        self.assertEqual(report.remaining_line(self.r), "남은 high 1(보고만 1)")
        self.assertEqual(report.finding_counts(self.r), "리뷰 지적: 해소됨 1 · 보고만 1")
        self.assertEqual([f["claim"] for f in review.remaining(ts.review)], ["그대로인 문제"])
        with mock.patch.object(report.git, "out", return_value="a.py | 1 +"), \
                mock.patch.object(review, "_call", return_value="요약") as call:
            report.summarize(self.r)
        self.assertIn("해소됨(재리뷰 확인", call.call_args.kwargs["prompt"])
        facts = (self.r.rundir / "finish/report-input.md").read_text()
        self.assertIn(f"1차 재리뷰의 새 문제 — 상태: {report.REPORT_RESOLVED}", facts)
        self.assertIn("그대로인 문제 — 상태: 보고만", facts)

    def test_prior_findings_show_in_their_own_section_and_not_in_counts(self):
        ts = self.r.st.ticket("01")
        self.assertEqual(report.prior_findings_section(self.r), "")
        self.assertNotIn("버려진 시도의 지적", report.evidence(self.r))
        ts.prior_findings = [{"attempt": 1, "reviewer": "codex", "reviewed_head": "0123456789abcdef0123",
                              "findings": [{**finding("버려진 높은 지적"), "action": review.REPORT},
                                           {**finding("버려진 낮은 지적"), "severity": "low"}]}]
        text = report.evidence(self.r)
        section = text.split("### 버려진 시도의 지적\n\n", 1)[1].split("\n\n", 1)[0]
        self.assertEqual(section.splitlines(), [
            "- 01 시도 1 리뷰(codex, 0123456789ab) [high] a.py:1: 버려진 높은 지적",
            "- 01 시도 1 리뷰(codex, 0123456789ab) [low] a.py:1: 버려진 낮은 지적"])
        self.assertLess(text.index("### 리뷰 지적"), text.index("### 버려진 시도의 지적"))
        # 집계에는 들어가지 않는다
        self.assertEqual(report.remaining_line(self.r), "")
        self.assertEqual(report.finding_counts(self.r), "")

    def test_remaining_line_lists_skipped_reviews_alone_or_with_high(self):
        st = self.r.st
        st.ticket("01").second_review = review.record("agy", f"{review.LIMIT}: 이번 실행의 agy 호출이 상한 1/1에 닿았다")
        self.assertEqual(report.remaining_line(self.r), "건너뛴 리뷰: 01")
        st.ticket("01").review = {"reviewer": "codex", "findings": [{**finding(), "action": review.REPORT}]}
        self.assertEqual(report.remaining_line(self.r), "남은 high 1(보고만 1) · 건너뛴 리뷰: 01")
        text = report._render(self.r, "요약", 0)
        self.assertIn(f"{report.status_line(self.r)} · 남은 high 1(보고만 1) · 건너뛴 리뷰: 01\n", text)
        # 거부 같은 다른 note는 건너뜀이 아니다
        st.ticket("01").second_review = review.record("agy", "같은 계열은 거부")
        self.assertEqual(report.remaining_line(self.r), "남은 high 1(보고만 1)")

    def test_remaining_line_tolerates_old_state_without_severity_or_status(self):
        ts = self.r.st.ticket("01")
        ts.review = {"findings": [{"location": "a.py:1", "claim": "옛 지적", "evidence": "", "action": review.REPORT},
                                  {"severity": "high", "location": "a.py:2", "claim": "high 지적", "evidence": ""}]}
        ts.second_review = {"reviewer": "agy", "note": None}
        self.assertEqual(report.remaining_line(self.r), "남은 high 1(보고만 1)")  # action이 없으면 보고만
        self.assertIn("옛 지적 — 상태: 보고만", report._render(self.r, "요약", 0))

    def run_summary(self, fn, *args):
        with mock.patch.object(go, "say") as say:
            fn(*args)
        return [call.args[0] for call in say.call_args_list]

    def test_go_summary_shows_line_and_only_summary_does_not(self):
        r = self.r
        r.no_merge = False
        r.st.network = {}
        r.prior = set()
        r.st.ticket("01").review = {"reviewer": "codex", "findings": [
            {**finding(), "action": review.REPORT}, finding(rereview=review.UNCHECKED, rereview_reason="한도")]}
        r.st.ticket("01").second_review = review.record("agy", f"{review.LIMIT}: 상한")
        lines = self.run_summary(go._summary, r, "https://example.com/pr/1")
        self.assertEqual([line for line in lines if "high" in line or "건너뛴" in line],
                         ["■ 남은 high 2(보고만 1 · 확인 못 함 1) · 건너뛴 리뷰: 01"])
        self.assertEqual(lines[-1], "■ PR: https://example.com/pr/1")
        self.assertTrue(lines[-2].startswith("■ 남은 high"))
        r.no_merge = True
        only = self.run_summary(go._summary, r, None)
        self.assertFalse([line for line in only if "high" in line or "건너뛴" in line], only)
        r.st.ticket("01").review = {}
        r.st.ticket("01").second_review = {}
        r.no_merge = False
        self.assertFalse([line for line in self.run_summary(go._summary, r, None) if "high" in line])

    def test_progress_and_gs_status_show_rereview_and_second_fix(self):
        st = self.r.st
        st.started_at = "2026-11-04T00:00:00+00:00"
        ts = st.ticket("03")
        ts.status = state.RUNNING
        for phase, model, label in (("rereview", "codex+agy", "재리뷰"), ("fix2", "claude", "수정 2")):
            with self.subTest(phase=phase):
                state.begin_phase(ts, phase, model, at=st.started_at)
                st.progress = state.calculate_progress(st, ["03"], 1, at=st.started_at)
                expected = f"03 {label} 중({model})"
                self.assertIn(expected, st.progress["line"])
                state.save(self.r.rundir, st)
                out = io.StringIO()
                self.assertEqual(status.status(self.r.repo, "demo", out), 0)
                self.assertIn(expected, out.getvalue())


class FindingStatusFlowTest(test_rereview.Base):
    def test_report_uses_real_fix_and_rereview_results_for_all_five_statuses(self):
        self.two_reviewers()
        f = test_second_review.finding
        self.findings("codex", f("FIX A: 고칠 오류"), f("FIX B: 남을 오류", "medium"), f("문서 제안", "low"))
        self.findings("agy", f("FIX C: 확인 못 할 오류"))
        self.answer("codex", 1, [(1, "resolved", "커밋으로 확인"), (2, "unresolved", "오류가 남음")],
                    [f("FIX N: 새 오류")])
        # agy는 형식이 틀린 답 → 확인 못 함. 2차 수정 실패 → B는 미해결, 새 지적 N은 수정 못 함.
        (self.bin / "fixfail_2").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        text = self.final_report()
        self.assertIn("리뷰 지적: 수정됨 1 · 미해결 1 · 보고만 1 · 수정 못 함 1 · 확인 못 함 1", text)
        for claim, label in (("FIX A: 고칠 오류", "수정됨(재리뷰 확인)"), ("FIX B: 남을 오류", "미해결"),
                             ("문서 제안", "보고만"), ("FIX N: 새 오류", "수정 못 함(수정 worker 실패: 종료 코드 3)"),
                             ("FIX C: 확인 못 할 오류", "확인 못 함(재리뷰 실패)")):
            self.assertIn(f"{claim} — 상태: {label}", text)
        self.assertIn("수정 커밋 1개", text)
        self.assertIn("재리뷰 1차: resolved 1", text)
        self.assertNotIn("재리뷰 없음", text)

    def test_go_prints_remaining_high_and_skipped_review_without_changing_verdict(self):
        self.limit(1)
        self.tickets(**{"01": ("claude", "codex", "agy", "[]"), "04": ("claude", "codex", "agy", '["01"]')})
        self.findings("codex", test_second_review.finding("문서 제안"))  # FIX가 없어 보고만
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.run_state().finish["phase"], "verified")
        lines = out.strip().splitlines()
        self.assertEqual(lines[-2], "■ 남은 high 2(보고만 2) · 건너뛴 리뷰: 04")
        self.assertTrue(lines[-1].startswith("■ PR:"), lines[-1])
        self.assertRegex(self.final_report(), r"마무리: verified · .* · 남은 high 2\(보고만 2\) · 건너뛴 리뷰: 04\n")


if __name__ == "__main__":
    unittest.main()
