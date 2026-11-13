"""진행 계산·시도별 단계 이력·보고서·옛 state 호환."""
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from gs import report, state, status


START = datetime(2026, 11, 3, 9, tzinfo=timezone.utc)


def clock(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


class ProgressTest(unittest.TestCase):
    def test_spec_line_and_eta(self):
        st = state.State(feature="goldstack-v2", started_at=clock(0))
        order = [f"{n:02}" for n in range(1, 9)]
        for tid in order:
            st.ticket(tid)
        for tid in order[:3]:
            ts = st.ticket(tid)
            ts.status, ts.started_at, ts.ended_at = state.MERGED, clock(0), clock(1440)
        ts = st.ticket("04")
        ts.status = state.RUNNING
        state.begin_phase(ts, "review", "codex", attempt=1, at=clock(1200))
        p = state.calculate_progress(st, order, 3, at=clock(1440))
        self.assertEqual(p, {
            "done": 3, "total": 8, "running": [{"id": "04", "phase": "review", "model": "codex"}],
            "elapsed_s": 1440, "eta_s": 2880,
            "line": "▓▓▓░░░░░ goldstack-v2 3/8 · 04 리뷰 중(codex) · 24분 · 약 48분 남음 + 마무리"})

    def test_no_completed_ticket_and_empty_scope(self):
        st = state.State(feature="f", started_at=clock(0))
        st.ticket("01").status = state.RUNNING
        p = state.calculate_progress(st, ["01"], 1, models={"01": "agy"}, at=clock(1))
        self.assertIsNone(p["eta_s"])
        self.assertIn("남은 시간 계산 중", p["line"])
        self.assertEqual(p["running"], [{"id": "01", "phase": "worker", "model": "agy"}])
        self.assertEqual(state.calculate_progress(st, [], 1, at=clock(1))["total"], 0)

    def test_scope_prior_runs_failures_and_rounding(self):
        st = state.State(feature="f", started_at=clock(0))
        for tid in ("old", "01", "02", "skipped", "outside", "pending"):
            st.ticket(tid)
        for tid, seconds in (("old", 12000), ("outside", 12000), ("01", 300), ("02", 330)):
            ts = st.ticket(tid)
            ts.status, ts.started_at, ts.ended_at = state.MERGED, clock(0), clock(seconds)
        st.ticket("02").status = state.FAILED
        st.ticket("skipped").status = state.SKIPPED
        p = state.calculate_progress(st, ["old", "01", "02", "skipped", "pending"], 3,
                                     prior={"old"}, at=clock(400))
        self.assertEqual((p["done"], p["total"], p["eta_s"]), (4, 5, 300))
        self.assertEqual(state.minutes(30), 1)
        self.assertEqual(state.minutes(29), 0)
        self.assertEqual(state.minutes(90), 2)
        # 상태에는 있어도 지난 실행에서 끝난 티켓의 시간은 ETA 표본이 아니다.
        st.ticket("01").started_at, st.ticket("01").ended_at = clock(-300), clock(-1)
        p = state.calculate_progress(st, ["01", "pending"], 1, at=clock(400))
        self.assertIsNone(p["eta_s"])

    def test_retry_time_includes_first_attempt(self):
        st = state.State(feature="f", started_at=clock(0))
        ts = st.ticket("01")
        state.begin_phase(ts, "worker", "codex", attempt=1, at=clock(60))
        state.end_phase(ts, clock(120))
        state.begin_phase(ts, "worker", "codex", attempt=2, at=clock(180))
        state.begin_phase(ts, "verify", "codex", at=clock(300))
        state.end_phase(ts, clock(360))
        ts.status, ts.started_at, ts.ended_at = state.MERGED, clock(180), clock(360)
        st.ticket("02")
        p = state.calculate_progress(st, ["01", "02"], 1, at=clock(360))
        self.assertEqual(p["eta_s"], 300)
        self.assertEqual([p["attempt"] for p in ts.phases], [1, 2, 2])
        self.assertEqual(state.phase_durations(ts), {"worker": 180, "verify": 60})

    def test_eta_compares_actual_times_across_offset_changes(self):
        before = "2026-11-01T01:30:00-07:00"
        earlier = "2026-11-01T01:50:00-07:00"
        after = "2026-11-01T01:10:00-08:00"
        later = "2026-11-01T01:20:00-08:00"
        end = "2026-11-01T01:30:00-08:00"
        cases = [
            ("current phase", before, [after], after, later, 600),
            ("previous phase", after, ["2026-11-01T01:15:00-07:00", later], later, end, 600),
            ("earliest attempt", "2026-11-01T00:30:00-07:00", [earlier, after], after, later, 1800),
            ("legacy current ticket", before, [], after, later, 600),
            ("legacy previous ticket", after, [], earlier, after, None),
        ]
        for name, run_start, phases, start, ended_at, eta in cases:
            with self.subTest(name=name):
                st = state.State(feature="f", started_at=run_start)
                ts = st.ticket("01")
                for attempt, phase_start in enumerate(phases, 1):
                    state.begin_phase(ts, "worker", "codex", attempt=attempt, at=phase_start)
                state.end_phase(ts, ended_at)
                ts.status, ts.started_at, ts.ended_at = state.MERGED, start, ended_at
                st.ticket("02")
                p = state.calculate_progress(st, ["01", "02"], 1, at=ended_at)
                self.assertEqual(p["eta_s"], eta)

    def test_finish_and_finished_elapsed(self):
        st = state.State(feature="f", started_at=clock(0), phase="finish")
        st.ticket("01").status = state.MERGED
        p = state.calculate_progress(st, ["01"], 1, at=clock(60))
        self.assertEqual(p["running"], [{"id": "", "phase": "finish", "model": "claude"}])
        self.assertIn("마무리 중(claude)", p["line"])
        st.finished_at = clock(120)
        p = state.calculate_progress(st, ["01"], 1, at=clock(999))
        self.assertEqual((p["elapsed_s"], p["running"]), (120, []))

    def test_parallel_running_tickets_follow_scope(self):
        st = state.State(feature="f", started_at=clock(0))
        for tid, phase, model in (("01", "worker", "claude"), ("02", "fix", "agy"),
                                  ("outside", "review", "codex")):
            ts = st.ticket(tid)
            ts.status = state.RUNNING
            state.begin_phase(ts, phase, model, attempt=1, at=clock(0))
        p = state.calculate_progress(st, ["02", "01"], 2, at=clock(60))
        self.assertEqual(p["running"], [{"id": "02", "phase": "fix", "model": "agy"},
                                       {"id": "01", "phase": "worker", "model": "claude"}])
        self.assertIn("02 수정 중(agy) · 01 worker 중(claude)", p["line"])

    def test_legacy_state_report_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            rundir = repo / ".goldstack/work/f/run"
            rundir.mkdir(parents=True)
            state.path(rundir).write_text(json.dumps({"feature": "f", "started_at": clock(0),
                                                     "tickets": {"01": {"status": "merged"}}}))
            st = state.load(rundir, "f")
            self.assertEqual((st.ticket("01").phases, st.progress), ([], {}))
            r = SimpleNamespace(st=st, order=["01"], rundir=rundir,
                                feat=SimpleNamespace(tickets={"01": SimpleNamespace(title="t")},
                                                     spec=SimpleNamespace(verify="true")))
            self.assertNotIn("단계별 소요", report.evidence(r))
            ts = st.ticket("01")
            for phase, model, start in (("worker", "claude", 0), ("review", "codex", 540),
                                        ("fix", "claude", 780), ("verify", "claude", 900)):
                state.begin_phase(ts, phase, model, attempt=1, at=clock(start))
            state.end_phase(ts, clock(1080))
            self.assertIn("단계별 소요: worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분", report.evidence(r))
            st.progress = state.calculate_progress(st, ["01"], 1, at=clock(1080))
            state.save(rundir, st)
            self.assertEqual(state.load(rundir, "f").ticket("01").phases, ts.phases)
            out = io.StringIO()
            self.assertEqual(status.status(repo, "f", out), 0)
            self.assertEqual(out.getvalue().splitlines()[-1], st.progress["line"])
            ts.phases = [p for p in ts.phases if p["phase"] != "fix"]
            self.assertNotIn("수정 2분", report.evidence(r))


def merged(st, tid, start, end):
    ts = st.ticket(tid)
    ts.status, ts.started_at, ts.ended_at = state.MERGED, clock(start), clock(end)
    return ts


def running(st, tid, start, phase="worker"):
    ts = st.ticket(tid)
    ts.status = state.RUNNING
    state.begin_phase(ts, phase, "codex", attempt=1, at=clock(start))
    return ts


class TierProgressTest(unittest.TestCase):
    def progress(self, elapsed, *, tier="large", **kwargs):
        st = state.State(feature="f", started_at=clock(0))
        running(st, "01", 0)
        return state.calculate_progress(st, ["01"], 1, at=clock(elapsed * 60),
                                        tiers={"01": tier}, tier_medians_s={"large": 48 * 60},
                                        finish_median_s=0, **kwargs)

    def test_large_uses_tier_median_for_remaining_time(self):
        p = self.progress(30, history_median_s=25 * 60)
        self.assertEqual(p["eta_s"], 18 * 60)
        self.assertIn("약 18분 남음(이전 실행 기준)", p["line"])
        self.assertNotIn("넘김", p["line"])
        self.assertNotIn("예상 넘긴 티켓 있음", p["line"])

    def test_large_overrun_displays_estimate_and_growing_excess(self):
        for elapsed, excess in ((60, 12), (65, 17)):
            with self.subTest(elapsed=elapsed):
                p = self.progress(elapsed, history_median_s=25 * 60)
                self.assertIn(f"01 예상 48분 넘김(+{excess}분)", p["line"])
                self.assertIn("예상 넘긴 티켓 있음", p["line"].split(" · ")[-1])
        p = self.progress(48, history_median_s=25 * 60)
        self.assertNotIn("넘김", p["line"])
        self.assertNotIn("예상 넘긴 티켓 있음", p["line"])

    def test_missing_tier_uses_overall_median(self):
        for tier in (None, "", "small"):
            with self.subTest(tier=tier):
                p = self.progress(10, tier=tier, history_median_s=25 * 60)
                self.assertEqual(p["eta_s"], 15 * 60)

    def test_tier_history_without_overall_history(self):
        self.assertEqual(self.progress(30)["eta_s"], 18 * 60)

    def test_current_tier_average_precedes_history_and_overall_average(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "large1", 0, 40 * 60)
        merged(st, "large2", 0, 60 * 60)
        merged(st, "small", 0, 5 * 60)
        # 범위 밖·이전 실행의 같은 tier 기록은 표본에 넣지 않는다.
        merged(st, "outside", 0, 100 * 60)
        merged(st, "prior", 0, 200 * 60)
        st.ticket("next")
        tiers = {tid: "large" for tid in st.tickets}
        tiers["small"] = "small"
        p = state.calculate_progress(st, ["large1", "large2", "small", "prior", "next"], 1,
                                     prior={"prior"}, at=clock(200 * 60), tiers=tiers,
                                     tier_medians_s={"large": 48 * 60}, history_median_s=25 * 60,
                                     finish_median_s=0)
        self.assertEqual(p["eta_s"], 50 * 60)
        self.assertNotIn("이전 실행 기준", p["line"])

    def test_tier_history_precedes_current_overall_average_and_falls_back(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "done", 0, 10 * 60)
        running(st, "next", 10 * 60)
        for tier, expected, historical in (("large", 43, True), ("small", 5, False), (None, 5, False)):
            with self.subTest(tier=tier):
                p = state.calculate_progress(st, ["done", "next"], 1, at=clock(15 * 60),
                                             tiers={"done": "medium", "next": tier},
                                             tier_medians_s={"large": 48 * 60}, history_median_s=25 * 60,
                                             finish_median_s=0)
                self.assertEqual(p["eta_s"], expected * 60)
                self.assertEqual("이전 실행 기준" in p["line"], historical)

    def test_unknown_estimate_keeps_calculating_but_shows_known_overrun(self):
        st = state.State(feature="f", started_at=clock(0))
        running(st, "01", 0, phase="network")
        st.ticket("02")
        p = state.calculate_progress(st, ["01", "02"], 2, at=clock(60 * 60),
                                     tiers={"01": "large"}, tier_medians_s={"large": 48 * 60})
        self.assertIsNone(p["eta_s"])
        self.assertIn("01 예상 48분 넘김(+12분)", p["line"])
        self.assertTrue(p["line"].endswith("남은 시간 계산 중(예상 넘긴 티켓 있음)"))


class ScheduleTest(unittest.TestCase):
    """남은 시간 = 의존과 max_workers로 흉내 낸 일정 + 마무리."""

    def eta(self, st, order, workers, at, **kw):
        p = state.calculate_progress(st, order, workers, at=clock(at), **kw)
        return p["eta_s"], p["line"].split(" · ")[-1]

    def test_serial_chain_is_not_divided_by_workers(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        st.ticket("02"), st.ticket("03")
        deps = {"01": [], "02": ["01"], "03": ["02"]}
        # 첫 티켓이 10분 걸렸고 둘이 남았다: 20분. max_workers = 3이어도 같다
        self.assertEqual(self.eta(st, ["01", "02", "03"], 3, 600, deps=deps, finish_median_s=0),
                         (1200, "약 20분 남음"))
        self.assertEqual(self.eta(st, ["01", "02", "03"], 3, 600, finish_median_s=0), (600, "약 10분 남음"))

    def test_parallel_tickets_share_workers(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        for tid in ("02", "03", "04", "05"):
            st.ticket(tid)
        deps = {"02": ["01"], "03": ["01"], "04": ["01"], "05": ["02", "03"]}
        # 02·03·04가 한꺼번에 돌고 05는 02·03 뒤: 20분. 자리가 둘이어도 02·03, 04·05로 20분, 하나면 40분
        order = ["01", "02", "03", "04", "05"]
        self.assertEqual(self.eta(st, order, 3, 600, deps=deps, finish_median_s=0), (1200, "약 20분 남음"))
        self.assertEqual(self.eta(st, order, 2, 600, deps=deps, finish_median_s=0), (1200, "약 20분 남음"))
        self.assertEqual(self.eta(st, order, 1, 600, deps=deps, finish_median_s=0), (2400, "약 40분 남음"))

    def test_running_ticket_counts_remaining_time_only(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        running(st, "02", 600)
        st.ticket("03")
        deps = {"02": ["01"], "03": ["02"]}
        # 02는 4분 썼다: 남은 6분 + 03의 10분
        self.assertEqual(self.eta(st, ["01", "02", "03"], 2, 840, deps=deps, finish_median_s=0), (960, "약 16분 남음"))
        # 02가 네트워크 대기 중이어도 자리를 쓰고 쓴 시간을 뺀다
        state.begin_phase(st.ticket("02"), "network", "codex", at=clock(700))
        self.assertEqual(self.eta(st, ["01", "02", "03"], 2, 840, deps=deps, finish_median_s=0), (960, "약 16분 남음"))

    def test_running_ticket_over_average_marks_overrun(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        running(st, "02", 600)
        self.assertEqual(self.eta(st, ["01", "02"], 1, 600 + 1500, finish_median_s=0), (60, "약 1분 남음(예상 넘긴 티켓 있음)"))

    def test_running_ticket_just_under_average_counts_remainder(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        running(st, "02", 600)
        # 평균 10분 중 590초를 썼다: 남은 10초는 1분으로 올리지 않는다(분 반올림은 그대로)
        self.assertEqual(self.eta(st, ["01", "02"], 1, 1190, finish_median_s=300), (300, "약 5분 남음"))

    def test_retry_time_of_running_ticket_counts_from_first_attempt(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        ts = running(st, "02", 600)
        state.begin_phase(ts, "worker", "codex", attempt=2, at=clock(900))
        # 첫 시도부터 5분을 썼다: 남은 5분
        self.assertEqual(self.eta(st, ["01", "02"], 1, 900, finish_median_s=0), (300, "약 5분 남음"))

    def test_finish_estimate_is_added_or_flagged(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        st.ticket("02")
        self.assertEqual(self.eta(st, ["01", "02"], 1, 600, finish_median_s=900), (1500, "약 25분 남음"))
        self.assertEqual(self.eta(st, ["01", "02"], 1, 600), (600, "약 10분 남음 + 마무리"))

    def test_no_sample_keeps_calculating_message(self):
        st = state.State(feature="f", started_at=clock(0))
        st.ticket("01")
        self.assertEqual(self.eta(st, ["01"], 1, 0, finish_median_s=900), (None, "남은 시간 계산 중"))

    def test_ticket_blocked_by_failure_is_not_counted(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        st.ticket("02").status = state.FAILED
        for tid in ("03", "04"):
            st.ticket(tid)
        deps = {"03": ["02"], "04": ["03"]}
        self.assertEqual(self.eta(st, ["01", "02", "03", "04"], 2, 600, deps=deps, finish_median_s=0), (0, "약 0분 남음"))

    def test_dependency_outside_scope_counts_as_done(self):
        st = state.State(feature="f", started_at=clock(0))
        merged(st, "01", 0, 600)
        st.ticket("02")
        self.assertEqual(self.eta(st, ["01", "02"], 1, 600, deps={"02": ["outside"]}, finish_median_s=0),
                         (600, "약 10분 남음"))

    def test_finishing_shows_remaining_finish_time(self):
        st = state.State(feature="f", started_at=clock(0), phase="finish")
        merged(st, "01", 0, 600)
        # 마무리 15분 중 5분을 썼다
        eta, text = self.eta(st, ["01"], 1, 900, finish_median_s=900)
        self.assertEqual((eta, text), (600, "약 10분 남음"))
        # 값이 없거나 넘겼거나 1분도 안 남았으면 마무리 중이다
        for at, finish in ((900, None), (600 + 900, 900), (600 + 1000, 900), (600 + 871, 900)):
            with self.subTest(at=at, finish=finish):  # 마지막은 29초 남아 0분으로 반올림되는 경우
                self.assertEqual(self.eta(st, ["01"], 1, at, finish_median_s=finish), (None, "마무리 중"))
        p = state.calculate_progress(st, ["01"], 1, at=clock(900), finish_median_s=900)
        self.assertIn("마무리 중(claude)", p["line"])

    def test_waiting_for_ci_uses_the_same_rule(self):
        st = state.State(feature="f", started_at=clock(0), phase="finish", finish={"phase": "checks_pending"})
        merged(st, "01", 0, 600)
        for at, finish, expected in ((1200, 1800, (1200, "약 20분 남음")), (1200, None, (None, "마무리 중")),
                                     (2400, 1800, (None, "마무리 중"))):
            with self.subTest(at=at, finish=finish):
                p = state.calculate_progress(st, ["01"], 1, at=clock(at), finish_median_s=finish)
                self.assertEqual((p["eta_s"], p["line"].split(" · ")[-1]), expected)
                self.assertIn("CI 대기 중", p["line"])
                self.assertNotIn("약 0분 남음", p["line"])

    def test_finishing_ignores_previous_run_tickets_for_finish_start(self):
        st = state.State(feature="f", started_at=clock(1000), phase="finish")
        merged(st, "01", 0, 600)  # 지난 실행에서 병합: 마무리는 이번 실행 시작부터 센다
        p = state.calculate_progress(st, ["01"], 1, prior={"01"}, at=clock(1300), finish_median_s=900)
        self.assertEqual(p["eta_s"], 600)

    def test_historical_basis_is_marked_after_the_finish_marker(self):
        st = state.State(feature="f", started_at=clock(0))
        st.ticket("01")
        p = state.calculate_progress(st, ["01"], 1, at=clock(0), history_median_s=600)
        self.assertTrue(p["line"].endswith("약 10분 남음 + 마무리(이전 실행 기준)"))
        p = state.calculate_progress(st, ["01"], 1, at=clock(0), history_median_s=600, finish_median_s=300)
        self.assertTrue(p["line"].endswith("약 15분 남음(이전 실행 기준)"))
        st.phase = "finish"
        p = state.calculate_progress(st, ["01"], 1, at=clock(0), history_median_s=600, finish_median_s=300)
        self.assertEqual(p["line"].split(" · ")[-1], "약 5분 남음")


if __name__ == "__main__":
    unittest.main()
