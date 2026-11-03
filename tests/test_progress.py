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
            "elapsed_s": 1440, "eta_s": 2400,
            "line": "▓▓▓░░░░░ goldstack-v2 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음"})

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
        self.assertEqual((p["done"], p["total"], p["eta_s"]), (4, 5, 120))
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


if __name__ == "__main__":
    unittest.main()
