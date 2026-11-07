"""`gs go`의 리뷰·수정·실패 재시도 시나리오."""
import json
import os
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from gs import config, review, state, worker
import support
from support import alive, kill_quietly, sh, ticket


class GoReviewRetryTest(support.GoTest):
    def test_progress_is_saved_during_each_phase(self):
        snapshots = []
        save = state.save

        def observe(rundir, st):
            save(rundir, st)
            # 메모리 객체가 아닌 실제 독자가 보는 중간 state.json을 읽는다.
            snapshots.append(json.loads(state.path(rundir).read_text()))

        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다",
                                "evidence": "값이 틀림"}]), mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        phases = []
        for snapshot in snapshots:
            p = snapshot["progress"]
            self.assertEqual(p["total"], 1)
            self.assertIn(p["done"], (0, 1))
            for active in p["running"]:
                if not phases or phases[-1] != active["phase"]:
                    phases.append(active["phase"])
                if active["phase"] == "review":
                    self.assertEqual((active["id"], active["model"]), ("01", "codex"))
            if snapshot["phase"] == "finish":
                self.assertEqual(p["running"], [{"id": "", "phase": "finish", "model": "claude"}])
        self.assertEqual(phases, ["worker", "review", "fix", "rereview", "verify", "finish"])
        last = snapshots[-1]
        self.assertTrue(last["finished_at"])
        self.assertEqual((last["progress"]["done"], last["progress"]["running"]), (1, []))
        self.assertEqual([p["phase"] for p in last["tickets"]["01"]["phases"]], phases)
        self.assertTrue(all(p["started_at"] and p["ended_at"] for p in last["tickets"]["01"]["phases"]))
        self.assertIn("단계별 소요:", self.final_report())
        self.assertEqual(self.status("demo")[1].splitlines()[-1], last["progress"]["line"])

    def test_review_fix_once_then_merge(self):
        self.assertEqual(self.go("--only", "01")[0], 0)  # 01이 먼저 integration에 있다: diff는 04만이어야 한다
        with self.review_with([
            {"severity": "high", "location": "file_04:1", "claim": "FIX: 값이 틀렸다", "evidence": "cat file_04 → 04"},
            {"severity": "low", "location": "file_04", "claim": "FIX 이름이 마음에 안 든다", "evidence": ""},
            {"severity": "medium", "location": "file_04", "claim": "설명 문서가 없다", "evidence": "티켓 완료 조건"},
        ]):
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04", "04"])  # 구현 worker, 수정 worker 한 번
        self.assertEqual(self.lines("fix.log"), ["fix 04"])
        self.assertEqual(self.lines("review.calls"), ["codex", "codex", "codex"])  # 01·04 한 번씩, 04 수정 뒤 재리뷰
        self.assertEqual(self.merged(), ["01", "04"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("fixed_04", files)  # 수정 커밋이 병합에 들어갔다
        self.assertIn("수정 worker 시작: 지적 1개", out)
        self.assertIn("[04] 검증 통과", out)
        self.assertTrue((self.rundir / "04/1/fix/verify.log").exists())  # 재리뷰 뒤 verify

        # reviewer에게는 merge-base 기준 그 티켓 diff와 티켓·spec 경로를 줬다
        diff = (self.bin / "review.diff").read_text()
        self.assertIn("file_04", diff)
        self.assertNotIn("file_01", diff)
        prompt = (self.bin / "review.prompt").read_text()
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/tickets/04-t.md"), prompt)
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/spec.md"), prompt)
        # 판단 모델은 새 claude -p(Opus)이고 파일 경로만 받는다
        self.assertIn("-p --model opus", (self.bin / "judge.calls").read_text())
        self.assertNotIn("값이 틀렸다", (self.bin / "judge.input").read_text())

        rec = self.review_state("04")
        self.assertEqual([(f["action"], f["fix_attempt"]) for f in rec["findings"]],
                         [("fix", review.ATTEMPTED), ("report", ""), ("report", "")])  # 근거 없는 지적은 report
        self.assertIn("근거 없음", rec["findings"][1]["why"])
        # 가짜 reviewer의 재리뷰 답은 형식이 틀렸다. 수정을 시도한 fix 지적도 고쳐졌다고 치지 않고 남긴다
        self.assertEqual([f["claim"] for f in review.remaining(rec)],
                         ["FIX: 값이 틀렸다", "FIX 이름이 마음에 안 든다", "설명 문서가 없다"])
        self.assertEqual((rec["findings"][0]["rereview"], rec["findings"][0]["rereview_reason"]),
                         (review.UNCHECKED, review.REASON_FAILED))
        brief = (self.rundir / "04/1/fix/brief.md").read_text()
        self.assertIn("FIX: 값이 틀렸다", brief)
        self.assertNotIn("마음에 안 든다", brief)
        self.assertIn("남은 리뷰 지적 3", out)

    def test_fix_findings_stay_in_report_when_rereview_unchecked(self):
        # 리뷰 #2: 수정 worker가 지적 A만 고치고 B는 거절해도 커밋·종료 코드만으로는 알 수 없다.
        # 재리뷰가 확인하지 못했으면 둘 다 unchecked로 남은 지적에 들어가 보고서에 나와야 한다.
        with self.review_with([
            {"severity": "high", "location": "file_01", "claim": "FIX A: 값이 틀렸다", "evidence": "e1"},
            {"severity": "medium", "location": "file_01", "claim": "FIX B: 경계값 누락", "evidence": "e2"},
        ]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        rec = self.review_state()
        self.assertEqual([f["claim"] for f in review.remaining(rec)], ["FIX A: 값이 틀렸다", "FIX B: 경계값 누락"])
        self.assertEqual([f["rereview"] for f in rec["findings"]], [review.UNCHECKED, review.UNCHECKED])
        report = self.final_report()
        self.assertIn("FIX A: 값이 틀렸다", report)
        self.assertIn("FIX B: 경계값 누락", report)
        self.assertIn("남은 리뷰 지적 2", out)
        self.assertEqual([f["fix_attempt"] for f in rec["findings"]], [review.ATTEMPTED, review.ATTEMPTED])

    def test_malformed_judge_output_is_isolated_to_ticket(self):
        # 리뷰 #3: 판단 모델이 형식이 틀린 JSON을 내도 코디네이터가 죽지 않는다. 리뷰 실패처럼 모두 report로 두고 병합한다
        (self.bin / "findings.json").write_text(json.dumps({"findings": [
            {"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]}))
        (self.bin / "judge").write_text('#!/bin/bash\ncat > /dev/null\necho \'{"decisions":[{"id":[],"action":"fix"}]}\'\n')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01"])
        self.assertEqual(self.lines("fix.log"), [])
        rec = self.review_state()
        self.assertIn("판단 모델 호출 불가", rec["note"])
        self.assertEqual([f["action"] for f in rec["findings"]], ["report"])

    def test_unexpected_review_error_is_isolated_to_ticket(self):
        # 리뷰 #3: 리뷰 단계의 예상 못 한 예외도 코디네이터를 죽이지 않는다. 리뷰 실패로 적고 verify로 병합한다
        with mock.patch.object(review, "run", side_effect=RuntimeError("뜻밖의 오류")):
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01", "04"])
        rec = self.review_state()
        self.assertIn("리뷰 실패", rec["note"])
        self.assertIn("뜻밖의 오류", rec["note"])
        self.assertIn("뜻밖의 오류", self.final_report())

    def test_timed_out_fix_worker_that_touched_integration_is_stopped(self):
        # 리뷰 #4: 수정 worker가 integration을 바꾼 뒤 멈춰 시간 초과되면, 실패 처리 전에 그 worker를 끝내야 한다.
        # 끝내지 않으면 재시도 worker와 함께 살아 남아 계속 바꿀 수 있다.
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              echo "fix $GS_TICKET" >> "$here/fix.log"
              if [ ! -f "$here/fix.first" ]; then
                touch "$here/fix.first"
                echo $$ > "$here/fix.pid"
                echo x > "$GS_WORKTREE/../integration/evil"
                sleep 30
                exit 1
              fi
              echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
            fi
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]), \
                mock.patch("gs.go._idle_seconds", return_value=support.IDLE_SECONDS), \
                mock.patch.object(worker, "POLL_SECONDS", 0.05):
            code, out, err = self.go("--only", "01")
        pid = int((self.bin / "fix.pid").read_text())
        self.addCleanup(kill_quietly, pid)
        self.assertEqual(code, 0, out + err)
        self.assertIn("integration worktree를 바꿨다", out)
        self.assertEqual(self.lines("fix.log"), ["fix 01", "fix 01"])
        self.assertFalse(alive(pid), "시간 초과된 수정 worker가 살아 있다")

    def test_review_report_only_merges_directly(self):
        with self.review_with([{"severity": "low", "location": "file_01", "claim": "변수 이름이 짧다",
                                "evidence": "file_01 첫 줄"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # 수정 worker 없음
        self.assertEqual(self.lines("fix.log"), [])
        self.assertEqual(self.merged(), ["01"])
        self.assertFalse((self.rundir / "01/1/fix").exists())
        rec = self.review_state()
        self.assertEqual(rec["reviewer"], "codex")
        self.assertEqual([(f["severity"], f["action"]) for f in rec["findings"]], [("low", "report")])
        self.assertEqual(len(review.remaining(rec)), 1)

    def test_same_family_reviewer_is_refused(self):
        (self.repo / ".goldstack/work/demo/tickets/10-t.md").write_text(ticket("10").replace("reviewer: codex", "reviewer: claude"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "same family")
        sh(self.repo, "git", "push", "-q", "origin", "main")
        code, out, err = self.go("--only", "10")
        self.assertEqual(code, 1)
        self.assertIn("리뷰는 다른 계열이어야 한다", err)
        self.assertIn("아무것도 띄우지 않았다", err)
        self.assertEqual((self.calls(), self.lines("review.calls")), ([], []))
        # 리뷰 단계 자체도 같은 계열이면 reviewer를 부르지 않고 거부한다
        with self.assertRaisesRegex(review.Refused, "같은 계열"):
            review.run(repo=self.repo, worktree=self.repo, rdir=self.rundir / "x", base="main", branch="main",
                       ticket=Path("t"), spec=Path("s"), model="claude", reviewer="claude",
                       cfg=config.load(self.repo)[0])
        self.assertEqual(self.lines("review.calls"), [])

    def test_failed_fix_is_discarded_and_reviewed_work_merged(self):
        (self.bin / "fixfail").touch()
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "01"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", files)
        self.assertNotIn("badfix_01", files)  # 실패한 수정은 버렸다
        rec = self.review_state()
        self.assertIn("수정 worker 실패(종료 코드 3)", rec["fix"])
        self.assertEqual(len(review.remaining(rec)), 1)  # 고치지 못한 fix 지적이 남는다
        self.assertEqual(self.lines("review.calls"), ["codex"])  # 버린 수정은 재리뷰하지 않는다
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].failures, 0)  # 티켓 실패로 세지 않는다

    def test_reviewer_failure_is_recorded_and_ticket_still_merges(self):
        with mock.patch.dict(os.environ, {"GS_REVIEWER_CMD": "echo 'not json'"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("리뷰 없음", self.review_state()["note"])
        self.assertIn("리뷰 실패", self.review_state()["note"])
        self.assertIn("리뷰 실패", self.final_report())  # 리뷰 없이 병합했다는 사실이 보고서에 나온다

    def test_idle_timeout_retries_successfully(self):
        self.timeout_retry("subprocess")

    def test_idle_timeout_terminates_process_and_herdr_pane(self):
        self.timeout_retry("herdr")

    def test_output_or_commits_reset_idle_timeout(self):
        # 각각 전체 실행 시간(6초)은 유휴 제한(5초)보다 길지만, 출력 또는 커밋이 2초마다 생긴다.
        for mode in ("output", "commits"):
            with self.subTest(mode=mode):
                tid = "17" if mode == "output" else "18"
                self.add_ticket(tid)
                (self.bin / "worker.sh").write_text(textwrap.dedent(f'''\
                    for i in 1 2 3; do
                      sleep 2
                      if [ '{mode}' = 'output' ]; then echo "working $i";
                      else echo "$i" > file_$GS_TICKET; git add -A; git commit -qm "step $i"; fi
                    done
                    echo done > file_$GS_TICKET; git add -A; git commit -qm done
                '''))
                with mock.patch("gs.go._idle_seconds", return_value=support.IDLE_SECONDS):
                    code, out, err = self.go("--only", tid)
                self.assertEqual(code, 0, out + err)
                self.assertEqual(state.load(self.rundir, "demo").tickets[tid].attempts, 1)
                self.assertNotIn("시간 초과", out)

    def test_twice_failed_skips_transitive_dependents_only(self):
        self.add_ticket("11")
        (self.repo / ".goldstack/work/demo/tickets/09-t.md").write_text(ticket("09", '["03"]'))
        self.parallel(3)
        code, out, err = self.go("--only", "02,03,09,11")
        self.assertEqual(code, 1, out + err)
        st = state.load(self.rundir, "demo").tickets
        self.assertEqual({tid: ts.status for tid, ts in st.items()},
                         {"02": "failed", "03": "skipped", "09": "skipped", "11": "merged"})
        self.assertEqual(sorted(self.calls()), ["02", "02", "11"])
        self.assertEqual((st["02"].attempts, st["02"].failures), (2, 2))
        self.assertEqual(len(st["02"].failed_worktrees), 2)
        for wt in st["02"].failed_worktrees:
            self.assertTrue(Path(wt).is_dir())
        self.assertEqual(st["03"].attempts, 0)
        self.assertEqual(st["09"].attempts, 0)
        self.assertEqual(self.merged(), ["11"])

    def test_repending_after_lost_integration_resets_failures(self):  # 07 리뷰(claude) 지적: 중간
        # 지난 실행: 01이 한 번 실패한 뒤 병합됐다(state merged, failures=1). 그 PR·integration은 버려졌다.
        self.rundir.mkdir(parents=True, exist_ok=True)
        st = state.load(self.rundir, "demo")
        ts = st.ticket("01")
        ts.status, ts.failures, ts.failure_summary = "merged", 1, ""
        state.save(self.rundir, st)
        self._fail_once_then_succeed()
        code, out, err = self.go("--only", "01")
        self.assertIn("integration에 표시가 없다", out)
        self.assertEqual(code, 0, out + err)  # 첫 실패에서 바로 failed가 되지 않고 재시도한다
        self.assertIn("한 번 재시도", out)

    def test_start_error_does_not_overwrite_previous_failure_evidence(self):  # 07 리뷰(claude) 지적: 낮음
        (self.bin / "worker.sh").write_text("exit 1\n")
        from gs import go as gomod
        real, calls = gomod.git.branch_exists, []

        def flaky(*a, **kw):
            calls.append(a)
            if any("retry" in str(x) for x in a):
                raise OSError("boom at retry start")
            return real(*a, **kw)
        with mock.patch.object(gomod.git, "branch_exists", side_effect=flaky):
            self.go("--only", "01")
        first = self.rundir / "01" / "1" / "failure.log"
        self.assertIn("종료 코드", first.read_text())
        self.assertNotIn("boom at retry start", first.read_text())

    def test_verify_failure_retries_in_fresh_worktree(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            if [ ! -f "$here/first" ]; then
              touch "$here/first" BROKEN
            else
              test ! -e BROKEN || exit 8
              grep -q '검증 실패' "$GS_BRIEF" || exit 9
            fi
            echo done > file_01; git add -A; git commit -qm done
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts), ("merged", 2))
        self.assertTrue((self.rundir / "01/1/verify.log").exists())
        self.assertTrue((self.rundir / "01/2/verify.log").exists())
        self.assertTrue((self.rundir / "wt/01/BROKEN").exists())
        self.assertNotIn("BROKEN", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_judge_failure_still_retries_with_evidence_path(self):
        with mock.patch.dict(os.environ, {"GS_JUDGE": "/does/not/exist"}):
            code, out, err = self.go("--only", "06")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual(ts.attempts, 2)
        brief = (self.rundir / "06/2/brief.md").read_text()
        self.assertIn("실패 요약 호출 불가", brief)
        self.assertIn(str(self.rundir / "06/1/failure.log"), brief)

    def test_resume_after_first_failure_keeps_retry_limit(self):
        from gs.go import _start as real_start

        def start(r, t, runner):
            if r.st.ticket(t.id).failures:
                raise RuntimeError("coordinator interrupted before retry")
            return real_start(r, t, runner)

        with mock.patch("gs.go._start", side_effect=start):
            with self.assertRaisesRegex(RuntimeError, "coordinator interrupted"):
                self.go("--only", "06")
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual((ts.status, ts.failures), ("pending", 1))
        code, out, err = self.go("--only", "06")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 2, 2))
        self.assertEqual(self.calls(), ["06", "06"])
        self.assertIn("판단 모델의 실패 요약", (self.rundir / "06/2/brief.md").read_text())

    def test_ticket_verify_timeout_retries_with_same_family(self):
        self.hang_verify("ticket")
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if [ ! -f "$here/first" ]; then
              touch "$here/first"; echo x > HANG  # 첫 시도: verify가 멈춘다
            else
              grep -q '검증 시간 초과' "$GS_BRIEF" || exit 9
            fi
            echo done > file_01; git add -A; git commit -qm done
        '''))
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        log = self.rundir / "01/1/verify.log"
        self.assertIn(f"[01] 실패: 검증 시간 초과(0.02분, 로그 {log})", out)
        self.assertIn("같은 계열(claude)로", out)
        self.assertTrue(log.read_text().endswith("\n시간 초과: 0.02분\n"))
        self.assertIn("검증 시간 초과(0.02분", (self.rundir / "01/1/failure.log").read_text())
        self.assertNotIn("시간 초과", (self.rundir / "01/2/verify.log").read_text())
        self.assertNotIn("HANG", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assert_children_dead()


if __name__ == "__main__":
    unittest.main()
