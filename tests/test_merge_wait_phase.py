"""goldstack-v39 03: 병합 줄에서 다른 티켓의 검증을 기다린 시간은 단계 `merge_wait`(`병합 대기`)로 남는다.

대기 순서는 시간이 아니라 가짜 검증의 파일 신호로 만든다(test_async_verify와 같은 fixture).
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from test_async_verify import Base

from gs import report, state


def clock(minute):
    return f"2026-11-01T01:{minute:02d}:00-08:00"


class MergeWaitPhaseTest(Base):
    def test_ticket_that_queues_behind_a_verify_gets_a_merge_wait_phase(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        with self.when_queued("12", lambda: self.signal("release_11")):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(out.count("[12] 병합 대기: 11 검증 중"), 1, out)
        self.assertEqual(self.merged(), ["11", "12"])
        phases = self.phases("12")
        self.assertIn("merge_wait", phases, phases)
        at = phases.index("merge_wait")
        self.assertEqual(phases[at + 1], "verify", phases)  # 다음 단계가 verify다
        self.assertIn(phases[at - 1], ("review", "rereview"), phases)  # 앞은 리뷰나 재리뷰다
        self.assertEqual(phases.count("merge_wait"), 1, phases)
        closed = [p for p in self.ts("12").phases if p["phase"] == "merge_wait"]
        self.assertTrue(closed[0]["ended_at"], closed)

    def test_ticket_that_does_not_queue_has_no_merge_wait_phase(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        with self.when_queued("12", lambda: self.signal("release_11")):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertNotIn("merge_wait", self.phases("11"))
        self.assertIn("verify", self.phases("11"))


class MergeWaitReportTest(unittest.TestCase):
    def test_report_shows_merge_wait_before_verify_and_old_state_still_loads(self):
        self.assertEqual(state.PHASE_LABELS["merge_wait"], "병합 대기")
        order = list(state.PHASE_LABELS)
        self.assertEqual(order.index("merge_wait") + 1, order.index("verify"))
        with tempfile.TemporaryDirectory() as tmp:
            rundir = Path(tmp) / ".goldstack/work/f/run"
            rundir.mkdir(parents=True)
            st = state.State(feature="f", started_at=clock(0))
            ts = st.ticket("01")
            for phase, start in (("worker", 0), ("review", 10), ("merge_wait", 20), ("verify", 25)):
                state.begin_phase(ts, phase, "claude", attempt=1, at=clock(start))
            state.end_phase(ts, clock(28))
            old = st.ticket("02")  # 이 단계가 없는 옛 기록
            for phase, start in (("worker", 0), ("review", 10), ("verify", 20)):
                state.begin_phase(old, phase, "claude", attempt=1, at=clock(start))
            state.end_phase(old, clock(23))
            r = SimpleNamespace(st=st, order=["01", "02"], rundir=rundir,
                                feat=SimpleNamespace(tickets={t: SimpleNamespace(title="t") for t in ("01", "02")},
                                                     spec=SimpleNamespace(verify="true")))
            text = report.evidence(r)
            self.assertIn("- 01 단계별 소요: worker 10분 · 리뷰 10분 · 병합 대기 5분 · 검증 3분\n", text)
            self.assertIn("- 02 단계별 소요: worker 10분 · 리뷰 10분 · 검증 3분\n", text)
            state.save(rundir, st)
            self.assertEqual(state.load(rundir, "f").ticket("01").phases, ts.phases)


if __name__ == "__main__":
    unittest.main()
