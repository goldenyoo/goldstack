"""goldstack-v37 01: 티켓 검증 호출(verify.run)은 루프 밖 스레드에서 돈다. 그동안 루프는 worker 끝·리뷰·수정 worker·새 worker를 처리하고,
병합·검증은 한 번에 하나다(다른 티켓은 줄을 선다). 다른 티켓 경로의 integration 되돌리기는 검증 반영 뒤로 미룬다.

가짜 검증(VERIFY)은 파일 신호로 멈췄다 풀린다. 순서는 시간이 아니라 신호와 events.log로 본다(test_async_review와 같다).
기다리는 상한은 잘못됐을 때 시험이 끝나게 하는 안전장치다: 넘기면 timeouts에 남고 시험이 실패한다.
"""
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_async_review
from support import alive, group_alive, kill_quietly
from test_second_review import finding

from gs import config, go, state, transient, verify

# 가짜 검증: 병합 중인 티켓(index에 새로 든 start_<id>)마다 몇 번째 검증인지 세고, 그 검증의 신호 파일을 본다.
#   hold_<id>_<n>: verifying_<id>를 만들고 release_<id>가 생길 때까지 멈춘다. 그동안 자식(sleep)을 띄워 둔다(프로세스 그룹이 끝나는지 본다)
#   term_<id>_<n>: 끝에 스스로 SIGTERM으로 죽는다(검증 끊김).  fail_<id>_<n>: 떨어진다
# 검증이 본 integration의 티켓 파일을 seen_<id>_<n>에 남긴다. 티켓이 없는 검증(마무리)은 그냥 통과한다.
VERIFY = """\
here="{bin}"
tid="$(git diff --cached --name-only | sed -n 's/^start_//p' | head -n 1)"
[ -n "$tid" ] || exit 0
n=$(( $(cat "$here/verifies_$tid" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/verifies_$tid"
echo "verify $tid $n" >> "$here/events.log"
ls start_* > "$here/seen_${{tid}}_$n"
if [ -f "$here/hold_${{tid}}_$n" ]; then
  echo $$ > "$here/verify_pid_$tid"
  sleep 300 & child=$!
  echo $child > "$here/verify_child_$tid"
  echo up > "$here/verifying_$tid"
  for i in $(seq 3000); do [ -f "$here/release_$tid" ] && break; sleep 0.02; done
  [ -f "$here/release_$tid" ] || echo "release $tid" >> "$here/timeouts"
  kill $child
fi
echo "verify-end $tid $n" >> "$here/events.log"
[ -f "$here/term_${{tid}}_$n" ] && kill -TERM $$
[ -f "$here/fail_${{tid}}_$n" ] && exit 1
exit 0
"""
IS_REPAIR = 'grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"'


class Base(test_async_review.Base):
    def setup_verify(self, workers, *tids):
        self.setup_tickets(workers, *tids)
        (self.bin / "verify.sh").write_text(VERIFY.format(bin=self.bin))
        support.GoTest.parallel(self, workers, verify=f"bash {self.bin / 'verify.sh'}")

    def signal(self, *names):
        for name in names:
            (self.bin / name).touch()

    def verifies(self):
        return [line for line in self.events() if line.startswith("verify ")]

    def when_queued(self, tid, then):
        """tid가 병합 줄에 서면(_merge 뒤) then을 한 번 부른다."""
        real, fired = go._merge, []

        def merge(r, a):
            real(r, a)
            if not fired and any(e.a.t.id == tid for e in r.merges.queue):
                fired.append(True)
                then()
        return mock.patch.object(go, "_merge", merge)

    def assert_verify_gone(self, tid):
        for name in (f"verify_pid_{tid}", f"verify_child_{tid}"):
            pid = int((self.bin / name).read_text())
            self.addCleanup(kill_quietly, pid)
            for _ in range(100):  # 고아는 init이 거둔다
                if not alive(pid):
                    break
                time.sleep(0.05)
            self.assertFalse(alive(pid), f"검증 프로세스가 살아 있다: {name}")


class LoopGoesOnTest(Base):
    def test_review_and_fix_worker_go_on_while_a_verify_runs(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        self.answer_file("review_12", findings=[finding("FIX A: 값이 틀렸다")])
        self.answer_file("rereview_12", verdicts=[{"id": 1, "status": "resolved", "evidence": "확인"}], findings=[])
        self.hook("fix_12", 'touch "$here/release_11"\n')  # 12의 수정 worker가 떠야 11의 검증이 풀린다
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12"])
        for line in ("end 12", "review 12", "review-end 12", "fix 12"):
            self.before("verify 11 1", line)
            self.before(line, "verify-end 11 1")
        self.assertEqual(self.ts("12").review["findings"][0]["rereview"], "resolved")

    def test_loop_waits_for_a_verify_that_is_all_that_is_left(self):
        self.setup_verify(1, "11")
        self.signal("hold_11_1")
        real, seen = go._wait_any, []

        def wait_any(r, active, runner, *, once=False):
            if not seen and not active and (self.bin / "verifying_11").exists():
                seen.append(once)
                self.signal("release_11")  # 검증만 남은 루프가 여기까지 왔다
            return real(r, active, runner, once=once)

        with mock.patch.object(go, "_wait_any", wait_any):
            code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(seen, [True])
        self.assertEqual(self.merged(), ["11"])

    def test_finished_verify_is_merged_while_another_worker_runs(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        # 12의 worker는 11의 검증을 풀고, 11이 integration에 병합될 때까지 끝나지 않는다
        self.hook("start_12", textwrap.dedent("""\
            await "$here/verifying_11" up
            touch "$here/release_11"
            for i in $(seq 3000); do git log --format=%B gs/demo/integration | grep -q 'gs-ticket: demo/11' && break; sleep 0.02; done
            git log --format=%B gs/demo/integration | grep -q 'gs-ticket: demo/11' || echo "merge 11" >> "$here/timeouts"
        """))
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12"])
        self.before("verify-end 11 1", "end 12")


class LineTest(Base):
    def test_ticket_whose_turn_comes_during_a_verify_waits_in_line(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        with self.when_queued("12", lambda: self.signal("release_11")):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(out.count("[12] 병합 대기: 11 검증 중"), 1, out)
        self.assertEqual(self.verifies(), ["verify 11 1", "verify 12 1"])
        self.before("verify-end 11 1", "verify 12 1")
        self.assertEqual(self.lines("seen_12_1"), ["start_11", "start_12"])  # 11을 반영한 integration 위에서 검증했다
        log = self.integration("log", "--first-parent", "--format=%s", "gs/demo/integration")
        self.assertLess(log.index("Merge 12"), log.index("Merge 11"), log)  # 최근 것이 위다
        self.assertEqual(self.merged(), ["11", "12"])

    def test_failed_verify_lets_the_waiting_ticket_merge_without_it(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1", "fail_11_1")
        self.hook("start_11", f"if {IS_REPAIR}; then exit 0; fi  # 수리 worker는 고치지 못한다\n")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        with self.when_queued("12", lambda: self.signal("release_11")):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(out.count("[12] 병합 대기: 11 검증 중"), 1, out)
        self.before("verify-end 11 1", "verify 12 1")
        self.assertEqual(self.lines("seen_12_1"), ["start_12"])  # 11 없는 integration 위에서 병합·검증했다
        log = self.integration("log", "--first-parent", "--format=%s", "gs/demo/integration")
        self.assertLess(log.index("Merge 11"), log.index("Merge 12"), log)  # 12가 먼저 병합됐다
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.merged(), ["11", "12"])

    def test_interrupted_verify_runs_again_ahead_of_the_line_on_the_same_tree(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1", "term_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        with self.when_queued("12", lambda: self.signal("release_11")):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertIn("[11] 검증 끊김(종료 코드 ", out)
        self.assertEqual(out.count("[12] 병합 대기: 11 검증 중"), 1, out)
        self.assertEqual(self.verifies(), ["verify 11 1", "verify 11 2", "verify 12 1"])  # 줄 선 12가 끼어들지 않는다
        rows = [x for x in state.load(self.rundir, "demo").metrics["validations"] if x["label"].startswith("ticket-11")]
        self.assertEqual([x["label"] for x in rows], ["ticket-11-끊김", "ticket-11"])
        self.assertEqual(rows[0]["tree_sha"], rows[1]["tree_sha"])
        self.assertEqual(rows[0]["ticket_head"], rows[1]["ticket_head"])
        self.assertEqual(self.lines("seen_11_2"), ["start_11"])
        self.assertEqual(self.merged(), ["11", "12"])


class IntegrationResetTest(Base):
    def test_another_tickets_error_does_not_undo_the_merge_being_verified(self):
        self.setup_verify(2, "11", "13")
        self.signal("hold_11_1")
        self.hook("start_13", 'await "$here/verifying_11" up\n')
        real_check, real_error, broke = go._check_worker, go._ticket_error, []

        def check(r, a, *args, **kw):
            if a.t.id == "13" and not broke:
                broke.append(True)
                raise OSError("결과 처리 시험 오류")
            return real_check(r, a, *args, **kw)

        def error(r, a, e):
            real_error(r, a, e)
            if a.t.id == "13":
                self.signal("release_11")  # 13의 오류 처리(integration 되돌리기 포함)가 11의 검증 도중에 끝났다

        with mock.patch.object(go, "_check_worker", check), mock.patch.object(go, "_ticket_error", error):
            code, out, err = self.go(*self.only("11", "13"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertIn("[13] 실패: worker 결과 처리 중 오류: OSError: 결과 처리 시험 오류", out)
        self.assertNotIn("검증하는 동안 integration이 바뀌었다", out)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("Merge 11: t11", self.integration("log", "--format=%s", "gs/demo/integration"))
        self.assertEqual(self.verifies(), ["verify 11 1", "verify 13 1"])
        self.assertEqual(self.lines("seen_13_1"), ["start_11", "start_13"])  # 미룬 되돌리기가 11의 병합을 지우지 않았다
        self.assertEqual(self.merged(), ["11", "13"])


class StopTest(Base):
    def test_stopped_during_the_first_verify_leaves_no_process_and_starts_over(self):
        self.setup_verify(1, "11")
        self.signal("hold_11_1")
        with self.leave_when(self.bin / "verifying_11", KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.go(*self.only("11"))
        self.assert_verify_gone("11")
        self.assert_no_timeouts()  # 검증이 풀리기를 기다리다 스스로 끝난 것이 아니다
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.network_resume), (state.RUNNING, {}))
        code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("[11] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 새로 시작한다", out)
        self.assertEqual(self.calls(), ["11", "11"])
        self.assertEqual(self.merged(), ["11"])

    def test_stopped_during_the_second_run_continues_with_it(self):
        self.setup_verify(1, "11")
        self.signal("term_11_1", "hold_11_2")
        with self.leave_when(self.bin / "verifying_11", KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.go(*self.only("11"))
        self.assert_verify_gone("11")
        self.assert_no_timeouts()  # 검증이 풀리기를 기다리다 스스로 끝난 것이 아니다
        self.assertTrue(self.ts("11").network_resume["verify_again"])
        code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("[11] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 끊긴 검증을 같은 worktree에서 다시 한다", out)
        self.assertEqual(self.calls(), ["11"])
        self.assertEqual(self.verifies(), ["verify 11 1", "verify 11 2", "verify 11 3"])
        self.assertEqual(self.merged(), ["11"])

    def test_network_abort_waits_for_the_verify_and_does_not_start_the_line(self):
        self.setup_verify(2, "11", "12")
        self.signal("hold_11_1")
        self.hook("start_12", 'await "$here/verifying_11" up\n')
        real, fired = go._wait_any, []

        def wait_any(r, active, runner, *, once=False):
            if not fired and r.merges.queue:  # 11의 검증 중에 12가 줄을 섰다
                fired.append(True)
                self.signal("release_11")
                raise transient.NetworkAbort("시험 끊김")
            return real(r, active, runner, once=once)

        with mock.patch.object(go, "_wait_any", wait_any):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, go.EXIT_NETWORK, out + err)
        self.assert_no_timeouts()
        line = "■ 중단(네트워크): 11 검증을 마치고 멈춘다"
        self.assertIn(line, out)
        self.assertLess(out.index(line), out.index("[11] 검증 통과 → integration 병합"))
        self.assertEqual(self.ts("11").status, state.MERGED)
        self.assertEqual(self.verifies(), ["verify 11 1"])  # 줄 선 12는 시작하지 않았다
        ts = self.ts("12")
        self.assertEqual((ts.status, ts.reason, ts.network_resume["done"], ts.network_resume["reviewed"]),
                         (state.PENDING, go.NETWORK_ABORT, True, True))
        reviews = self.lines("review.calls")
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("[12] 지난 리뷰는 끝났다. 수정 worker 또는 병합으로 잇는다", out)
        self.assertEqual(self.calls(), ["11", "12"])  # 12의 worker도
        self.assertEqual(self.lines("review.calls"), reviews)  # 리뷰도 다시 하지 않는다
        self.assertEqual(self.merged(), ["11", "12"])


class CancelTest(unittest.TestCase):
    """verify.run의 취소 통로: 서면 도는 명령의 프로세스 그룹을 끝내고, 판별·재시도의 다음 명령을 띄우지 않는다."""

    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.log = self.dir / "verify.log"
        patch = mock.patch.dict("os.environ", {"GS_VERIFY_TIMEOUT": ""})
        patch.start()
        self.addCleanup(patch.stop)

    def run_verify(self, command, cancel, *, retries=0, triage=None, unchanged=None):
        spec = SimpleNamespace(verify=command, verify_minutes=1, verify_retries=retries)
        with self.log.open("w", encoding="utf-8") as f:
            return verify.run(spec, self.dir, f, triage, unchanged, cancel)

    def cancel_on_check(self, cancel):
        """트리 확인(unchanged)이 불리는 때, 곧 다음 명령을 띄우기 직전에 취소한다."""
        def unchanged():
            cancel.set()
            return True
        return unchanged

    def test_cancel_before_a_retry_launches_nothing_more(self):
        cancel = threading.Event()
        triage = config.VerifyConfig(r"^NOMATCH (\S+)$", f"echo {{file}} >> {self.dir}/reruns", 3)
        with self.assertRaises(verify.Cancelled):
            self.run_verify(f"echo run >> {self.dir}/runs; exit 1", cancel, retries=1, triage=triage,
                            unchanged=self.cancel_on_check(cancel))
        self.assertEqual((self.dir / "runs").read_text().splitlines(), ["run"])
        self.assertNotIn("검증 재시도", self.log.read_text())

    def test_cancel_before_a_triage_run_launches_nothing_more(self):
        cancel = threading.Event()
        triage = config.VerifyConfig(r"^FAIL: (\S+)$", f"echo {{file}} >> {self.dir}/reruns", 3)
        with self.assertRaises(verify.Cancelled):
            self.run_verify(f"echo run >> {self.dir}/runs; echo 'FAIL: test_a'; exit 1", cancel, retries=1, triage=triage,
                            unchanged=self.cancel_on_check(cancel))
        self.assertEqual((self.dir / "runs").read_text().splitlines(), ["run"])
        self.assertFalse((self.dir / "reruns").exists())
        self.assertNotIn("판별 종료 코드", self.log.read_text())

    def test_cancel_during_a_command_ends_its_process_group(self):
        cancel, ready = threading.Event(), self.dir / "ready"

        def cancel_when_ready():
            deadline = time.monotonic() + 60
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            cancel.set()

        helper = threading.Thread(target=cancel_when_ready)
        helper.start()
        try:
            with self.assertRaises(verify.Cancelled):
                self.run_verify(f"sleep 300 & echo $! > {self.dir}/child; echo $$ > {self.dir}/leader; touch {ready}; wait",
                                cancel, retries=1)
        finally:
            helper.join()
        self.assertTrue(ready.exists())
        leader, child = (int((self.dir / name).read_text()) for name in ("leader", "child"))
        for pid in (leader, child):
            self.addCleanup(kill_quietly, pid)
        self.assertFalse(group_alive(leader))
        self.assertFalse(alive(child))
        self.assertNotIn("종료 코드:", self.log.read_text())  # 결과가 없다: 재시도도 하지 않았다

    def test_unset_cancel_runs_to_the_end_and_a_set_one_launches_nothing(self):
        cancel = threading.Event()
        res = self.run_verify(f"echo run >> {self.dir}/runs; exit 0", cancel)
        self.assertTrue(res.ok)
        cancel.set()
        with self.assertRaises(verify.Cancelled):  # 이미 선 취소는 첫 명령도 띄우지 않는다
            self.run_verify(f"echo run >> {self.dir}/runs; exit 0", cancel)
        self.assertEqual((self.dir / "runs").read_text().splitlines(), ["run"])


if __name__ == "__main__":
    unittest.main()
