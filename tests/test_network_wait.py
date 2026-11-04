"""네트워크 대기(v7 06): 일시 오류는 실패로 세지 않고, 기다렸다 같은 worktree에서 잇고, 상한을 넘기면 `중단(네트워크)`."""
import contextlib
import io
import json
import os
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

import support
from support import alive, sh, ticket

from gs import cli, config, feature, go, review, state, transient, worker

ERROR_RESULT = '{"type":"result","is_error":true,"api_error":"connection_failed","terminal_reason":"api_error",' \
    '"result":"API Error: Connection refused (ECONNREFUSED)"}'
OTHER_ERROR = '{"type":"result","is_error":true,"result":"boom"}'
RECONNECTING = '{"type":"error","message":"Reconnecting... waiting for network (Connection failed: x)"}'


def worker_ticket(tid, deps="[]", model="claude", reviewer="codex", second=""):
    extra = f"second_reviewer: {second}\n" if second else ""
    return (f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: {deps}\nmodel: {model}\nreviewer: {reviewer}\n{extra}---\n'
            f"## 목표\n{tid}\n")


class NetworkTest(support.GoTest):
    """가짜 claude·codex를 실제 어댑터로 돌린다: 판별(03)과 실행 스크립트까지 진짜 경로다."""
    MINUTE = "0.05"  # 1분 = 0.05초(GS_NETWORK_MINUTE). 일정 1→2→5→10분 = 0.05→0.1→0.25→0.5초

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.MINUTE})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")
        self.fake("claude", 'echo "$PWD" >> "$here/cwd_$GS_TICKET"\necho x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"\n')

    def fake(self, name, body):
        """가짜 모델 CLI. 부를 때마다 start <티켓> <회차>를 남긴다. n이 회차다."""
        path = self.bin / name
        path.write_text(textwrap.dedent('''\
            #!/bin/bash
            here="$(dirname "$0")"
            if [ "$1" = plugin ]; then echo '[]'; exit 0; fi
            n=$(( $(cat "$here/n_$GS_TICKET" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/n_$GS_TICKET"
            echo "start $GS_TICKET $n" >> "$here/events.log"
            echo $$ > "$here/pid_$GS_TICKET"
            trap 'echo "end $GS_TICKET $n" >> "$here/events.log"' EXIT
        ''') + body)
        path.chmod(0o755)

    def tickets(self, text, spec_workers=None):
        """티켓 파일들을 {티켓: 본문}으로 쓰고 커밋·push한다."""
        for tid, body in text.items():
            (self.repo / f".goldstack/work/demo/tickets/{tid}-t.md").write_text(body)
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "tickets")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        if spec_workers:
            self.parallel(spec_workers)

    def limit(self, minutes):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("network_wait_minutes = 60", f"network_wait_minutes = {minutes}"))

    def ticket_state(self, tid):
        return state.load(self.rundir, "demo").tickets[tid]

    def event_log(self):
        return [line for line in (self.bin / "events.log").read_text().splitlines()]

    def transient_first(self, leftover="partial.txt"):
        """첫 회차는 커밋 안 한 파일을 남기고 연결 오류로 끝난다. 다음 회차는 남은 파일을 보고 커밋한다."""
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then echo left > {leftover}; echo '{ERROR_RESULT}'; exit 1; fi
            cat "$GS_BRIEF" > "$here/brief_$n"
            test -f {leftover} || exit 9
            echo "$PWD" > "$here/cwd_$n"
            git add -A; git commit -qm "t$GS_TICKET"
        '''))

    def test_transient_waits_and_continues_in_same_worktree(self):
        self.transient_first()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures, ts.attempts), ("merged", 0, 2), out)
        self.assertEqual(ts.failed_worktrees, [])
        self.assertEqual(ts.branch, "gs/demo/01")  # -retry-가 없다
        self.assertEqual(ts.worktree, str(self.rundir / "wt/01"))
        self.assertEqual(Path((self.bin / "cwd_2").read_text().strip()), self.rundir / "wt/01")
        self.assertTrue((self.rundir / "01/1/worker.log").exists())  # 새 시도 디렉터리, 지난 로그는 남는다
        self.assertTrue((self.rundir / "01/2/worker.log").exists())
        self.assertIn(worker.NETWORK_RESUME, (self.bin / "brief_2").read_text())
        self.assertIn("지난 시도가 네트워크로 끊겼다. `git status`와 `git diff`로 남은 변경을 보고 이어라",
                      (self.bin / "brief_2").read_text())
        self.assertIn("일시 오류(", out)
        self.assertIn("네트워크 대기(1회, 1분 뒤)", out)
        self.assertIn("■ 네트워크 회복", out)
        self.assertEqual(ts.transient_errors, 1)
        self.assertGreater(ts.network_wait_seconds, 0)
        self.assertEqual(ts.network_resume, {})
        net = state.load(self.rundir, "demo").network
        self.assertEqual(net["errors"], 1)
        self.assertGreater(net["waited_seconds"], 0)
        self.assertEqual(net["wait"], {})
        self.assertEqual(self.merged(), ["01"])

    def test_commits_of_interrupted_attempt_count(self):
        """앞 시도의 커밋만 있고 다음 시도가 더 안 해도 `커밋 없음`이 아니다."""
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then echo x > file_01; git add -A; git commit -qm work; echo '{ERROR_RESULT}'; exit 1; fi
            exit 0
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ticket_state("01").failures, 0)
        self.assertIn("file_01", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_other_failure_retries_in_new_worktree(self):
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then echo '{OTHER_ERROR}'; exit 1; fi
            echo x > file_01; git add -A; git commit -qm t01
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures, ts.attempts, ts.transient_errors), ("merged", 1, 2, 0), out)
        self.assertEqual(ts.branch, "gs/demo/01-retry-1")
        self.assertEqual(ts.failed_worktrees, [str(self.rundir / "wt/01")])
        self.assertNotIn("네트워크 대기", out)
        self.assertNotIn(worker.NETWORK_RESUME, (self.rundir / "01/2/brief.md").read_text())

    def test_two_other_failures_still_fail_ticket(self):
        self.fake("claude", f"echo '{OTHER_ERROR}'; exit 1\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures), ("failed", 2))

    def test_nothing_new_starts_while_waiting_and_running_worker_is_left_alone(self):
        """대기 중 12는 끝나도 리뷰를 미루고 13은 시작하지 않는다. 진행 바에 대기가 보인다."""
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "3"})  # 12가 첫 대기(3초) 안에 끝나게
        patch.start()
        self.addCleanup(patch.stop)
        (self.bin / "reviewer.sh").write_text(support.FAKE_REVIEWER + '\necho review >> "$here/events.log"\n')
        self.fake("claude", textwrap.dedent(f'''\
            case "$GS_TICKET" in
              11) if [ "$n" = 1 ]; then touch "$here/cut"; echo '{ERROR_RESULT}'; exit 1; fi ;;
              12) for i in $(seq 100); do [ -f "$here/cut" ] && break; sleep 0.05; done
                  for i in $(seq 100); do grep -q '네트워크 대기' "$GS_WORKTREE/../../state.json" && break; sleep 0.02; done
                  cp "$GS_WORKTREE/../../state.json" "$here/during.json" ;;
            esac
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12"), "13": ticket("13", '["12"]')}, spec_workers=2)
        code, out, err = self.go("--only", "11,12,13")
        self.assertEqual(code, 0, out + err)
        ev = self.event_log()
        self.assertLess(ev.index("end 12 1"), ev.index("start 11 2"), ev)  # 도는 worker는 그대로 끝났다
        self.assertLess(ev.index("start 11 2"), ev.index("review"), ev)  # 그 리뷰는 다시 띄운 뒤에
        self.assertLess(ev.index("end 11 2"), ev.index("start 13 1"), ev)  # 새 worker는 회복 뒤에
        self.assertIn("[12] 네트워크 대기 중이라 리뷰를 회복 뒤로 미룬다", out)
        line = json.loads((self.bin / "during.json").read_text())["progress"]["line"]
        self.assertIn("네트워크 대기(1회, 1분 뒤)", line)
        tickets = state.load(self.rundir, "demo").tickets
        self.assertEqual({t: tickets[t].status for t in ("11", "12", "13")},
                         {"11": "merged", "12": "merged", "13": "merged"})
        self.assertEqual((tickets["11"].failures, tickets["12"].attempts), (0, 1))

    def test_restarted_worker_running_long_enough_means_recovered(self):
        """다시 띄운 11이 5분(시험에서 0.25초) 돌면 끝나기 전에 13을 시작한다. 11은 13이 시작해야 끝난다."""
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 11 ]; then
              if [ "$n" = 1 ]; then touch "$here/cut"; echo '{ERROR_RESULT}'; exit 1; fi
              for i in $(seq 400); do [ -f "$here/n_13" ] && break; sleep 0.05; done
              [ -f "$here/n_13" ] || exit 7
            fi
            if [ "$GS_TICKET" = 12 ]; then for i in $(seq 100); do [ -f "$here/cut" ] && break; sleep 0.05; done; fi
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12"), "13": ticket("13", '["12"]')}, spec_workers=2)
        code, out, err = self.go("--only", "11,12,13")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ticket_state("11").failures, 0, out)
        self.assertIn("■ 네트워크 회복", out)

    def test_restarted_codex_still_reconnecting_is_not_recovered(self):
        """다시 띄운 codex가 Reconnecting 뒤 조용하면 5분(0.25초)이 지나도 회복이 아니다. 다른 이벤트가 나온 뒤에야 13이 시작한다."""
        self.fake("codex", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then touch "$here/cut"; echo '{RECONNECTING}'; exit 1; fi
            echo '{RECONNECTING}'
            sleep 1.5
            if [ -f "$here/n_13" ]; then touch "$here/early"; fi
            echo '{{"type":"item.completed"}}'
            for i in $(seq 400); do [ -f "$here/n_13" ] && break; sleep 0.05; done
            [ -f "$here/n_13" ] || exit 7
            echo x > file_11; git add -A; git commit -qm t11
        '''))
        self.fake("claude", textwrap.dedent('''\
            if [ "$GS_TICKET" = 12 ]; then for i in $(seq 100); do [ -f "$here/cut" ] && break; sleep 0.05; done; fi
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": worker_ticket("11", model="codex", reviewer="claude"), "12": ticket("12"),
                      "13": ticket("13", '["12"]')}, spec_workers=2)
        code, out, err = self.go("--only", "11,12,13")
        self.assertEqual(code, 0, out + err)
        self.assertFalse((self.bin / "early").exists(), out)
        self.assertEqual(self.ticket_state("11").failures, 0, out)
        self.assertIn("■ 네트워크 회복", out)

    def test_abort_stops_workers_without_finish_then_next_go_continues(self):
        self.limit(1)  # 대기 1번(0.05초) 뒤 다시 끊기면 넘는다
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$GS_TICKET" = 12 ] && [ ! -f "$here/up" ]; then sleep 30; exit 1; fi
            if [ ! -f "$here/up" ]; then echo left > partial.txt; echo '{ERROR_RESULT}'; exit 1; fi
            if [ "$GS_TICKET" = 11 ] && [ ! -f "$here/twice" ]; then  # 재개 뒤 한 번 더 끊겨도 합계를 새로 세 중단이 아니다
              touch "$here/twice"; echo '{ERROR_RESULT}'; exit 1
            fi
            test "$GS_TICKET" = 12 || test -f partial.txt || exit 9
            cat "$GS_BRIEF" > "$here/brief_$GS_TICKET"
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        self.tickets({"11": ticket("11"), "12": ticket("12")}, spec_workers=2)
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertIn("■ 마무리: 중단(네트워크)", out)
        self.assertFalse(alive(int((self.bin / "pid_12").read_text())))  # 돌던 worker를 끝냈다
        st = state.load(self.rundir, "demo")
        for tid in ("11", "12"):
            ts = st.tickets[tid]
            self.assertEqual((ts.status, ts.failures, ts.failed_worktrees), ("pending", 0, []), out)
        self.assertEqual(st.tickets["11"].transient_errors, 2)  # 처음 끊김과 다시 띄운 뒤 끊김
        self.assertEqual(st.finish, {})  # 마무리를 하지 않았다
        self.assertTrue(st.network["aborted"])
        self.assertFalse((self.bin / "gh.log").exists())
        _, shown = self.status("demo")
        self.assertIn("중단(네트워크)", shown.splitlines()[0])

        (self.bin / "up").touch()
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("중단", out)
        st = state.load(self.rundir, "demo")
        for tid in ("11", "12"):
            ts = st.tickets[tid]
            self.assertEqual((ts.status, ts.failures, ts.branch), ("merged", 0, f"gs/demo/{tid}"), out)
            self.assertEqual(ts.worktree, str(self.rundir / "wt" / tid))
            self.assertIn(worker.NETWORK_RESUME, (self.bin / f"brief_{tid}").read_text())
        self.assertEqual(st.tickets["11"].transient_errors, 3)  # 누적은 남는다
        self.assertEqual(st.finish["phase"], "verified")
        self.assertNotIn("aborted", st.network)

    def test_gs_killed_while_waiting_continues_in_same_worktree(self):
        self.transient_first()
        with mock.patch("gs.go._net_tick", side_effect=[None, RuntimeError("gs가 죽었다")]):
            with self.assertRaises(RuntimeError):
                self.go("--only", "01")
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures), ("running", 0))
        self.assertEqual(ts.network_resume["worktree"], str(self.rundir / "wt/01"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures, ts.branch), ("merged", 0, "gs/demo/01"), out)
        self.assertIn(worker.NETWORK_RESUME, (self.bin / "brief_2").read_text())

    def _codex_ticket(self):
        self.tickets({"11": worker_ticket("11", model="codex", reviewer="claude")})

    def test_codex_reconnecting_only_beyond_limit_aborts(self):
        self.limit(2)  # 0.1초
        self.fake("codex", f"if [ -f \"$here/up\" ]; then echo x > file_11; git add -A; git commit -qm t11; exit 0; fi\n"
                           f"while true; do echo '{RECONNECTING}'; sleep 0.02; done\n")
        self._codex_ticket()
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 3, out + err)
        self.assertIn("Reconnecting만", out)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertFalse(alive(int((self.bin / "pid_11").read_text())))
        ts = self.ticket_state("11")
        self.assertEqual((ts.status, ts.failures), ("pending", 0))
        (self.bin / "up").touch()
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 0, out + err)
        ts = self.ticket_state("11")
        self.assertEqual((ts.status, ts.failures, ts.branch), ("merged", 0, "gs/demo/11"))

    def test_codex_reconnecting_with_other_events_does_not_abort(self):
        self.limit(20)  # 1초. 합쳐서는 넘게 돈다(연속으로는 넘지 않는다)
        self.fake("codex", textwrap.dedent(f'''\
            for i in $(seq 60); do echo '{RECONNECTING}'; sleep 0.03; echo '{{"type":"item.completed"}}'; done
            echo x > file_11; git add -A; git commit -qm t11; echo '{{"type":"turn.completed"}}'
        '''))
        self._codex_ticket()
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ticket_state("11").transient_errors, 0)

    def test_fix_worker_interrupted_continues_with_same_findings(self):
        self.fake("claude", textwrap.dedent(f'''\
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              c=$(( $(cat "$here/fixes" 2>/dev/null || echo 0) + 1 )); echo $c > "$here/fixes"
              if [ "$c" = 1 ]; then echo half > half.txt; echo '{ERROR_RESULT}'; exit 1; fi
              cat "$GS_BRIEF" > "$here/fix_brief"
              test -f half.txt || exit 9
              echo fixed > fixed; git add -A; git commit -qm fix; exit 0
            fi
            echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        finding = {"severity": "high", "location": "a", "claim": "FIX 이것", "evidence": "e"}
        with self.review_with([finding]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.failures, ts.transient_errors), ("merged", 0, 1), out)
        self.assertEqual(ts.review["findings"][0]["fix_attempt"], review.ATTEMPTED)
        self.assertIn(worker.NETWORK_RESUME, (self.bin / "fix_brief").read_text())
        self.assertIn("FIX 이것", (self.bin / "fix_brief").read_text())
        self.assertTrue((self.rundir / "01/1/fix-net1/worker.log").exists())
        self.assertIn("fixed", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())


class ReviewAbortTest(support.GoTest):
    """다른 호출이 낼 중단 예외(실제로 던지는 호출은 07). 가짜 worker는 어댑터를 거치지 않는다."""

    def test_one_reviewer_abort_is_not_review_failure_and_resumes_from_review(self):
        with mock.patch("gs.review.run", side_effect=transient.NetworkAbort("리뷰 끊김")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn("gs-ticket: demo/01", self.integration("log", "--format=%B", "gs/demo/integration"))
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.failures, ts.review), ("pending", 0, {}))
        self.assertTrue(ts.network_resume["done"])
        # 다음 gs go는 worker를 다시 띄우지 않고 리뷰부터 잇는다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(self.lines("review.calls"), ["codex"])
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.worktree), ("merged", 1, str(self.rundir / "wt/01")))

    def test_two_reviewers_abort_goes_up_from_run_together(self):
        (self.repo / ".goldstack/work/demo/tickets/01-t.md").write_text(
            worker_ticket("01", second="agy"))
        sh(self.repo, "git", "commit", "-qam", "second reviewer")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        real = review.run

        def run(**job):
            if job["reviewer"] == "agy":
                raise transient.NetworkAbort("agy 끊김")
            return real(**job)

        with mock.patch("gs.review.run", side_effect=run):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn("뜻밖의 오류", out)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.failures, ts.review, ts.second_review), ("pending", 0, {}, {}))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(sorted(self.lines("review.calls")), ["agy", "codex", "codex"])

    def test_rereview_abort_goes_up_and_resumes_from_rereview(self):
        finding = {"severity": "high", "location": "a", "claim": "FIX 이것", "evidence": "e"}
        with self.review_with([finding]):
            with mock.patch("gs.review.rereview", side_effect=transient.NetworkAbort("재리뷰 끊김")):
                code, out, err = self.go("--only", "01")
            self.assertEqual(code, 3, out + err)
            self.assertNotIn("재리뷰 1차 실패", out)
            ts = state.load(self.rundir, "demo").tickets["01"]
            self.assertEqual((ts.status, ts.failures), ("pending", 0))
            self.assertEqual((ts.network_resume["fix"], ts.network_resume["done"]), (1, True))
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01"])  # 수정 worker를 다시 띄우지 않는다
        self.assertEqual(self.lines("review.calls"), ["codex", "codex"])
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.status, "merged")
        self.assertEqual(ts.review["fix"].count("수정 커밋"), 1)


class ChainAbortTest(support.GoTest):
    def test_multi_feature_stops_with_code_3(self):
        fdir = self.repo / ".goldstack/work/next"
        (fdir / "tickets").mkdir(parents=True)
        (fdir / "spec.md").write_text("---\nfeature: next\nverify: test ! -f BROKEN\n---\n")
        (fdir / "tickets/01-t.md").write_text(ticket("01"))
        def run(repo, name):
            state.save(self.rundir, state.State(feature=name, finish={"phase": "verified"},
                                                network={"aborted": "대기 합계"}))
            return 3

        with mock.patch("gs.go.go", side_effect=run) as go:
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(["--repo", str(self.repo), "go", "demo", "next"])
        self.assertEqual(code, 3)
        self.assertEqual(go.call_count, 1)
        self.assertIn("■ demo: 중단(네트워크) → 여기서 멈춤(남은: next)", out.getvalue())


class UnitTest(unittest.TestCase):
    def test_config_default_and_template(self):
        self.assertIn("network_wait_minutes = 60\n", config.DEFAULT_CONFIG)
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / ".goldstack").mkdir()
            path = repo / config.CONFIG_PATH
            path.write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            self.assertEqual(config.load(repo)[0].timeouts.network_wait_minutes, 60)
            path.write_text(config.DEFAULT_CONFIG.format(base='"main"').replace("network_wait_minutes = 60\n", ""))
            self.assertEqual(config.load(repo)[0].timeouts.network_wait_minutes, 60)  # 옛 config
            path.write_text(config.DEFAULT_CONFIG.format(base='"main"').replace("network_wait_minutes = 60",
                                                                                "network_wait_minutes = 0"))
            cfg, problems = config.load(repo)
            self.assertIsNone(cfg)
            self.assertIn("timeouts.network_wait_minutes", str(problems[0]))

    def test_backoff_schedule_and_limit(self):
        with mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "60"}):
            b = transient.Backoff()
            delays = []
            while (delay := b.next(60)) is not None:
                delays.append(delay / 60)
        self.assertEqual(delays, [1, 2, 5, 10, 10, 10, 10, 10, 2])  # 합계 60. 마지막은 상한에 맞춘다
        self.assertEqual(b.count, 9)

    def test_minute_seam(self):
        for raw, want in (("", 60), ("0.5", 0.5), ("x", 60), ("0", 60), ("-1", 60)):
            with mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": raw}):
                self.assertEqual(transient.minute_seconds(), want)

    def test_reconnect_watch(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "worker.log"
            watch = transient.ReconnectWatch(log)
            self.assertEqual(watch.stalled_for(), 0)  # 로그가 아직 없다
            log.write_text(RECONNECTING + "\n")
            watch.poll()
            first = watch.since
            self.assertIsNotNone(first)
            with log.open("a") as f:
                f.write("warning: 이벤트가 아닌 줄\n" + RECONNECTING + "\n")
            time.sleep(0.01)
            self.assertGreater(watch.stalled_for(), 0)
            self.assertEqual(watch.since, first)  # 이어진다
            with log.open("a") as f:
                f.write('{"type":"item.completed"')  # 아직 다 안 쓴 줄은 세지 않는다
            self.assertGreater(watch.stalled_for(), 0)
            with log.open("a") as f:
                f.write("}\n")
            self.assertEqual(watch.stalled_for(), 0)  # 다른 이벤트
            self.assertIsNotNone(watch.last)

    def _codex_active(self, log, **kw):
        t = feature.Ticket("01", "t", [], [], "codex", "claude", "", "", Path("01.md"))
        return go.Active(t, worker.Finished(worker.Job(t, Path("."), Path(".")), 0), "b", Path("."), "0",
                         watch=transient.ReconnectWatch(log), **kw)

    def test_quiet_seconds_reads_log_and_stays_zero_while_reconnecting(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "worker.log"
            a = self._codex_active(log, started=time.monotonic() - 100)
            self.assertGreaterEqual(a.quiet_seconds(), 100)  # 로그가 없으면 시작부터 잰다
            log.write_text(RECONNECTING + "\n")
            self.assertEqual(a.quiet_seconds(), 0)  # 아무도 poll하지 않은 Reconnecting도 본다
            a.watch.since -= 100
            a.watch.last -= 100
            self.assertEqual(a.quiet_seconds(), 0)  # 마지막 출력이 오래됐어도 재연결 중이면 회복이 아니다
            with log.open("a") as f:
                f.write('{"type":"item.completed"}\n')
            self.assertGreaterEqual(a.quiet_seconds(), 100)  # 다른 이벤트가 나오면 마지막 Reconnecting부터 잰다
            with log.open("a") as f:
                f.write(RECONNECTING + '\n{"type":"item.completed"}\n')
            self.assertLess(a.quiet_seconds(), 50)  # 새 Reconnecting이 시계를 다시 시작한다

    def test_quiet_seconds_unreadable_log_is_not_recovery(self):
        with tempfile.TemporaryDirectory() as d:  # 디렉터리는 FileNotFoundError가 아닌 OSError를 낸다
            a = self._codex_active(Path(d), started=time.monotonic() - 100)
            self.assertEqual(a.quiet_seconds(), 0)

    def test_progress_line_and_status_show_wait(self):
        st = state.State(feature="demo", started_at="2026-11-04T10:00:00+09:00")
        st.ticket("01").status = state.RUNNING
        st.ticket("01").phases = [{"attempt": 1, "phase": "network", "model": "", "started_at": st.started_at,
                                   "ended_at": ""}]
        st.ticket("02").status = state.RUNNING
        st.ticket("02").phases = [{"attempt": 1, "phase": "worker", "model": "codex", "started_at": st.started_at,
                                   "ended_at": ""}]
        st.network["wait"] = {"count": 2, "due_at": "2026-11-04T10:05:00+09:00"}
        with mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "60"}):
            p = state.calculate_progress(st, ["01", "02"], 2, at="2026-11-04T10:02:00+09:00")
        self.assertIn("네트워크 대기(2회, 3분 뒤)", p["line"])
        self.assertIn("02 worker 중(codex)", p["line"])
        self.assertEqual([x["id"] for x in p["running"]], ["02"])
        st.network["wait"] = {"count": 2, "due_at": ""}
        p = state.calculate_progress(st, ["01", "02"], 2, at="2026-11-04T10:02:00+09:00")
        self.assertIn("네트워크 회복 확인(2회)", p["line"])
        st.finished_at = "2026-11-04T10:03:00+09:00"
        p = state.calculate_progress(st, ["01", "02"], 2)
        self.assertNotIn("네트워크", p["line"])

    def test_gs_status_shows_wait(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            rundir = repo / ".goldstack/work/demo/run"
            st = state.State(feature="demo", progress={"line": "▓░ demo 0/1 · 네트워크 대기(2회, 3분 뒤) · 1분"})
            state.save(rundir, st)
            sh(repo, "git", "init", "-q")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["--repo", str(repo), "status", "demo"]), 0)
            self.assertIn("네트워크 대기(2회, 3분 뒤)", out.getvalue())

    def test_old_state_loads_without_network_fields(self):
        with tempfile.TemporaryDirectory() as d:
            rundir = Path(d)
            (rundir / "state.json").write_text(json.dumps({"feature": "demo", "tickets": {"01": {"status": "merged"}}}))
            st = state.load(rundir, "demo")
            self.assertEqual(st.network, {})
            self.assertEqual((st.tickets["01"].transient_errors, st.tickets["01"].network_resume), (0, {}))
            self.assertEqual(state.network_label(st, state.now()), "")

    def test_skill_covers_exit_code_3(self):
        text = (Path(__file__).parent.parent / "skills/go/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("종료 코드 3", text)
        self.assertIn("중단(네트워크)", text)
        self.assertIn("`gs go`를 다시 돌리면 이어 간다", text)


if __name__ == "__main__":
    unittest.main()
