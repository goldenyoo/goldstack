"""goldstack-v9 06: 리뷰는 루프 밖 스레드에서 돈다. 그동안 다른 worker가 처리되고, 리뷰 중인 티켓은 worker 자리를 쓰지 않고, state는 루프만 고친다.

가짜 리뷰어·worker는 파일 신호로 서로를 기다린다(await). 순서는 시간이 아니라 신호와 events.log로 본다. 기다리는 상한은 잘못됐을 때 시험이 끝나게 하는
안전장치다: 넘기면 timeouts에 남고 시험이 실패한다.
"""
import json
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
import unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_network_wait
import test_recheck_resolved
import test_review_network
import test_rereview
from support import alive, sh, ticket
from test_review_network import AGY_DOWN, CODEX_DOWN
from test_second_review import finding

from gs import config, go, review, state, transient

AWAIT = """\
await() {  # await <파일> <패턴>: 파일에 패턴이 나올 때까지 기다린다. 못 보면 시험이 잡도록 남긴다
  for i in $(seq 3000); do grep -q "$2" "$1" 2>/dev/null && return 0; sleep 0.02; done
  echo "$1 $2" >> "$here/timeouts"; return 1
}
"""
# 티켓별 동작은 <kind>_<티켓>.sh 훅으로 끼운다. kind는 start(구현), fix(수정), review, rereview다.
WORKER = 'here="$(dirname "$0")"\nstatus="$GS_WORKTREE/../../state.json"\n' + AWAIT + """\
kind=start; grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF" && kind=fix
echo "$GS_TICKET" >> "$here/calls.log"
echo "$kind $GS_TICKET" >> "$here/events.log"
trap 'echo "end $GS_TICKET" >> "$here/events.log"' EXIT
hook="$here/${kind}_$GS_TICKET.sh"; [ -f "$hook" ] && . "$hook"
echo "$kind" > "${kind}_$GS_TICKET"; git add -A; git commit -qm "$kind $GS_TICKET"
[ -f "$here/dirty_$GS_TICKET" ] && echo left > "pending_$GS_TICKET"
exit 0
"""
REVIEWER = 'here="$(dirname "$0")"\n' + AWAIT + """\
in="$(mktemp)"; cat > "$in"
tid="$(grep -o 'tickets/[0-9]*-t.md' "$in" | head -n 1 | sed 's/tickets.//; s/-t.md//')"
kind=review; grep -q '"verdicts"' "$in" && kind=rereview
echo "$kind $tid" >> "$here/events.log"
echo "$GS_REVIEWER" >> "$here/review.calls"
hook="$here/${kind}_$tid.sh"; [ -f "$hook" ] && . "$hook"
echo "$kind-end $tid" >> "$here/events.log"
answer="$here/${kind}_$tid.json"
if [ -f "$answer" ]; then cat "$answer"; elif [ "$kind" = review ]; then echo '{"findings": []}'
else echo '{"verdicts": [], "findings": []}'; fi
"""
# 리뷰어를 붙잡아 둔다: 자식까지 프로세스 그룹에 두고 끝날 때까지 돈다. 붙잡힌 것을 reviewing_<티켓>으로 알린다.
HOLD = 'sleep 300 & echo $! > "$here/child_$tid"; echo $$ > "$here/leader_$tid"; echo up > "$here/reviewing_$tid"; wait\n'


def await_ends(count):
    return f"""for i in $(seq 3000); do [ "$(grep -c '^end' "$here/events.log")" -ge {count} ] && break; sleep 0.02; done
[ "$(grep -c '^end' "$here/events.log")" -ge {count} ] || echo "ends {count}" >> "$here/timeouts"
"""


def peak(events, begins, ends):
    """events 안에서 동시에 돈 수의 최댓값. begins·ends는 줄 앞머리다."""
    now = top = 0
    for line in events:
        word = line.split()[0]
        now += (word in begins) - (word in ends)
        top = max(top, now)
    return top


class Base(test_rereview.Base):
    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.sh").write_text(REVIEWER)

    def setup_tickets(self, workers, *tids, deps=None, reviewer="codex"):
        self.tickets(**{tid: ("claude", reviewer, None, (deps or {}).get(tid, "[]")) for tid in tids})
        spec = (self.repo / ".goldstack/work/demo/spec.md").read_text()
        if f"max_workers: {workers}\n" not in spec:
            support.GoTest.parallel(self, workers)

    def only(self, *tids):
        return "--only", ",".join(tids)

    def hook(self, name, body):
        (self.bin / f"{name}.sh").write_text(body)

    def answer_file(self, name, **data):
        (self.bin / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False))

    def events(self):
        return self.lines("events.log")

    def before(self, first, then):
        events = self.events()
        self.assertLess(events.index(first), events.index(then), events)

    def assert_no_timeouts(self):
        self.assertEqual(self.lines("timeouts"), [])

    def workers_peak(self):
        return peak(self.events(), ("start", "fix"), ("end",))

    def reviews_peak(self):
        return peak(self.events(), ("review", "rereview"), ("review-end", "rereview-end"))

    def network(self, minutes):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("network_wait_minutes = 60", f"network_wait_minutes = {minutes}"))
        self.commit(f"network {minutes}")
        self.minute()

    def minute(self):
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "0.01"})
        patch.start()
        self.addCleanup(patch.stop)

    def leave_when(self, path, error=None, then=None):
        """path가 생기면 _wait_any 자리에서 루프를 떠난다(error) 또는 then을 한 번 부른다. 끝난 worker 확인은 진짜가 한다."""
        real = go._wait_any
        fired = []

        def wait_any(r, active, runner, *, once=False):
            if path.exists() and not fired:
                fired.append(True)
                if then:
                    then()
                else:
                    raise error
            return real(r, active, runner, once=once)
        return mock.patch.object(go, "_wait_any", wait_any)

    def assert_reviewer_gone(self, tid):
        self.assertFalse(alive(int((self.bin / f"leader_{tid}").read_text())), "리뷰어가 살아 있다")
        self.assertFalse(alive(int((self.bin / f"child_{tid}").read_text())), "리뷰어의 자식이 살아 있다")

    def kill_reviewer_leftovers(self, *tids):
        for tid in tids:
            for name in (f"leader_{tid}", f"child_{tid}"):
                path = self.bin / name
                if path.exists():
                    support.kill_quietly(int(path.read_text()))


class OtherWorkersDuringReviewTest(Base):
    def test_other_worker_is_merged_and_ready_ticket_runs_while_a_reviewer_is_held(self):
        self.setup_tickets(2, "11", "12", "13", deps={"13": '["12"]'})
        # 11의 리뷰어는 13이 integration에 병합될 때까지 붙잡힌다. 12의 worker·리뷰·병합과 13의 시작·병합이 그 사이에 끝나야 풀린다
        self.hook("start_12", 'await "$here/events.log" "^review 11$"\n')
        self.hook("review_11", textwrap.dedent("""\
            for i in $(seq 3000); do git log --format=%B gs/demo/integration | grep -q 'gs-ticket: demo/13' && break; sleep 0.02; done
            git log --format=%B gs/demo/integration | grep -q 'gs-ticket: demo/13' || echo "merge 13" >> "$here/timeouts"
        """))
        code, out, err = self.go(*self.only("11", "12", "13"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12", "13"])
        events = self.events()
        held = events.index("review 11"), events.index("review-end 11")
        for line in ("end 12", "review 12", "start 13", "end 13", "review 13"):
            self.assertIn(events.index(line), range(*held), events)
        log = self.integration("log", "--first-parent", "--format=%s", "gs/demo/integration")
        self.assertLess(log.index("Merge 11"), log.index("Merge 13"), log)  # 최근 것이 위다: 11이 마지막에 병합됐다

    def test_two_reviews_ending_together_merge_one_at_a_time_on_the_loop_thread(self):
        self.setup_tickets(2, "11", "12")
        self.hook("start_11", 'await "$here/events.log" "^start 12$"\n')
        self.hook("start_12", 'await "$here/events.log" "^start 11$"\n')
        self.hook("review_11", 'await "$here/events.log" "^review 12$"\n')
        self.hook("review_12", 'await "$here/events.log" "^review 11$"\n')
        real = go._merge_stage
        now, seen, threads = [], [], set()

        def merge(r, a):
            self.assertEqual(now, [], "병합이 겹쳤다")
            now.append(a.t.id)
            threads.add(threading.current_thread())
            for _ in range(3000):  # 두 리뷰가 모두 끝난 뒤에 첫 병합을 진행한다
                if sum(line.startswith("review-end") for line in self.events()) == 2:
                    break
                threading.Event().wait(0.01)
            seen.append(sum(line.startswith("review-end") for line in self.events()))
            try:
                return real(r, a)
            finally:
                now.pop()

        with mock.patch.object(go, "_merge_stage", merge):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12"])
        self.assertEqual(seen, [2, 2])
        self.assertEqual(threads, {threading.main_thread()})
        self.assertEqual(self.reviews_peak(), 2)


class SeatsTest(Base):
    def test_reviewing_ticket_leaves_its_worker_seat_and_review_seats_are_capped(self):
        self.setup_tickets(1, "11", "12", "13")
        # max_workers 1. 11의 리뷰어는 13의 worker가 끝날 때까지 붙잡힌다. 12는 리뷰 자리가 나기를 기다리고 13이 그 worker 자리를 쓴다
        self.hook("review_11", 'await "$here/events.log" "^end 13$"\n')
        self.hook("start_13", 'cp "$status" "$here/state_at_13.json"\n')
        code, out, err = self.go(*self.only("11", "12", "13"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12", "13"])
        self.assertEqual(self.workers_peak(), 1)
        self.assertEqual(self.reviews_peak(), 1)
        self.before("end 13", "review 12")
        self.assertEqual(self.phases("11"), ["worker", "review", "verify", "finish"])
        self.assertEqual(self.phases("12"), ["worker", "review_wait", "review", "verify", "finish"])
        line = json.loads((self.bin / "state_at_13.json").read_text())["progress"]["line"]
        self.assertIn("11 리뷰 중(codex)", line)
        self.assertIn("12 리뷰 대기 중", line)
        self.assertIn("13 worker 중(claude)", line)

    def test_max_workers_workers_and_max_workers_reviews_run_together(self):
        tids = ("11", "12", "13", "14", "15")
        self.setup_tickets(2, *tids)
        self.hook("start_11", 'await "$here/events.log" "^start 12$"\n')
        self.hook("start_12", 'await "$here/events.log" "^start 11$"\n')
        for me, other in (("11", "12"), ("12", "11")):
            self.hook(f"review_{me}", f'await "$here/events.log" "^review {other}$"\n' + await_ends(5))
        code, out, err = self.go(*self.only(*tids))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), list(tids))
        self.assertEqual(self.workers_peak(), 2)
        self.assertEqual(self.reviews_peak(), 2)
        for later in ("13", "14", "15"):
            self.before("end 15", f"review {later}")

    def test_fix_worker_uses_a_worker_seat_and_waits_for_one(self):
        self.setup_tickets(1, "11", "12", "13")
        self.answer_file("review_11", findings=[finding("FIX A: 값이 틀렸다")])
        self.answer_file("rereview_11", verdicts=[{"id": 1, "status": "resolved", "evidence": "확인"}], findings=[])
        # 11의 리뷰는 12가 자리를 쓰는 동안 끝난다. 12는 11이 수정 자리를 기다리는 것을 본 뒤에 끝난다
        self.hook("review_11", 'await "$here/events.log" "^start 12$"\n')
        self.hook("start_12", 'await "$status" "\\"fix_wait\\""\n')
        code, out, err = self.go(*self.only("11", "12", "13"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12", "13"])
        self.assertEqual(self.workers_peak(), 1)
        self.before("end 12", "fix 11")
        self.before("fix 11", "start 13")  # 빈 자리는 수정 worker가 새 티켓보다 먼저 얻는다
        # 재리뷰는 12의 리뷰가 자리를 쓰는 동안이면 기다린다. 그 대기는 끝나는 때에 달렸다
        self.assertEqual([p for p in self.phases("11") if p != "review_wait"],
                         ["worker", "review", "fix_wait", "fix", "rereview", "verify", "finish"])
        self.assertEqual(self.ts("11").review["findings"][0]["rereview"], review.RESOLVED)


class SeatRulesTest(unittest.TestCase):
    def reviews(self, *tickets):
        reviews = go.Reviews(2)
        self.addCleanup(reviews.executor.shutdown)
        reviews.tickets = {str(i): rv for i, rv in enumerate(tickets)}
        return reviews

    def test_only_tickets_in_the_review_flow_take_review_seats(self):
        waiting, running = go.Reviewing(None), go.Reviewing(None, flow=iter(()))
        finished = go.Reviewing(None, finished=True, todo=[{"id": 1}])
        self.assertEqual(self.reviews(waiting, running, finished).reviewing(), 1)

    def test_new_tickets_wait_only_for_a_fix_worker_that_has_something_to_fix(self):
        self.assertFalse(self.reviews(go.Reviewing(None), go.Reviewing(None, finished=True)).fix_waiting())
        self.assertTrue(self.reviews(go.Reviewing(None, finished=True, todo=[{"id": 1}])).fix_waiting())


class LoopThreadOnlyTest(Base):
    def test_state_is_saved_only_on_the_loop_thread_through_waits_and_two_reviewers(self):
        self.minute()
        self.tickets(**{tid: ("claude", "codex", "agy", "[]") for tid in ("11", "12")})
        support.GoTest.parallel(self, 2)
        for tid in ("11", "12"):
            self.hook(f"review_{tid}", textwrap.dedent(f"""\
                if [ "$GS_REVIEWER" = codex ] && [ ! -f "$here/once_{tid}" ]; then touch "$here/once_{tid}"; echo '{CODEX_DOWN}'; exit 1; fi
            """))
        real = state.save
        threads = set()

        def save(rundir, st):
            threads.add(threading.current_thread())
            return real(rundir, st)

        changes = []
        begin = review.CallWait._begin

        def recorded_begin(wait, *args):
            changes.append(threading.current_thread())
            return begin(wait, *args)

        with mock.patch.object(state, "save", save), mock.patch.object(review.CallWait, "_begin", recorded_begin):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(threads, {threading.main_thread()})
        self.assertEqual(set(changes), {threading.main_thread()})
        st = self.run_state()
        self.assertEqual(st.network["errors"], 2)
        self.assertEqual(st.network["wait"], {})
        self.assertEqual(st.agy_calls, 2)  # 재시도는 codex다
        for tid in ("11", "12"):
            self.assertEqual(st.tickets[tid].transient_errors, 1)
            self.assertEqual((st.tickets[tid].review["note"], st.tickets[tid].second_review["note"]), ("", ""))
        calls = st.metrics["review_calls"]
        self.assertEqual(sorted(x["result"] for x in calls if x["reviewer"] == "codex"), ["error", "error", "passed", "passed"])
        self.assertEqual({x["reviewer"] for x in st.metrics["reviewers"]}, {"codex", "agy"})
        self.assertEqual(len(st.metrics["reviewers"]), 4)


class ThreadErrorTest(Base):
    def test_unexpected_error_inside_the_call_is_a_review_failure_as_before(self):
        self.setup_tickets(1, "11")
        with mock.patch("gs.review.run", side_effect=RuntimeError("뜻밖")):
            code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures), ("merged", 0))
        self.assertIn("리뷰 실패(리뷰 없음, verify만으로 병합한다): 뜻밖의 오류 RuntimeError: 뜻밖", ts.review["note"])

    def test_error_escaping_the_review_thread_fails_the_ticket_and_retries(self):
        self.setup_tickets(1, "11")
        real = go._call_reviewers
        calls = []

        def call(jobs, tree):
            calls.append(threading.current_thread())
            if len(calls) == 1:
                raise RuntimeError("스레드가 죽었다")
            return real(jobs, tree)

        with mock.patch.object(go, "_call_reviewers", call):
            code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(threading.main_thread(), calls)  # 루프 밖에서 돈다
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures, ts.attempts), ("merged", 1, 2))
        self.assertIn("[11] 실패: worker 결과 처리 중 오류: ReviewThreadError: RuntimeError: 스레드가 죽었다", out)
        self.assertEqual(ts.network_resume, {})

    def test_git_error_from_the_review_thread_fails_the_ticket(self):
        self.setup_tickets(1, "11")
        real = review.run
        calls = []

        def run(**kw):
            calls.append(1)
            if len(calls) == 1:
                raise go.git.GitError("git이 죽었다")
            return real(**kw)

        with mock.patch("gs.review.run", run):
            code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures, ts.attempts), ("merged", 1, 2))
        self.assertIn("worker 결과 처리 중 오류: GitError: git이 죽었다", out)

    def test_error_escaping_the_rereview_thread_is_unchecked_and_merges(self):
        self.setup_tickets(1, "11")
        self.answer_file("review_11", findings=[finding("FIX A: 값이 틀렸다")])
        with mock.patch.object(go, "_call_rereviewers", side_effect=RuntimeError("스레드가 죽었다")):
            code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures), ("merged", 0))
        f = ts.review["findings"][0]
        self.assertEqual((f["rereview"], f["rereview_reason"]), (review.UNCHECKED, review.REASON_FAILED))
        self.assertIn("ReviewThreadError", f["rereview_evidence"])


class LeavingTheLoopTest(Base):
    """어떻게 떠나든 돌던 리뷰어의 프로세스 그룹을 끝내고, 다음 gs go가 worker를 다시 띄우지 않고 리뷰를 다시 한다."""

    def setUp(self):
        super().setUp()
        self.setup_tickets(2, "11")
        self.hook("review_11", HOLD)
        self.addCleanup(self.kill_reviewer_leftovers, "11", "12")

    def resume_does_only_the_review(self):
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.review), (state.RUNNING, {}))
        self.assertTrue(ts.network_resume["done"])
        (self.bin / "review_11.sh").unlink()
        code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("[11] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 리뷰부터 다시 한다", out)
        self.assertEqual(self.calls(), ["11"])  # worker를 다시 띄우지 않는다
        self.assertEqual(self.events().count("review 11"), 2)
        self.assertEqual(self.merged(), ["11"])
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures, ts.attempts, ts.worktree), ("merged", 0, 1, str(self.rundir / "wt/11")))
        self.assertEqual(ts.network_resume, {})

    def test_interrupt_ends_the_reviewer_group(self):
        with self.leave_when(self.bin / "reviewing_11", KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            self.go(*self.only("11"))
        self.assert_reviewer_gone("11")
        self.resume_does_only_the_review()

    def test_sigterm_is_a_human_stop_too(self):
        # 시험을 띄운 쪽이 무시하게 해 뒀어도 같은 조건으로 본다
        self.addCleanup(signal.signal, signal.SIGTERM, signal.signal(signal.SIGTERM, signal.SIG_DFL))
        kill = lambda: os.kill(os.getpid(), signal.SIGTERM)  # noqa: E731
        with self.leave_when(self.bin / "reviewing_11", then=kill), self.assertRaises(KeyboardInterrupt):
            self.go(*self.only("11"))
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)
        self.assert_reviewer_gone("11")
        self.resume_does_only_the_review()

    def test_unexpected_error_ends_the_reviewer_group(self):
        with self.leave_when(self.bin / "reviewing_11", RuntimeError("gs가 죽었다")), self.assertRaisesRegex(RuntimeError, "gs가 죽었다"):
            self.go(*self.only("11"))
        self.assert_reviewer_gone("11")
        self.resume_does_only_the_review()

    def test_network_abort_of_another_ticket_ends_the_reviewer_group(self):
        self.network(1)
        self.setup_tickets(2, "11", "12")
        self.hook("review_12", f'await "$here/reviewing_11" up\necho \'{CODEX_DOWN}\'; exit 1\n')
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, go.EXIT_NETWORK, out + err)
        self.assert_no_timeouts()
        self.assert_reviewer_gone("11")
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        for tid in ("11", "12"):
            ts = self.ts(tid)
            self.assertEqual((ts.status, ts.failures, ts.review, ts.reason), (state.PENDING, 0, {}, go.NETWORK_ABORT))
            self.assertTrue(ts.network_resume["done"])
        self.assertEqual(self.run_state().network["wait"], {})
        for hook in ("review_11", "review_12"):
            (self.bin / f"{hook}.sh").unlink()
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.calls()), ["11", "12"])
        self.assertEqual(self.merged(), ["11", "12"])

    def test_killed_gs_redoes_the_review_without_a_new_worker(self):
        log = Path(self.tmp.name) / "first.log"
        with log.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "go", "demo", "--only", "11"],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            deadline = time.monotonic() + 60
            while not (self.bin / "reviewing_11").exists():
                self.assertIsNone(proc.poll(), log.read_text())
                self.assertLess(time.monotonic(), deadline, log.read_text())
                time.sleep(0.02)
        finally:
            proc.kill()  # 정리할 틈이 없다. 표시는 리뷰를 시작하기 전에 파일에 있어야 한다
            proc.wait()
        self.kill_reviewer_leftovers("11")
        self.resume_does_only_the_review()

    def test_workers_stop_even_if_stopping_the_reviews_is_interrupted(self):
        """리뷰어를 기다리는 동안 또 Ctrl-C가 와도 도는 worker를 남기지 않는다."""
        self.setup_tickets(2, "11", "12")
        self.hook("start_12", 'echo $$ > "$here/worker_12"\nsleep 300\n')
        worker = self.bin / "worker_12"
        self.addCleanup(lambda: worker.exists() and support.kill_quietly(int(worker.read_text())))
        real_wait = go._wait_any

        def wait_any(r, active, runner, *, once=False):
            if (self.bin / "reviewing_11").exists() and worker.exists():
                raise KeyboardInterrupt("첫 번째")
            return real_wait(r, active, runner, once=once)

        def interrupted(r):
            r.reviews.cancel.set()  # 진짜도 맨 앞에서 세운다(StopReviewsTest). 그래서 리뷰어는 스스로 끝난다
            raise KeyboardInterrupt("두 번째")

        with mock.patch.object(go, "_wait_any", wait_any), mock.patch.object(go, "_stop_reviews", interrupted), \
                self.assertRaises(KeyboardInterrupt):
            self.go(*self.only("11", "12"))
        self.assertFalse(alive(int(worker.read_text())), "worker가 살아 있다")

    def test_snapshot_worktree_of_the_stopped_review_is_removed(self):
        (self.bin / "dirty_11").touch()  # 미커밋 변경이 남아 리뷰는 임시 worktree에서 돈다
        with self.leave_when(self.bin / "reviewing_11", RuntimeError("gs가 죽었다")), self.assertRaises(RuntimeError):
            self.go(*self.only("11"))
        self.assert_reviewer_gone("11")
        self.assertEqual(list(self.rundir.glob("gs-review-*")), [])
        self.assertNotIn("gs-review-", sh(self.repo, "git", "worktree", "list"))

    def test_old_state_without_the_mark_restarts_the_worker(self):
        with self.leave_when(self.bin / "reviewing_11", RuntimeError("gs가 죽었다")), self.assertRaises(RuntimeError):
            self.go(*self.only("11"))
        path = state.path(self.rundir)
        raw = json.loads(path.read_text())
        ticket_state = raw["tickets"]["11"]
        del ticket_state["network_resume"]  # 옛 state: 리뷰 중에 죽었어도 표시가 없다
        self.assertEqual(ticket_state["phases"][-1]["phase"], "review")
        path.write_text(json.dumps(raw, ensure_ascii=False))
        (self.bin / "review_11.sh").unlink()
        code, out, err = self.go(*self.only("11"))
        self.assertEqual(code, 0, out + err)
        self.assertIn("[11] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 새로 시작한다", out)
        self.assertEqual(self.calls(), ["11", "11"])
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures, ts.attempts), ("merged", 0, 1))

    def test_ticket_waiting_for_a_review_seat_resumes_too(self):
        self.setup_tickets(1, "11", "12")
        self.hook("start_12", 'echo up > "$here/started_12"\n')
        # 12의 worker가 끝나 리뷰 자리를 기다리는 것을 본 뒤에 떠난다
        marker = self.bin / "seen_wait"
        real = go._wait_any

        def wait_any(r, active, runner, *, once=False):
            if r.st.ticket("12").phases and r.st.ticket("12").phases[-1]["phase"] == "review_wait":
                marker.touch()
                raise RuntimeError("gs가 죽었다")
            return real(r, active, runner, once=once)

        with mock.patch.object(go, "_wait_any", wait_any), self.assertRaises(RuntimeError):
            self.go(*self.only("11", "12"))
        self.assertTrue(marker.exists())
        self.assert_reviewer_gone("11")
        self.assertTrue(self.ts("12").network_resume["done"])
        (self.bin / "review_11.sh").unlink()
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.calls()), ["11", "12"])
        self.assertEqual(self.merged(), ["11", "12"])
        self.assertEqual(self.ts("12").attempts, 1)


class StopReviewsTest(unittest.TestCase):
    def test_cancel_is_up_before_anything_else_can_be_interrupted(self):
        reviews = go.Reviews(1)
        self.addCleanup(reviews.executor.shutdown)
        reviews.tickets["11"] = go.Reviewing(None, future=Future())
        with mock.patch.object(go, "say", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            go._stop_reviews(SimpleNamespace(reviews=reviews))
        self.assertTrue(reviews.cancel.is_set())


class StopSignalsTest(unittest.TestCase):
    def test_ignored_signal_stays_ignored(self):
        """nohup으로 띄우면 SIGHUP은 무시된다. 터미널이 닫혀도 멈추면 안 된다."""
        before = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        self.addCleanup(signal.signal, signal.SIGHUP, before)
        with go._stop_signals():
            self.assertEqual(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)
            os.kill(os.getpid(), signal.SIGHUP)
        self.assertEqual(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)

    def test_default_signal_becomes_an_interrupt_only_inside(self):
        before = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        self.addCleanup(signal.signal, signal.SIGTERM, before)
        with self.assertRaises(KeyboardInterrupt), go._stop_signals():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)  # 처리기가 올린다. 여기까지 오면 안 된다
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)


class ProgressTest(Base):
    def test_status_and_progress_show_the_reviewing_ticket(self):
        self.setup_tickets(2, "11", "12")
        self.hook("review_11", 'echo up > "$here/reviewing_11"\nawait "$here/release" up\n')
        self.hook("start_12", 'await "$here/reviewing_11" up\nawait "$here/release" up\n')
        seen = []

        def look():
            seen.append(support.GoTest.status(self, "demo")[1])
            seen.append(state.load(self.rundir, "demo"))
            (self.bin / "release").write_text("up\n")

        with self.leave_when(self.bin / "reviewing_11", then=look):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        table, st = seen
        self.assertRegex(table, r"11\s+실행 중\s+1")
        self.assertRegex(table, r"12\s+실행 중\s+1")
        self.assertIn("11 리뷰 중(codex)", table)
        self.assertIn("12 worker 중(claude)", table)
        running = {x["id"]: x["phase"] for x in st.progress["running"]}
        self.assertEqual(running, {"11": "review", "12": "worker"})


class AgyLimitTest(Base):
    def test_concurrent_reviews_do_not_launch_past_the_limit(self):
        self.limit(2)
        tids = ("11", "12", "13")
        self.setup_tickets(3, *tids, reviewer="agy")
        for tid in tids:
            # 먼저 시작한 두 리뷰는 함께 돈다: 둘 다 시작해야 하나가 끝난다
            self.hook(f"review_{tid}", textwrap.dedent("""\
                for i in $(seq 3000); do [ "$(grep -c '^review ' "$here/events.log")" -ge 2 ] && break; sleep 0.02; done
            """))
        code, out, err = self.go(*self.only(*tids))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.reviews_peak(), 2)
        self.assertEqual(self.lines("review.calls"), ["agy", "agy"])
        st = self.run_state()
        self.assertEqual(st.agy_calls, 2)
        notes = [st.tickets[tid].review["note"] for tid in tids]
        self.assertEqual(sum(note.startswith(review.LIMIT) for note in notes), 1, notes)
        self.assertEqual(self.merged(), list(tids))

    def test_retry_of_a_running_review_counts_before_the_next_review_decides(self):
        self.minute()
        self.limit(2)
        self.setup_tickets(2, "11", "12", reviewer="agy")
        self.hook("review_11", textwrap.dedent(f"""\
            if [ ! -f "$here/once" ]; then touch "$here/once"; echo '{AGY_DOWN}' >&2; exit 1; fi
            echo up > "$here/retried"
        """))
        self.hook("start_12", 'await "$here/retried" up\n')  # 12는 11의 재시도가 뜬 뒤에 끝난다
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.lines("review.calls"), ["agy", "agy"])
        st = self.run_state()
        self.assertEqual(st.agy_calls, 2)
        self.assertTrue(st.tickets["12"].review["note"].startswith(review.LIMIT), st.tickets["12"].review)

    def test_retry_is_counted_before_it_goes_out(self):
        """루프가 _drain을 지난 뒤에 재시도 대기가 끝나도 세기 전에는 나가지 않는다. 상한 판단마다 나간 호출이 모두 세여 있다."""
        self.minute()
        self.limit(2)
        self.setup_tickets(2, "11", "12", reviewer="agy")
        self.hook("review_11", textwrap.dedent(f"""\
            if [ ! -f "$here/once" ]; then echo x > "$here/once"; echo '{AGY_DOWN}' >&2; exit 1; fi
        """))
        self.hook("start_12", 'await "$here/once" x\n')
        real_pause, real_plan = review.CallWait._pause, go._plan_review
        deciding, paused, decided = threading.Event(), threading.Event(), []

        def pause(wait, seconds):
            self.assertTrue(deciding.wait(60))  # 12의 판단 직전까지 11의 재시도를 붙잡는다
            real_pause(wait, seconds)
            paused.set()

        def plan(r, a):
            if a.t.id == "12":  # 루프는 _drain을 지났다. 이제 11의 대기가 끝난다: 지적의 순서다
                deciding.set()
                self.assertTrue(paused.wait(60))
                threading.Event().wait(0.3)  # 세지 않은 재시도가 나갈 틈. 고친 코드의 통과는 이 시간에 기대지 않는다
            decided.append((len(self.lines("review.calls")), r.st.agy_calls))
            return real_plan(r, a)

        with mock.patch.object(review.CallWait, "_pause", pause), mock.patch.object(go, "_plan_review", plan):
            code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(decided, [(0, 0), (1, 1)])  # (나간 호출, 센 호출)
        self.assertEqual(self.lines("review.calls"), ["agy"] * 3)
        self.assertEqual(self.run_state().agy_calls, 3)  # 재시도는 상한을 보지 않는다. 나간 호출은 모두 셌다


class HeadMovedWhileWaitingTest(Base):
    """리뷰가 끝나 수정 worker 자리를 기다리는 사이 head가 움직였다(살아 남은 worker의 자손). 아무도 안 본 커밋 위에서 수정 worker를 띄우지 않는다."""

    def test_commit_while_waiting_for_a_fix_seat_is_reviewed_before_the_fix(self):
        self.setup_tickets(1, "11", "12")
        self.answer_file("review_11", findings=[finding("FIX A: 값이 틀렸다")])
        self.answer_file("rereview_11", verdicts=[{"id": 1, "status": "resolved", "evidence": "확인"}], findings=[])
        self.hook("review_11", 'await "$here/events.log" "^start 12$"\ngit rev-parse HEAD >> "$here/reviewed_11"\n')
        self.hook("start_12", textwrap.dedent("""\
            await "$status" '"fix_wait"'
            git -C "$GS_WORKTREE/../11" commit -q --allow-empty -m late
            git -C "$GS_WORKTREE/../11" rev-parse HEAD > "$here/late_11"
        """))
        code, out, err = self.go(*self.only("11", "12"))
        self.assertEqual(code, 0, out + err)
        self.assert_no_timeouts()
        self.assertEqual(self.merged(), ["11", "12"])
        first, second = self.lines("reviewed_11")
        [late] = self.lines("late_11")
        self.assertEqual(second, late)
        self.assertNotEqual(first, late)
        self.assertIn("병합 전 대조", out)
        events = self.events()
        self.assertLess(len(events) - 1 - events[::-1].index("review-end 11"), events.index("fix 11"), events)
        rec = self.ts("11").review
        self.assertEqual(rec["rereviews"][0]["base"], late)  # 수정의 재리뷰는 다시 본 head부터 본다
        self.assertEqual([p for p in self.phases("11") if p != "review_wait"],
                         ["worker", "review", "fix_wait", "review", "fix", "rereview", "verify", "finish"])


class SecondRereviewWaitTest(test_recheck_resolved.Base):
    """2차 재리뷰가 끝나 끊김의 끝을 기다리는 사이 커밋이 생겼다. 앞 head의 resolved를 최종 커밋의 확인으로 세지 않는다."""

    def commit_while_waiting(self, command):
        real, fired = go._leave_review, []

        def leave(r, rv, active, runner):
            if rv.a.fix != 2 or fired:
                return real(r, rv, active, runner)
            fired.append(True)
            with mock.patch.object(go.Outage, "active", True):  # 이 티켓만 끊김의 끝을 기다린 것으로 한다
                self.assertFalse(real(r, rv, active, runner))
            sh(rv.a.wt, "bash", "-c", f"{command}; git add -A; git commit -q --allow-empty -m late")
            return False

        with mock.patch.object(go, "_leave_review", leave):
            return self.run_ok()

    def test_commit_while_waiting_is_rechecked_at_the_new_head(self):
        self.findings("codex", test_recheck_resolved.A, test_recheck_resolved.B)
        self.a_fixed_first()
        out = self.commit_while_waiting("rm fixed_A")
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])
        a, b = self.ts().review["findings"]
        self.assertEqual(self.result(a), (1, review.UNRESOLVED, 2))
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertIn(test_recheck_resolved.UNFIXED, self.report_line("FIX A"))
        self.assertEqual(self.phases().count("network"), 1)
        self.assertNotIn("경고: 병합 전 대조", out)

    def test_commit_after_the_one_more_look_is_only_recorded(self):
        self.findings("codex", test_recheck_resolved.A, test_recheck_resolved.B)
        self.a_fixed_first()
        (self.bin / "late_codex_2.sh").write_text("touch late1\n")  # 재리뷰 중의 커밋이 "한 번 더"를 쓴다
        out = self.commit_while_waiting("rm fixed_A")
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])  # 더 부르지 않는다
        self.assertNotIn("fixed_A", self.files())
        self.assertIn("경고: 병합 전 대조", out)
        rec = self.ts().review
        for f in rec["findings"]:
            self.assertEqual((f["rereview"], f["rereview_reason"], f["rereview_round"]),
                             (review.UNCHECKED, review.REASON_FAILED, 2))
        self.assertIn("리뷰하지 못했다", rec["fix"])


class OutageDuringReviewTest(support.GoTest):
    """리뷰 중에 worker 끊김이 시작됐다. 도는 리뷰는 그대로 끝나고, 그 뒤의 병합은 끊김이 끝난 뒤에 간다. 실제 어댑터로 일시 오류를 판별한다."""
    N = test_network_wait.NetworkTest
    fake, tickets = N.fake, N.tickets

    def setUp(self):
        super().setUp()
        for patch in (mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.N.MINUTE}),
                      mock.patch.object(transient, "RECOVERY_MINUTES", 10 ** 6)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")

    def test_merge_after_a_review_waits_for_the_outage_to_end(self):
        # 11의 리뷰어는 12의 끊김을 본 뒤에 끝난다. 다시 띄운 12는 11이 끊김의 끝을 기다리는 것을 본 뒤에 끝난다(자기 것 + 11의 network 단계)
        self.fake("claude", AWAIT + textwrap.dedent(f"""\
            status="$GS_WORKTREE/../../state.json"
            case "$GS_TICKET" in
              12) if [ "$n" = 1 ]; then await "$here/reviewing" up; echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
                  for i in $(seq 3000); do [ "$(grep -c '"phase": "network"' "$status")" -ge 2 ] && break; sleep 0.02; done
                  [ "$(grep -c '"phase": "network"' "$status")" -ge 2 ] || echo network >> "$here/timeouts" ;;
            esac
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        """))
        (self.bin / "reviewer.sh").write_text('here="$(dirname "$0")"\n' + AWAIT + textwrap.dedent("""\
            cat > /dev/null
            if [ "$(basename "$PWD")" = 11 ]; then
              echo up > "$here/reviewing"
              await "$PWD/../../state.json" '네트워크 대기'
            fi
            echo '{"findings": []}'
        """))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("timeouts"), [])
        self.assertEqual(self.merged(), ["11", "12"])
        phases = [p["phase"] for p in state.load(self.rundir, "demo").tickets["11"].phases]
        self.assertEqual(phases, ["worker", "review", "network", "verify", "finish"])
        self.assertIn("■ 네트워크 회복", out)

    def test_commit_during_the_outage_is_reviewed_before_the_merge(self):
        # 앞 시험과 같은 순서에서, 다시 띄운 12가 끝나기 전에 11의 브랜치에 커밋이 생긴다
        self.fake("claude", AWAIT + textwrap.dedent(f"""\
            status="$GS_WORKTREE/../../state.json"
            case "$GS_TICKET" in
              12) if [ "$n" = 1 ]; then await "$here/reviewing" up; echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
                  for i in $(seq 3000); do [ "$(grep -c '"phase": "network"' "$status")" -ge 2 ] && break; sleep 0.02; done
                  [ "$(grep -c '"phase": "network"' "$status")" -ge 2 ] || echo network >> "$here/timeouts"
                  git -C "$GS_WORKTREE/../11" commit -q --allow-empty -m late ;;
            esac
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        """))
        (self.bin / "reviewer.sh").write_text('here="$(dirname "$0")"\n' + AWAIT + textwrap.dedent("""\
            cat > /dev/null
            if [ "$(basename "$PWD")" = 11 ]; then
              git rev-parse HEAD >> "$here/reviewed_11"
              if [ ! -f "$here/reviewing" ]; then
                echo up > "$here/reviewing"
                await "$PWD/../../state.json" '네트워크 대기'
              fi
            fi
            echo '{"findings": []}'
        """))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("timeouts"), [])
        self.assertEqual(self.merged(), ["11", "12"])
        ts = state.load(self.rundir, "demo").tickets["11"]
        self.assertEqual([p["phase"] for p in ts.phases], ["worker", "review", "network", "review", "verify", "finish"])
        first, second = self.lines("reviewed_11")
        self.assertEqual(sh(self.repo, "git", "log", "-1", "--format=%s", second), "late")
        self.assertNotEqual(sh(self.repo, "git", "log", "-1", "--format=%s", first), "late")
        self.assertEqual(ts.review["reviewed_head"], second)
        self.assertIn("병합 전 대조", out)


class CallWaitOffLoopTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "60"})
        patch.start()
        self.addCleanup(patch.stop)
        self.st = state.State(feature="demo")
        self.saves = []
        self.lines = []

    def waiter(self, tid, inbox, board=None, cancel=None):
        return review.CallWait(self.st, lambda: self.saves.append(dict(self.st.network.get("wait") or {})), tid,
                               self.lines.append, post=inbox.append, cancel=cancel, board=board)

    def in_thread(self, wait, *args):
        """호출 스레드처럼 wait를 부른다. (돌아왔는가, Cancelled 목록)."""
        done, stopped = threading.Event(), []

        def call():
            try:
                wait(*args)
            except review.Cancelled as e:
                stopped.append(e)
            finally:
                done.set()
        threading.Thread(target=call, daemon=True).start()
        return done, stopped

    def until_posted(self, inbox, count):
        for _ in range(6000):
            if len(inbox) >= count:
                return
            threading.Event().wait(0.01)
        self.fail(f"넘긴 변경이 {len(inbox)}개다. {count}개를 기다렸다")

    def test_call_leaves_state_alone_and_the_loop_applies_its_changes(self):
        inbox = []
        done, _ = self.in_thread(self.waiter("01", inbox), "끊김", 1, 0.01, "agy")
        self.until_posted(inbox, 3)  # 대기 시작, 저장, 대기 끝
        self.assertEqual((self.st.network, self.st.tickets, self.st.agy_calls, self.saves), ({}, {}, 0, []))
        self.assertEqual(self.lines, [])
        for change in inbox:
            change()
        self.assertTrue(done.wait(60))
        self.assertEqual(self.st.network["errors"], 1)
        self.assertEqual(self.st.network["wait"], {})
        self.assertEqual((self.st.agy_calls, self.st.tickets["01"].transient_errors), (1, 1))
        self.assertGreaterEqual(self.st.network["waited_seconds"], 0)
        self.assertEqual(self.saves[0]["count"], 1)
        self.assertIn("[01] 끊김. 네트워크 대기(1회", self.lines[0])

    def test_two_tickets_share_the_shown_wait_and_the_outage_label_comes_back(self):
        outage = {"count": 3, "due_at": "2099-01-01T00:00:00+09:00"}
        self.st.network["wait"] = dict(outage)
        board = review.WaitBoard()
        first, second = [], []
        both_called = threading.Barrier(2)  # 둘 다 살아 있어야 스레드 식별자가 다르다

        def call(wait, count):
            wait("끊김", count, 0)
            both_called.wait()

        threads = [threading.Thread(target=call, args=(self.waiter(tid, inbox, board), count))
                   for tid, inbox, count in (("01", first, 1), ("02", second, 2))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        (begin_a, *_, end_a), (begin_b, *_, end_b) = first, second
        begin_a()
        self.assertEqual(self.st.network["wait"]["count"], 1)
        begin_b()
        end_a()  # 01은 끝났고 02는 기다린다: 지운 값이나 지난 값이 보이면 안 된다
        self.assertEqual(self.st.network["wait"]["count"], 2)
        self.assertNotIn("waited_seconds", self.st.network)  # 벽시계는 모두 끝나야 한 번 센다
        end_b()
        self.assertEqual(self.st.network["wait"], outage)
        self.assertIn("waited_seconds", self.st.network)
        self.assertEqual({tid: ts.transient_errors for tid, ts in self.st.tickets.items()}, {"01": 1, "02": 1})

    def test_outage_published_during_a_call_wait_shows_after_it(self):
        n = go.Outage()
        inbox = []
        self.waiter("01", inbox, n.calls)("끊김", 1, 0)
        inbox[0]()
        n.backoff.next(60)
        n.probes.add("11")
        go._net_publish(SimpleNamespace(net=n, st=self.st, save=lambda: None))
        self.assertEqual(self.st.network["wait"]["count"], 1)  # 호출 대기가 먼저 보인다
        self.assertEqual(n.calls.before, {"count": 1, "due_at": ""})
        for change in inbox[1:]:
            change()
        self.assertEqual(self.st.network["wait"], {"count": 1, "due_at": ""})

    def test_cancel_ends_the_wait_without_counting_a_retry(self):
        cancel = threading.Event()
        cancel.set()
        inbox = []
        with self.assertRaises(review.Cancelled):
            self.waiter("01", inbox, cancel=cancel)("끊김", 1, 1000, "agy")
        for change in inbox:
            change()
        self.assertEqual(self.st.agy_calls, 0)
        self.assertEqual(self.st.network["wait"], {})

    def test_agy_retry_goes_out_only_after_the_loop_counted_it(self):
        inbox = []
        done, _ = self.in_thread(self.waiter("01", inbox), "끊김", 1, 0, "agy")
        self.until_posted(inbox, 2)
        self.assertFalse(done.wait(0.2))  # 세기 전이다. 고친 코드의 통과는 이 시간에 기대지 않는다
        self.assertEqual(self.st.agy_calls, 0)
        for change in inbox:
            change()
        self.assertTrue(done.wait(60))
        self.assertEqual(self.st.agy_calls, 1)

    def test_retry_of_other_families_does_not_wait_for_the_loop(self):
        inbox = []
        done, _ = self.in_thread(self.waiter("01", inbox), "끊김", 1, 0, "codex")
        self.assertTrue(done.wait(60))
        self.assertEqual(self.st.agy_calls, 0)

    def test_cancel_ends_the_wait_for_the_count(self):
        cancel = threading.Event()
        inbox = []
        done, stopped = self.in_thread(self.waiter("01", inbox, cancel=cancel), "끊김", 1, 0, "agy")
        self.until_posted(inbox, 2)
        cancel.set()
        self.assertTrue(done.wait(60))
        self.assertIsInstance(stopped[0], review.Cancelled)
        for change in inbox:
            change()
        self.assertEqual(self.st.agy_calls, 0)  # 나가지 않은 재시도는 세지 않는다

    def test_failed_save_still_lets_the_retry_go(self):
        def broken():
            raise OSError("디스크")

        inbox = []
        wait = review.CallWait(self.st, broken, "01", self.lines.append, post=inbox.append)
        done, _ = self.in_thread(wait, "끊김", 1, 0, "agy")
        self.until_posted(inbox, 2)
        for change in inbox:
            with self.assertRaises(OSError):
                change()
        self.assertTrue(done.wait(60))
        self.assertEqual(self.st.agy_calls, 1)


class CancelCallTest(test_review_network.Base):
    def call(self, path, cancel):
        return review._call([str(path)], prompt="p", cwd=self.dir, env=dict(os.environ), log=self.rdir / "cli.log",
                            timeout=300, cancel=cancel)

    def test_cancel_ends_a_running_call_and_its_group(self):
        path = self.script("cli", 'cat > /dev/null; sleep 300 & echo $! > "$here/child"; echo $$ > "$here/leader"; wait')
        cancel = threading.Event()
        errors = []

        def run():
            try:
                self.call(path, cancel)
            except review.Cancelled as e:
                errors.append(e)

        thread = threading.Thread(target=run)
        thread.start()
        for _ in range(3000):
            if (self.bin / "child").exists() and (self.bin / "child").read_text().strip():
                break
            threading.Event().wait(0.01)
        cancel.set()
        thread.join(30)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertFalse(alive(int((self.bin / "leader").read_text())))
        self.assertFalse(alive(int((self.bin / "child").read_text())))

    def test_cancelled_call_does_not_start(self):
        path = self.script("cli", 'echo ran')
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(review.Cancelled):
            self.call(path, cancel)
        self.assertEqual(self.calls("cli"), 0)

    def test_answer_arrives_through_the_cancel_checks(self):
        path = self.script("cli", 'cat; sleep 0.5; echo " done"')
        self.assertEqual(self.call(path, threading.Event()).split(), ["p", "done"])

    def test_timeout_still_applies_with_cancel(self):
        path = self.script("cli", 'sleep 300')
        with self.assertRaises(review.ReviewTimeout):
            review._call([str(path)], prompt="p", cwd=self.dir, env=dict(os.environ), log=self.rdir / "cli.log",
                         timeout=0.5, cancel=threading.Event())


if __name__ == "__main__":
    unittest.main()
