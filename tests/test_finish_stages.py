"""goldstack-v9 05: 끝난 worker 처리의 단계 경계와 순서를 고정한다. 결과 확인 → 리뷰·수정 worker 판단 → catch-up·병합·검증.

순서 시험은 단계 함수를 감싸 부른 순서를 적고 실제 `gs go`를 돌린다. 단계 함수는 들어갈 때 이름, 돌아올 때 `/이름`을 적는다.
`/이름`이 없으면 그 단계는 예외로 끝났다. 리뷰 단계(v9 06)는 제너레이터라 루프가 끝까지 돌린 뒤에 `/이름`을 적는다.
리뷰로 가는 티켓은 리뷰부터 잇는 표시(_mark_resume)를 먼저 남긴다.
"""
import inspect
import json
import os
import textwrap
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import support
import test_network_wait
import test_review_target
from support import sh, ticket
from test_second_review import finding

from gs import finish, git, go, review, state, transient, worker

STAGES = ("_check_worker", "_review_stage", "_merge_stage")
STEPS = ("_net_hold", "_net_park", "_end_fix", "_review", "_rereview", "_call_reviewers", "_call_rereviewers",
         "_moved_head", "_mark_resume", "_next_fix", "_start_fix", "_catch_up", "_verify", "_cleanup_merged", "_fail",
         "_start_repair", "_end_repair", "_repair_review", "_call_repair_reviewers")

CHECK = ["_check_worker", "_net_park", "/_check_worker"]
FIX_CHECK = ["_check_worker", "_net_park", "_end_fix", "/_check_worker"]
MARK = ["_mark_resume"]  # 리뷰에 들어가기 전: 어떻게 끝나든 다음 gs go가 리뷰부터 다시 한다
REVIEW = MARK + ["_review_stage", "_review", "_call_reviewers", "_moved_head", "/_review_stage"]
REREVIEW = MARK + ["_review_stage", "_rereview", "_call_rereviewers", "_moved_head", "/_review_stage"]
TO_FIX = ["_next_fix", "_start_fix"]
NO_FIX = ["_next_fix"]
MERGE = ["_merge_stage", "_catch_up", "_verify", "_cleanup_merged", "/_merge_stage"]
VERIFY_FAILED = ["_merge_stage", "_catch_up", "_verify", "_mark_resume", "/_merge_stage"]  # 수리 자리를 기다리는 표시를 남긴다
TO_REPAIR = ["_start_repair", "_mark_resume"]  # 수정 worker와 달리 띄운 worker에도 표시를 남긴다: gs가 죽어도 잇는다
PARKED = ["_check_worker", "_net_park", "_mark_resume", "/_check_worker"]  # 끊김 중에 끝났다. 회복하면 처음부터 다시 온다
HELD = ["_check_worker", "_net_hold", "_mark_resume", "/_check_worker", "_mark_resume"]  # 마지막 표시는 다시 띄운 worker(_resume)다
PROBE_ENDED = PARKED  # 다시 띄운 worker가 끝난 것이 회복의 근거다. 그때는 아직 끊김 중이라 자기도 한 번 미뤄진다


def ticket_of(args):
    if not isinstance(args[0], go.Run):  # _call_reviewers(jobs, tree)
        return args[0][0]["on_wait"].tid
    x = args[1]
    return x if isinstance(x, str) else getattr(x, "t", x).id


def watched(events, name, real):
    def wrapper(*args, **kwargs):
        tid = ticket_of(args)
        events.append((tid, name))
        result = real(*args, **kwargs)
        if name in STAGES:
            if inspect.isgenerator(result):
                return finishing(result, events, tid, name)
            events.append((tid, "/" + name))
        return result
    return wrapper


def finishing(flow, events, tid, name):
    value = yield from flow
    events.append((tid, "/" + name))
    return value


@contextmanager
def recorded(**fakes):
    """단계 함수를 부른 순서를 (티켓, 이름)으로 모은다. fakes의 함수는 진짜 대신 부른다."""
    events = []
    patches = [mock.patch.object(go, name, watched(events, name, fakes.get(name, getattr(go, name))))
               for name in (*STAGES, *STEPS)]
    for p in patches:
        p.start()
    try:
        yield events
    finally:
        for p in patches:
            p.stop()


def order(events, tid="01"):
    return [name for t, name in events if t == tid]


class StageOrderTest(test_review_target.Base):
    def run_go(self, **fakes):
        with recorded(**fakes) as events:
            code, out, err = self.go("--only", "01")
        return order(events), code, out + err

    def test_clean_worker(self):
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + NO_FIX + MERGE)
        self.assertEqual(self.merged(), ["01"])

    def test_fix_worker_comes_back_through_the_stages(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + TO_FIX + FIX_CHECK + REREVIEW + NO_FIX + MERGE)
        self.assertEqual(self.phases(), ["worker", "review", "fix", "rereview", "verify", "finish"])

    def test_second_fix_worker(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "unresolved", "그대로다")])
        self.answer("codex", 2, [(1, "resolved", "확인")])
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + TO_FIX + FIX_CHECK + REREVIEW + TO_FIX + FIX_CHECK + REREVIEW + NO_FIX + MERGE)

    def test_failed_fix_worker_skips_review_stage(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        (self.bin / "fixfail_1").touch()
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + TO_FIX + ["_check_worker", "_end_fix", "/_check_worker"] + MERGE)
        self.assertEqual(self.merged(), ["01"])

    def test_fix_worker_that_cannot_start_goes_to_merge(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        steps, code, log = self.run_go(_start_fix=lambda *args: None)
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + TO_FIX + MERGE)

    def test_head_moved_during_review_is_seen_inside_the_stage(self):
        self.late("review", 1)
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + MARK + ["_review_stage", "_review", "_call_reviewers", "_moved_head",
                                                "_review", "_call_reviewers", "_moved_head", "/_review_stage"] + NO_FIX + MERGE)
        self.assertEqual(self.subject(self.ts().review["reviewed_head"]), "late review 1")

    def test_head_moved_before_fix_worker_is_seen_first(self):
        self.late("review", 1)
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps[:steps.index("_start_fix")].count("_moved_head"), 2)

    def test_head_moved_during_rereview_is_seen_inside_the_stage(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.late("rereview", 1)
        self.answer("codex", 1, [(1, "resolved", "앞 판정")])
        self.answer("codex", 2, [(1, "resolved", "늦은 커밋까지 확인")])
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        self.assertEqual(steps, CHECK + REVIEW + TO_FIX + FIX_CHECK + MARK
                         + ["_review_stage", "_rereview", "_call_rereviewers", "_moved_head",
                            "_rereview", "_call_rereviewers", "_moved_head", "/_review_stage"] + NO_FIX + MERGE)

    def test_failed_worker_stops_at_the_check(self):
        (self.bin / "worker.sh").write_text("exit 1\n")
        steps, code, log = self.run_go()
        self.assertEqual(code, 1, log)
        self.assertEqual(steps, ["_check_worker", "_fail", "/_check_worker"] * 2)  # 첫 실패는 한 번 재시도한다

    def test_refused_review_fails_the_ticket_without_fix_or_merge(self):
        with mock.patch.object(review, "require_other_family", side_effect=review.Refused("리뷰 거부: 시험")):
            steps, code, log = self.run_go()
        self.assertEqual(code, 1, log)
        self.assertEqual(steps, (CHECK + MARK + ["_review_stage", "_review", "_fail"]) * 2)
        self.assertEqual(self.ts().reason, "리뷰 거부: 시험")

    def test_merge_stage_catches_up_then_merges_then_verifies(self):
        self.tickets(**{tid: ("claude", "codex", None, "[]") for tid in ("11", "12")})
        support.GoTest.parallel(self, 2)
        (self.bin / "barrier").write_text("2")  # 둘이 같은 integration 끝에서 시작한다. 나중 티켓은 catch-up을 한다
        real = go._verify
        seen = {}

        def verify(r, t):
            branch = go.ticket_branch(r.name, t.id)
            caught_up = git.run(r.repo, "merge-base", "--is-ancestor", r.ihead, branch, check=False).returncode == 0
            seen[t.id] = (caught_up, git.out(r.iwt, "rev-parse", "MERGE_HEAD") == git.sha(r.repo, branch))
            return real(r, t)

        with recorded(_verify=verify) as events:
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(seen, {"11": (True, True), "12": (True, True)})
        self.assertIn("gs: 최신 integration을", self.integration("log", "--format=%s", "gs/demo/integration"))
        for tid in ("11", "12"):
            self.assertEqual(order(events, tid), CHECK + REVIEW + NO_FIX + MERGE)
            self.assertEqual(self.phases(tid)[-2:], ["verify", "finish"])

    def test_catch_up_conflict_fails_before_merge_and_verify(self):
        self.tickets(**{tid: ("claude", "codex", None, "[]") for tid in ("11", "12")})
        support.GoTest.parallel(self, 2)
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "start $GS_TICKET" >> "$here/events.log"
            for i in $(seq 200); do [ "$(grep -c '^start' "$here/events.log")" -ge 2 ] && break; sleep 0.05; done
            echo "$GS_TICKET" > shared.txt; git add -A; git commit -qm "t$GS_TICKET"
        '''))  # 둘이 같은 integration 끝에서 시작해 같은 파일을 다르게 고친다
        with recorded() as events:
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        win = CHECK + REVIEW + NO_FIX + MERGE
        lose = CHECK + REVIEW + NO_FIX + ["_merge_stage", "_catch_up", "_fail", "/_merge_stage"]
        self.assertEqual(sorted((order(events, "11"), order(events, "12")), key=len), [win, lose + win])  # 진 쪽은 재시도한다
        self.assertEqual(self.merged(), ["11", "12"])

    def test_verify_failure_is_repaired_and_a_repair_without_a_commit_fails_the_ticket(self):
        (self.repo / ".goldstack/work/demo/spec.md").write_text("---\nfeature: demo\nverify: 'false'\nmax_workers: 1\n---\n")
        self.commit("verify false")
        steps, code, log = self.run_go()
        self.assertEqual(code, 1, log)
        # 수리 worker가 고칠 것이 없다. 같은 head를 다시 병합·검증하지 않고 바로 실패한다(goldstack-v25 03)
        no_commit = ["_check_worker", "_end_repair", "_fail", "/_check_worker"]
        self.assertEqual(steps, (CHECK + REVIEW + NO_FIX + VERIFY_FAILED + TO_REPAIR + no_commit) * 2)

    def test_repair_commit_comes_back_through_the_stages(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            if grep -q '^## 검증 실패(고칠 것)' "$GS_BRIEF"; then git rm -q BROKEN; git commit -qm repaired; exit 0; fi
            touch BROKEN; echo x > file_01; git add -A; git commit -qm t01
        '''))
        steps, code, log = self.run_go()
        self.assertEqual(code, 0, log)
        check = ["_check_worker", "_net_park", "_end_repair", "/_check_worker"]
        rereview = MARK + ["_review_stage", "_repair_review", "_call_repair_reviewers", "_moved_head", "/_review_stage"]
        # 다시 검증에 들어가기 전에도 표시를 남긴다: 거기서 죽어도 수리를 잃지 않는다
        self.assertEqual(steps, CHECK + REVIEW + NO_FIX + VERIFY_FAILED + TO_REPAIR + check + rereview + NO_FIX + MARK + MERGE)
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "rereview", "verify", "finish"])

    def test_calls_receive_values_and_a_snapshot_of_findings(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        self.answer("codex", 1, [(1, "resolved", "확인")])
        seen = {}
        reviewers, rereviewers = go._call_reviewers, go._call_rereviewers

        def call(name, real):
            def wrapper(jobs, tree):
                seen[name] = jobs
                return real(jobs, tree)
            return wrapper

        _, code, log = self.run_go(_call_reviewers=call("review", reviewers), _call_rereviewers=call("rereview", rereviewers))
        self.assertEqual(code, 0, log)
        self.assertEqual(sorted(seen), ["rereview", "review"])
        for jobs in seen.values():
            for job in jobs:
                self.assertNotIn("worktree", job)  # 트리는 호출 때 정해진다
                for key, value in job.items():
                    if key != "on_wait":  # 대기·측정을 state에 적는 통로(_call_reviewers docstring)
                        self.assertNotIsInstance(value, (go.Run, go.Active, state.State, state.TicketState, worker.Proc), key)
        self.assertEqual(seen["rereview"][0]["found"][0]["rereview"], "")  # 호출 때의 값 그대로다
        self.assertEqual(self.ts().review["findings"][0]["rereview"], review.RESOLVED)


class NetworkAbortStageTest(test_review_target.Base):
    def test_abort_in_review_keeps_the_mark_left_before_the_stage(self):
        with recorded() as events, mock.patch("gs.review.run", side_effect=transient.NetworkAbort("리뷰 끊김")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, go.EXIT_NETWORK, out + err)
        self.assertEqual(order(events), CHECK + MARK + ["_review_stage", "_review", "_call_reviewers"])
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.review), (state.PENDING, 0, {}))
        self.assertEqual((ts.network_resume["done"], ts.network_resume["fix"]), (True, 0))
        # 다음 gs go는 worker를 다시 띄우지 않고 리뷰부터 잇는다
        with recorded() as events:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(order(events), CHECK + REVIEW + NO_FIX + MERGE)
        self.assertEqual(self.calls(), ["01"])

    def test_abort_in_rereview_keeps_the_mark_left_before_the_stage(self):
        self.findings("codex", finding("FIX A: 값이 틀렸다"))
        with recorded() as events, mock.patch("gs.review.rereview", side_effect=transient.NetworkAbort("재리뷰 끊김")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, go.EXIT_NETWORK, out + err)
        self.assertEqual(order(events), CHECK + REVIEW + TO_FIX + FIX_CHECK + MARK
                         + ["_review_stage", "_rereview", "_call_rereviewers"])
        mark = self.ts().network_resume
        self.assertEqual((mark["done"], mark["fix"]), (True, 1))
        # 다음 gs go는 수정 worker를 다시 띄우지 않고 재리뷰부터 잇는다
        self.answer("codex", 1, [(1, "resolved", "확인")])
        with recorded() as events:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(order(events), FIX_CHECK + REREVIEW + NO_FIX + MERGE)
        self.assertEqual(self.lines("fix.log"), ["fix 01 1"])


class NetworkWaitStageTest(support.GoTest):
    """가짜 claude를 실제 어댑터로 돌린다(test_network_wait와 같다): 일시 오류 판별이 진짜 경로다.

    회복은 다시 띄운 worker가 끝나는 것으로만 일어나게 한다. 시험 시계(1분 = 0.05초)에서는 조용히 돈 시간이 0.25초만 넘어도
    회복이라, 그대로 두면 worker가 느린 만큼 미룸 순서가 달라진다.
    """
    N = test_network_wait.NetworkTest
    fake, transient_first, tickets = N.fake, N.transient_first, N.tickets

    def setUp(self):
        super().setUp()
        for patch in (mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.N.MINUTE}),
                      mock.patch.object(transient, "RECOVERY_MINUTES", 10 ** 6)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")

    def test_transient_end_is_held_at_the_check_before_any_review(self):
        self.transient_first()
        with recorded() as events:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(order(events), HELD + PROBE_ENDED + CHECK + REVIEW + NO_FIX + MERGE)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].network_resume, {})

    def test_worker_ended_during_outage_is_parked_at_the_check_until_recovery(self):
        # 파일 신호로 순서를 잡는다: 12는 11이 대기에 들어간 뒤 끝나고, 다시 띄운 11은 12가 미뤄진 뒤 끝난다.
        self.fake("claude", textwrap.dedent(f'''\
            status="$GS_WORKTREE/../../state.json"
            await() {{ for i in $(seq 2000); do grep -q "$1" "$status" && return; sleep 0.02; done; }}
            case "$GS_TICKET" in
              11) if [ "$n" = 1 ]; then echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
                  await '"done": true' ;;
              12) await '네트워크 대기' ;;
            esac
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        with recorded() as events:
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(order(events, "11"), HELD + PROBE_ENDED + CHECK + REVIEW + NO_FIX + MERGE)
        self.assertEqual(order(events, "12"), PARKED + CHECK + REVIEW + NO_FIX + MERGE)
        self.assertLess(events.index(("11", "_net_hold")), events.index(("12", "_net_park")), events)
        self.assertLess(events.index(("12", "_net_park")), events.index(("11", "_review_stage")), events)
        restarted = [i for i, e in enumerate(events) if e == ("11", "_mark_resume")][1]  # 첫째는 _net_hold의 표시다
        self.assertLess(restarted, events.index(("12", "_review_stage")), events)  # 미룬 리뷰는 다시 띄운 뒤에


class MainRetryTest(support.GoTest):
    """실제 `gs go`: main 검증 실패가 코드가 같은 병합이면 revert 전에 한 번 다시 돈다. 원격에 든 revert 개수를 본다."""
    FLAKY = "flaky: main 재시도 1번 만에 통과"

    def main_fails(self, times):
        """integration(브랜치)은 통과하고 main 검증(분리 HEAD)은 앞 times번 실패한다. 돈 worktree를 bin/main_runs에 줄로 적는다."""
        (self.bin / "verify.sh").write_text(textwrap.dedent(f"""\
            git symbolic-ref -q HEAD >/dev/null && exit 0
            echo "$PWD" >> "{self.bin}/main_runs"
            test "$(wc -l < "{self.bin}/main_runs")" -gt {times}
            """))
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")

    def go_01(self):
        return self.go("--only", "01")

    def dies_in_retry(self):
        real = finish._verify

        def verify(r, wt, label):
            if label == "main-retry":
                raise RuntimeError("gs가 죽었다")
            return real(r, wt, label)

        with mock.patch("gs.finish._verify", side_effect=verify), self.assertRaisesRegex(RuntimeError, "gs가 죽었다"):
            self.go_01()
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"]), ("main_retry", False), f)
        self.assertEqual(self.reverts(), [])
        self.assertIn("file_01", self.remote_files())

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def runs(self):
        return self.lines("main_runs")

    def log(self, label):
        return self.rundir / f"finish/{label}-verify.log"

    def reverts(self):
        merge = self.finish()["merge_sha"]
        return sh(self.remote, "git", "log", "--format=%H", "--fixed-strings", f"--grep=This reverts commit {merge}", "main").split()

    def assert_flaky_kept(self):
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"]), ("verified", True), f)
        self.assertIn(self.FLAKY, f["outcome"])
        self.assertIn(f"결과: {f['outcome']}", self.final_report())
        self.assertIn("file_01", self.remote_files())
        self.assertEqual(self.reverts(), [])
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)

    def assert_reverted_once(self):
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"]), ("reverted", False), f)
        self.assertEqual(self.reverts(), [f["revert_sha"]])
        self.assertNotIn("file_01", self.remote_files())
        self.assertNotIn(self.FLAKY, f["outcome"])
        self.assertEqual(self.calls(), ["01"])

    def test_flaky_main_keeps_the_merge(self):
        self.main_fails(1)
        code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        self.assert_flaky_kept()
        self.assertTrue(self.log("main").exists())
        self.assertIn("종료 코드: 0", self.log("main-retry").read_text())
        first, second = self.runs()
        self.assertNotEqual(first, second)  # 앞 검증이 더럽힌 worktree를 쓰지 않는다
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])

    def test_second_failure_reverts_once_and_report_shows_the_last_run(self):
        self.main_fails(2)
        code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 2)
        self.assertIn("검증: `main-retry`", self.final_report())
        self.assertEqual(self.go_01()[0], 1)  # 같은 병합을 두 번 revert하지 않는다
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 2)

    def test_code_outside_goldstack_reverts_without_retry(self):
        # integration 검증을 통과한 뒤 다른 사람이 main에 push했다. 병합 커밋에 검증하지 않은 코드가 들어간다.
        self.main_fails(1)
        real = finish._publish

        def publish(r, path):
            result = real(r, path)
            self.someone("echo other > other.txt", "git add other.txt", "git commit -qm 'someone else'")
            return result

        with mock.patch("gs.finish._publish", side_effect=publish):
            code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 1)
        self.assertFalse(self.log("main-retry").exists())

    def test_old_state_without_verified_head_reverts_without_retry(self):
        self.main_fails(1)
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("gs가 죽었다")), self.assertRaisesRegex(RuntimeError, "gs가 죽었다"):
            self.go_01()
        path = self.rundir / "state.json"
        old = json.loads(path.read_text())
        del old["finish"]["verified_head"]
        path.write_text(json.dumps(old))
        code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 1)

    def test_base_moved_during_first_verify_is_a_recheck_not_flaky(self):
        self.main_fails(1)
        real = finish._verify

        def verify(r, wt, label):
            ok = real(r, wt, label)
            if label == "main":
                self.someone("echo other > other.txt", "git add other.txt", "git commit -qm 'someone else'")
            return ok

        with mock.patch("gs.finish._verify", side_effect=verify):
            code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified", f)
        self.assertNotIn("flaky", f["outcome"])
        self.assertTrue(self.log("main-recheck").exists())
        self.assertFalse(self.log("main-retry").exists())
        self.assertEqual(self.reverts(), [])

    def test_git_error_before_retry_reports_the_phase_and_next_go_continues(self):
        self.main_fails(1)
        real = finish._check_merge
        seen = []

        def check(r):
            seen.append(r.st.finish["phase"])
            if r.st.finish["phase"] == "main_retry" and seen.count("main_retry") == 1:
                raise git.GitError("일시 오류")
            return real(r)

        with mock.patch("gs.finish._check_merge", side_effect=check):
            code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"]), ("main_retry", False), f)
        report = self.final_report()
        self.assertIn("마무리: main_retry · ", report)
        self.assertIn("main 검증 실패", report)
        self.assertNotIn("병합 전", report)
        self.assertIn("검증: `main`", report)  # 재시도 전이니 실패 증거는 첫 검증이다
        self.assertEqual(len(self.runs()), 1)
        code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        self.assert_flaky_kept()

    def retry_setup_fails(self):
        real = finish._prepare_base

        def prepare(r, wt):
            return None if r.st.finish["phase"] == "main_retry" else real(r, wt)

        with mock.patch("gs.finish._prepare_base", side_effect=prepare):
            code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["main_ok"], f["outcome"]), ("main_retry", False, "base 미검증(준비 실패)"), f)
        self.assertEqual(self.reverts(), [])
        self.assertIn("file_01", self.remote_files())
        self.assertEqual(len(self.runs()), 1)
        self.assertIn("마무리: main_retry · ", self.final_report())

    def test_retry_setup_failure_passes_on_next_go_as_flaky(self):
        self.main_fails(1)
        self.retry_setup_fails()
        code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        self.assert_flaky_kept()
        self.assertEqual(len(self.runs()), 2)
        self.assertTrue(self.log("main-retry").exists())

    def test_retry_setup_failure_fails_on_next_go_and_reverts_without_a_third_run(self):
        self.main_fails(2)  # 세 번째로 돌면 통과한다. 재시도가 한 번이면 거기까지 가지 않는다
        self.retry_setup_fails()
        code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 2)

    def test_dead_retry_passes_on_next_go(self):
        self.main_fails(1)
        self.dies_in_retry()
        self.assertEqual(len(self.runs()), 1)
        code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        self.assert_flaky_kept()
        self.assertEqual(len(self.runs()), 2)  # 첫 검증을 다시 돌리지 않고 재시도를 잇는다
        self.assertTrue(self.log("main-retry").exists())

    def test_dead_retry_fails_on_next_go_and_reverts_once(self):
        self.main_fails(2)
        self.dies_in_retry()
        code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        self.assert_reverted_once()
        self.assertEqual(len(self.runs()), 2)
        self.assertEqual(self.go_01()[0], 1)
        self.assert_reverted_once()

    def test_dead_retry_after_someone_reverted_does_not_revert_again(self):
        self.main_fails(1)
        self.dies_in_retry()
        theirs = self.someone(f"git revert --no-edit -m 1 {self.finish()['merge_sha']}")
        code, out, err = self.go_01()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual((f["phase"], f["revert_sha"]), ("reverted", theirs), f)
        self.assertEqual(self.reverts(), [theirs])
        self.assertEqual(len(self.runs()), 1)

    def test_dead_retry_after_base_moved_is_a_recheck_not_flaky(self):
        self.main_fails(1)
        self.dies_in_retry()
        self.someone("echo other > other.txt", "git add other.txt", "git commit -qm 'someone else'")
        code, out, err = self.go_01()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified", f)
        self.assertNotIn("flaky", f["outcome"])
        self.assertTrue(self.log("main-recheck").exists())
        self.assertEqual(self.reverts(), [])


class CallBoundaryTest(unittest.TestCase):
    """리뷰 단계의 경계: Run·Active 없이 값만으로 부를 수 있고 결과만 돌려준다."""
    TREE = Path("/nowhere/tree")

    def test_calls_take_only_jobs_and_tree(self):
        for call in (go._call_reviewers, go._call_rereviewers, go._call_repair_reviewers):
            self.assertEqual(list(inspect.signature(call).parameters), ["jobs", "tree"])

    def test_one_reviewer_runs_on_the_tree_and_returns_its_record(self):
        rec = {"reviewer": "codex"}
        with mock.patch.object(review, "run", return_value=rec) as run:
            self.assertEqual(go._call_reviewers([{"reviewer": "codex"}], self.TREE), [rec])
        run.assert_called_once_with(reviewer="codex", worktree=self.TREE)

    def test_one_reviewer_unexpected_error_stays_in_place(self):
        boom = RuntimeError("뜻밖의 오류")
        with mock.patch.object(review, "run", side_effect=boom):
            self.assertEqual(go._call_reviewers([{"reviewer": "codex"}], self.TREE), [boom])

    def test_one_reviewer_raises_what_the_stage_handles(self):
        for error in (review.Refused("거부"), git.GitError("git"), transient.NetworkAbort("중단")):
            with self.subTest(type(error).__name__), mock.patch.object(review, "run", side_effect=error):
                with self.assertRaises(type(error)):
                    go._call_reviewers([{"reviewer": "codex"}], self.TREE)

    def test_two_reviewers_return_in_job_order_with_errors_in_place(self):
        abort = transient.NetworkAbort("중단")

        def run(*, reviewer, worktree):
            if reviewer == "agy":
                raise abort
            return {"reviewer": reviewer, "tree": worktree}

        with mock.patch.object(review, "run", side_effect=run):
            results = go._call_reviewers([{"reviewer": "codex"}, {"reviewer": "agy"}], self.TREE)
        self.assertEqual(results, [{"reviewer": "codex", "tree": self.TREE}, abort])

    def test_rereviewers_return_in_job_order_with_errors_in_place(self):
        boom = RuntimeError("뜻밖의 오류")

        def rereview(*, reviewer, worktree):
            if reviewer == "codex":
                raise boom
            return {"reviewer": reviewer, "tree": worktree}

        with mock.patch.object(review, "rereview", side_effect=rereview):
            results = go._call_rereviewers([{"reviewer": "codex"}, {"reviewer": "agy"}], self.TREE)
        self.assertEqual(results, [boom, {"reviewer": "agy", "tree": self.TREE}])


if __name__ == "__main__":
    unittest.main()
