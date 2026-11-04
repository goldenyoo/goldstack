"""네트워크 대기 상한(v8 14): 회복은 다시 띄운 worker로만 판정하고, 끊김이 이어지면 상한에서 실제로 `중단(네트워크)`로 멈춘다."""
import contextlib
import io
import os
import textwrap
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_network_wait  # 모듈로 쓴다. 클래스를 이 모듈의 이름에 묶으면 그 시험이 여기서 또 돈다
from support import ticket

from gs import feature, go, state, transient, worker

ERROR = test_network_wait.ERROR_RESULT
ABORT_LINE = "■ 중단(네트워크): 다음 gs go가 이어 간다"
RECOVERED_LINE = "■ 네트워크 회복"
# 가짜 worker가 gs의 대기를 기다린다. 두 번째 대기가 잡혀 state.json에 보이면 넘어간다
AWAIT_SECOND_WAIT = """for i in $(seq 400); do grep -q '"count": 2' "$GS_WORKTREE/../../state.json" && break; sleep 0.02; done"""


class Base(support.GoTest):
    """가짜 claude를 실제 어댑터로 돌린다. 1분 = MINUTE초(GS_NETWORK_MINUTE)."""
    MINUTE = "1"

    fake = test_network_wait.NetworkTest.fake
    tickets = test_network_wait.NetworkTest.tickets
    limit = test_network_wait.NetworkTest.limit
    ticket_state = test_network_wait.NetworkTest.ticket_state

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.MINUTE})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")


class CapTest(Base):
    """대기 1분+2분 = 3초. 병렬 부하에서도 가짜 worker가 두 번째 대기 안에 끝나고, 30분 창은 30초다."""

    def test_three_transients_in_a_row_abort_at_limit(self):
        """티켓 하나: 1분+2분을 다 쓰고 세 번째 일시 오류에서 멈춘다."""
        self.limit(3)
        self.fake("claude", f"echo '{ERROR}'; exit 1\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn(ABORT_LINE, out)
        self.assertIn("대기 합계가 상한 3분을 넘었다", out)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures, ts.transient_errors), ("pending", 0, 3), out)

    def test_v7_report_reproduction(self):
        """v7 보고서 06: 함께 다시 뜬 12가 성공으로 끝나도 방금 끊긴 11의 대기가 취소되지 않고, 다음 gs go가 잇는다."""
        self.limit(3)
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 11 ]; then
              if [ "$n" = 1 ]; then for i in $(seq 200); do [ -f "$here/cut" ] && break; sleep 0.05; done; fi
              if [ "$n" -le 3 ]; then echo '{ERROR}'; exit 1; fi
              echo x > file_11; git add -A; git commit -qm t11; exit 0
            fi
            if [ "$n" = 1 ]; then
              echo x > file_12; git add -A; git commit -qm t12; touch "$here/cut"; echo '{ERROR}'; exit 1
            fi
            {AWAIT_SECOND_WAIT}
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 3, out + err)
        self.assertIn(ABORT_LINE, out)
        self.assertNotIn(RECOVERED_LINE, out)
        self.assertEqual(self.ticket_state("11").transient_errors, 3, out)
        twelve = self.ticket_state("12")
        self.assertEqual((twelve.status, twelve.failures), ("pending", 0), out)
        self.assertTrue(twelve.network_resume["done"])  # 성공한 12는 리뷰부터 잇는다
        self.assertEqual(self.lines("review.calls"), [])

        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ticket_state("11").status, "merged")
        self.assertEqual(self.ticket_state("12").status, "merged")

    def test_running_ticket_succeeding_during_wait_keeps_wait_and_aborts(self):
        """처음부터 돌던 12가 대기 중에 성공으로 끝나도 11은 대기를 다 쓰고 상한에서 멈춘다."""
        self.limit(3)
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 11 ]; then echo '{ERROR}'; exit 1; fi
            {AWAIT_SECOND_WAIT}
            echo x > file_12; git add -A; git commit -qm t12
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 3, out + err)
        self.assertIn(ABORT_LINE, out)
        self.assertNotIn(RECOVERED_LINE, out)
        self.assertEqual(self.ticket_state("11").transient_errors, 3, out)
        self.assertEqual((self.ticket_state("12").attempts, self.ticket_state("12").transient_errors), (1, 0))
        self.assertTrue(self.ticket_state("12").network_resume["done"])

    def test_probe_ending_does_not_cancel_wait_of_ticket_cut_while_it_ran(self):
        """11이 다시 떠 도는 동안 12가 끊겼다. 11이 끝나도 12의 대기와 합계는 그대로라 12의 다음 일시 오류에서 멈춘다."""
        self.limit(3)
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 11 ]; then
              if [ "$n" = 1 ]; then echo '{ERROR}'; exit 1; fi
              {AWAIT_SECOND_WAIT}
              echo x > file_11; git add -A; git commit -qm t11; exit 0
            fi
            if [ "$n" = 1 ]; then
              for i in $(seq 400); do grep -q 'start 11 2' "$here/events.log" && break; sleep 0.02; done
            fi
            echo '{ERROR}'; exit 1
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn(RECOVERED_LINE, out)
        self.assertEqual(self.ticket_state("12").transient_errors, 2, out)

    def _chain(self, body):
        self.fake("claude", textwrap.dedent(body))
        self.tickets({"11": ticket("11"), "12": ticket("12", '["11"]'), "13": ticket("13", '["12"]')})

    def test_cut_again_within_window_continues_total(self):
        """회복을 두 번 거쳐도 누계가 이어져, 세 번째 끊김의 첫 일시 오류에서 멈춘다(창 30초 안)."""
        self.limit(3)
        self._chain(f'''\
            if [ "$n" = 1 ]; then echo '{ERROR}'; exit 1; fi
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        ''')
        code, out, err = self.go("--only", "11,12,13")
        self.assertEqual(code, 3, out + err)
        self.assertIn(ABORT_LINE, out)
        self.assertEqual(out.count(RECOVERED_LINE), 2, out)
        self.assertIn("네트워크 대기(2회", out)  # 일정도 이어진다
        self.assertEqual(self.ticket_state("12").status, "merged")
        self.assertEqual(self.ticket_state("13").status, "pending")


class NewOutageTest(Base):
    """30분 창을 실제로 넘긴다: 1분 0.05초면 창은 1.5초다."""
    MINUTE = "0.05"

    def test_cut_after_normal_running_past_window_is_new_outage(self):
        """상한을 다 쓴 뒤 회복해도, 창을 넘겨 정상으로 돌았으면 새 끊김이라 멈추지 않는다."""
        self.limit(1)  # 첫 대기 1번으로 상한을 다 쓴다
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 12 ] && [ "$n" = 1 ]; then sleep 2; fi
            if [ "$n" = 1 ]; then echo '{ERROR}'; exit 1; fi
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12", '["11"]')})
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(ABORT_LINE, out)
        self.assertEqual(out.count(RECOVERED_LINE), 2, out)
        self.assertNotIn("네트워크 대기(2회", out)
        self.assertEqual(self.ticket_state("12").transient_errors, 1)


class TickTest(unittest.TestCase):
    """`_net_tick`·`_net_hold`의 판정을 시계 없이 본다. 1분 = 60초."""

    def setUp(self):
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "60"})
        patch.start()
        self.addCleanup(patch.stop)

    def run_(self, n, *order):
        return SimpleNamespace(net=n, st=state.State("demo"), order=list(order), save=lambda: None,
                               cfg=SimpleNamespace(timeouts=SimpleNamespace(network_wait_minutes=60)))

    def active(self, tid, code=0):
        t = feature.Ticket(tid, "t", [], [], "claude", "codex", "", "", Path(f"{tid}.md"))
        return go.Active(t, worker.Finished(worker.Job(t, Path("."), Path(".")), code), "b", Path("."), "0")

    def outage(self):
        n = go.Outage()
        n.backoff.next(60)
        return n

    def waiting(self, n, tid):
        n.waiting[tid] = self.active(tid)
        n.due = time.monotonic() + 1000
        n.wait_started = n.last_error = time.monotonic()

    def tick(self, r, active, resume=None):
        out = io.StringIO()
        with mock.patch("gs.go._resume", side_effect=resume or AssertionError("다시 띄우면 안 된다")), \
                contextlib.redirect_stdout(out):
            go._net_tick(r, active, None)
        return out.getvalue()

    def assert_still_waiting(self, n, due):
        self.assertEqual(n.due, due)
        self.assertIn("11", n.waiting)
        self.assertEqual((n.backoff.count, n.backoff.waited), (1, 1))
        self.assertIsNone(n.ended_at)

    def test_probe_ended_during_wait_is_not_recovery(self):
        n = self.outage()
        self.waiting(n, "11")
        due = n.due
        n.probes.add("12")
        n.parked["12"] = self.active("12")
        active = {}
        out = self.tick(self.run_(n, "11", "12"), active)
        self.assertNotIn(RECOVERED_LINE, out)
        self.assert_still_waiting(n, due)
        self.assertEqual(n.probes, set())  # 끝난 probe가 남아 대기 뒤에 회복으로 읽히지 않는다
        self.assertIn("12", n.parked)
        self.assertEqual(active, {})

    def test_quiet_probe_during_wait_does_not_cancel_wait(self):
        n = self.outage()
        self.waiting(n, "11")
        due = n.due
        n.last_error -= 10_000
        n.probes.add("12")
        active = {"12": self.active("12")}
        active["12"].started -= 10_000
        out = self.tick(self.run_(n, "11", "12"), active)
        self.assertNotIn(RECOVERED_LINE, out)
        self.assert_still_waiting(n, due)
        self.assertEqual(n.probes, {"12"})

    def test_running_worker_that_is_not_probe_is_not_recovery(self):
        n = self.outage()
        n.probes.add("11")
        n.last_error = time.monotonic() - 10_000
        probe, other = self.active("11"), self.active("12")
        other.started -= 10_000  # 다시 띄운 worker가 아니다. 얼마를 돌았든 근거가 아니다
        out = self.tick(self.run_(n, "11", "12"), {"11": probe, "12": other})
        self.assertNotIn(RECOVERED_LINE, out)
        self.assertEqual(n.probes, {"11"})

    def test_due_wait_restarts_workers_as_probes(self):
        n = self.outage()
        self.waiting(n, "11")
        n.due = time.monotonic() - 1
        r = self.run_(n, "11")
        r.st.ticket("11").network_resume = {"x": 1}
        started = self.active("11")
        started.proc = SimpleNamespace(job=started.proc.job)  # 실제로 띄운 worker
        active = {}
        out = self.tick(r, active, resume=[started])
        self.assertEqual(n.probes, {"11"})
        self.assertIs(active["11"], started)
        self.assertIsNone(n.due)
        self.assertNotIn(RECOVERED_LINE, out)

    def test_stand_in_for_fix_worker_that_could_not_restart_is_not_probe(self):
        """다시 띄우지 못한 수정 worker의 자리표시는 일시 오류 없이 끝난 worker가 아니다."""
        n = self.outage()
        self.waiting(n, "11")
        n.due = time.monotonic() - 1
        r = self.run_(n, "11")
        stand_in = self.active("11", code=1)
        active = {}
        out = self.tick(r, active, resume=[stand_in])
        self.assertEqual(n.probes, set())
        self.assertIs(active["11"], stand_in)
        self.assertNotIn(RECOVERED_LINE, out)  # 끊김은 끝나지만(기다릴 것이 없다) 회복을 본 것은 아니다
        self.assertIsNotNone(n.ended_at)
        self.assertEqual(n.backoff.count, 1)

    def test_no_worker_restarted_ends_wait_without_recovery(self):
        """다시 띄우지 못해 티켓만 실패했다. 기다릴 것이 없어 끊김은 끝나지만 누계는 남고 회복을 본 것은 아니다."""
        n = self.outage()
        self.waiting(n, "11")
        n.due = time.monotonic() - 1
        out = self.tick(self.run_(n, "11"), {}, resume=[None])
        self.assertNotIn(RECOVERED_LINE, out)
        self.assertIn("네트워크 대기 끝", out)
        self.assertFalse(n.active)
        self.assertIsNotNone(n.ended_at)
        self.assertEqual(n.backoff.count, 1)

    def test_probe_ended_without_wait_is_recovery_and_keeps_total(self):
        n = self.outage()
        n.probes.add("12")
        parked = self.active("12")
        n.parked["12"] = parked
        active = {}
        out = self.tick(self.run_(n, "12"), active)
        self.assertIn(RECOVERED_LINE, out)
        self.assertFalse(n.active)
        self.assertIs(active["12"], parked)
        self.assertEqual((n.backoff.count, n.backoff.waited), (1, 1))  # 회복해도 누계가 남는다
        self.assertIsNotNone(n.ended_at)

    def test_quiet_time_counts_from_last_transient_of_any_ticket(self):
        """오래 돈 probe도 마지막 일시 오류 뒤로 5분을 채워야 회복이다. 다른 티켓이 방금 끊겼으면 아니다."""
        n = self.outage()
        n.probes.add("11")
        probe = self.active("11")
        probe.started -= 10_000
        n.last_error = time.monotonic() - transient.RECOVERY_MINUTES * 60 + 100
        r = self.run_(n, "11")
        self.assertNotIn(RECOVERED_LINE, self.tick(r, {"11": probe}))
        self.assertEqual(n.probes, {"11"})
        n.last_error -= 200
        self.assertIn(RECOVERED_LINE, self.tick(r, {"11": probe}))
        self.assertEqual(n.probes, set())

    def test_recovered_by_quiet_probe_needs_five_minutes(self):
        n = self.outage()
        n.probes.add("11")
        n.last_error = time.monotonic() - 10_000
        probe = self.active("11")
        probe.started = time.monotonic() - transient.RECOVERY_MINUTES * 60 + 100
        r = self.run_(n, "11")
        self.assertNotIn(RECOVERED_LINE, self.tick(r, {"11": probe}))
        probe.started -= 200
        self.assertIn(RECOVERED_LINE, self.tick(r, {"11": probe}))

    def hold_after(self, seconds):
        """끊김이 seconds초 전에 끝난 뒤 새 일시 오류가 났다. Outage를 돌려준다."""
        n = self.outage()
        n.ended_at = time.monotonic() - seconds
        r = self.run_(n, "11")
        with contextlib.redirect_stdout(io.StringIO()):
            go._net_hold(r, self.active("11"), "연결")
        return n

    def test_cut_within_thirty_minutes_is_same_outage(self):
        n = self.hold_after(30 * 60 - 60)
        self.assertEqual((n.backoff.count, n.backoff.waited), (2, 3))  # 1분 + 이어진 2분
        self.assertIsNone(n.ended_at)
        self.assertLess(n.due - time.monotonic(), 2 * 60 + 1)
        self.assertGreater(n.due - time.monotonic(), 60)

    def test_cut_past_thirty_minutes_is_new_outage(self):
        n = self.hold_after(30 * 60 + 60)
        self.assertEqual((n.backoff.count, n.backoff.waited), (1, 1))  # 새로 센다
        self.assertIsNone(n.ended_at)

    def test_cut_while_outage_is_open_continues_total(self):
        n = self.outage()
        n.probes.add("11")
        r = self.run_(n, "11")
        with contextlib.redirect_stdout(io.StringIO()):
            go._net_hold(r, self.active("11"), "연결")
        self.assertEqual((n.backoff.count, n.backoff.waited), (2, 3))

    def test_cut_past_limit_within_window_aborts(self):
        n = go.Outage()
        n.backoff.next(1)
        n.ended_at = time.monotonic()
        r = self.run_(n, "11")
        r.cfg.timeouts.network_wait_minutes = 1
        with self.assertRaises(transient.NetworkAbort), contextlib.redirect_stdout(io.StringIO()):
            go._net_hold(r, self.active("11"), "연결")


if __name__ == "__main__":
    unittest.main()
