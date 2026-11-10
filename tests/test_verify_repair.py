"""goldstack-v12 02: 티켓 검증 실패를 새 시도 대신 같은 브랜치·worktree에서 수리한다.

가짜 worker는 brief로 수리 worker를 알아본다(`## 검증 실패(고칠 것)`). 수리 뒤 통과, 커밋 없는 수리의 실패, 수리 뒤 실패의 새 시도,
수리 중 재개(gs가 죽음, 네트워크), 수리하지 않는 실패, agy 상한, 옛 state를 끝까지 돌려 본다. 시간에 기대지 않고 파일 신호로 순서를 잡는다.

goldstack-v21 04: 끊긴 검증은 수리 없이 한 번 다시 돈다(InterruptedTest, InterruptedResumeTest). 검증 스크립트가 실제 신호로 죽는다.

goldstack-v22 01: gs만 SIGKILL로 죽어 살아 남은 검증을 다음 gs go가 끝낸다(StaleResumeTest, InterruptedResumeTest의 다시 검증).

goldstack-v25 03: 커밋 없이 끝났거나 실패해 버린 수리는 같은 head를 다시 검증하지 않고 시도가 실패한다. 마지막 메시지의 `브랜치 밖 원인:` 줄은 재시도 없는 실패다(NoCommitTest).

goldstack-v27 03: 그 줄은 수리 worker가 실패로 끝나도 재시도 없는 실패다. 다시 띄우지 못한 수리 worker 자리는 앞 실행의 마지막 메시지를 "(앞 실행)" 표시로 싣고,
그 메시지의 줄은 재시도 판단에 쓰지 않는다(EndAndResumeTest, AgyLimitTest).

goldstack-v30 01: 이번 실행에서 띄운 수리 worker가 그 줄을 남기고 네트워크로 끊겨도 다시 띄우지 않는다. 표식을 일시 오류 처리보다 먼저 본다
(MarkerBeforeNetworkTest는 가짜 codex로 끝까지, MarkerOrderTest는 _check_worker의 조건별로).
"""
import contextlib
import io
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_network_wait
from support import alive, group_alive, kill_group_quietly, kill_quietly, sh

from gs import config, failure, feature, go, report, retrolog, review, state, transient, verify, worker

IS_REPAIR = 'grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"'
BREAKS = 'touch BROKEN; echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"'
GOOD = 'echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"'
REPAIRS = 'git rm -q BROKEN; git commit -qm "repair $GS_TICKET"'
USELESS = 'echo tried >> "repair_$GS_TICKET"; git add -A; git commit -qm "useless $GS_TICKET"'
AFTER_HANG = 'rm -f "$here/hung"; ' + GOOD  # times_out_once_ready는 hung이 있는 동안 도는 명령을 시간 초과로 본다. 멈춘 검증 뒤에는 치운다
# 검증이 끊기는 모양들(verify.Result.interrupted). 모두 실제 신호다
TERM_SELF = "kill -TERM $$"  # 검증 스크립트가 신호로 죽는다
KILL_CHILD = "sh -c 'kill -KILL $$'; exit $?"  # 자식이 신호로 죽어 137로 끝난다
# xargs는 자식이 신호로 죽어도 1로 끝난다. 문구는 이 맥의 실측 값이다(test_verify.py)
XARGS = "sh -c 'kill -TERM $$'; echo 'xargs: sleep: terminated with signal 15; aborting'; exit 1"
NOTHING = ":"  # 이 검증은 끊기지 않는다: BROKEN이 있으면 실패, 없으면 통과다
HANG = 'echo $$ > "$here/verify.pid"; touch "$here/in_verify"; while :; do sleep 0.05; done'  # gs가 죽어도 돌아간다(gs_killed_in_verify)
STALE_LINE = "지난 실행의 검증이 아직 돌고 있어 끝냈다"


def said(text):
    """수리 worker가 text를 마지막 메시지로 남기는 셸 명령(claude의 result 이벤트 한 줄. streamfmt.last_message가 읽는다)."""
    return "echo " + shlex.quote(json.dumps({"type": "result", "result": text}, ensure_ascii=False))


NO_FIX = "고칠 곳을 찾지 못했다.\n이 티켓과 무관하게 불안정한 시험으로 보인다."  # 커밋 없이 끝난 수리 worker의 마지막 메시지
OUTSIDE = "integration .venv가 낡았다. uv sync --locked로 고쳐진다"  # 수리 worker가 짚은 브랜치 밖 원인


class Base(support.GoTest):
    def worker(self, first, repair, retry=None):
        """구현 worker는 first(새 시도면 retry, 없으면 first), 수리 worker는 repair를 돈다. 부를 때마다 calls.log에 적고 수리 brief를 남긴다."""
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if {is_repair}; then
              n=$(( $(cat "$here/repairs" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/repairs"
              cp "$GS_BRIEF" "$here/repair_brief_$n"
              {repair}
              exit $?
            fi
            if grep -q '^## 지난 시도 실패 요약' "$GS_BRIEF"; then
              {retry}
              exit $?
            fi
            {first}
        ''').format(is_repair=IS_REPAIR, repair=repair, first=first, retry=retry or first))

    def flaky_verify(self):
        """첫 검증만 떨어진다."""
        (self.bin / "verify.sh").write_text(f'[ -f "{self.bin}/verified" ] && exit 0\ntouch "{self.bin}/verified"\nexit 1\n')
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")

    def ts(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid]

    def phases(self, tid="01"):
        return [p["phase"] for p in self.ts(tid).phases]

    def reviewers(self):
        return self.lines("review.calls")

    def verifies(self, *runs):
        """n번째 검증은 runs[n-1]을 돌고, 거기서 끝나지 않으면 `test ! -f BROKEN`이다. 넘어간 검증(마무리 포함)은 그 시험만 돈다."""
        cases = "".join(f"  {n}) {run} ;;\n" for n, run in enumerate(runs, 1))
        (self.bin / "verify.sh").write_text(f'here="{self.bin}"\nn=$(( $(cat "$here/verifies" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/verifies"\n'
                                            f'case $n in\n{cases}esac\ntest ! -f BROKEN\n')
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")

    def ticket_verifies(self, tid="01"):
        """측정에 남은 티켓 검증(라벨, 결과). 보고서의 검증별 측정 표가 이것이다."""
        rows = state.load(self.rundir, "demo").metrics["validations"]
        return [(x["label"], x["result"]) for x in rows if x["label"].startswith(f"ticket-{tid}")]

    def stop_at_verify(self, nth=2):
        """nth번째 검증을 시작하기 전에 gs가 멈춘다."""
        real, seen = go._verify, []

        def stopping(r, t):
            seen.append(t.id)
            if len(seen) == nth:
                raise KeyboardInterrupt
            return real(r, t)

        with mock.patch("gs.go._verify", side_effect=stopping), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")

    def gs_killed_in_verify(self, log):
        """gs go를 따로 띄워 HANG 검증에 닿으면 gs만 SIGKILL한다. 살아 남은 검증의 프로세스 그룹을 돌려준다. 그 검증의 표지가 log(rundir 기준)인지 본다."""
        output = Path(self.tmp.name) / "first.log"
        with output.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "go", "demo", "--only", "01"],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            deadline = time.monotonic() + 120
            while not (self.bin / "in_verify").exists():
                self.assertIsNone(proc.poll(), output.read_text())
                self.assertLess(time.monotonic(), deadline, output.read_text())
                time.sleep(0.05)
            group = os.getpgid(int((self.bin / "verify.pid").read_text()))
            self.addCleanup(kill_group_quietly, group)
            os.kill(proc.pid, signal.SIGKILL)  # gs만 죽는다
            proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.assertTrue(group_alive(group))
        command = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(group)], capture_output=True, text=True).stdout.strip()
        self.assertTrue(command.endswith(" " + verify.mark(self.rundir / log)), command)
        return group

    def assert_stale_ended(self, group, out):
        """새 검증이 돌기 전에 옛 그룹이 끝났다: 트리를 되돌리는 준비(`■ integration:`)보다 먼저 끝냈다고 출력한다."""
        self.assertFalse(group_alive(group), out)
        self.assertIn(STALE_LINE, out)
        self.assertLess(out.index(STALE_LINE), out.index("■ integration:"), out)


class RepairTest(Base):
    def test_repair_commit_is_rereviewed_and_merged(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        # 새 시도가 아니다: 같은 브랜치·worktree이고 실패로 세지 않는다
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.branch), ("merged", 1, 0, "gs/demo/01"))
        self.assertEqual((ts.worktree, ts.failed_worktrees, ts.network_resume), (str(self.rundir / "wt/01"), [], {}))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "rereview", "verify", "finish"])
        self.assertEqual(state.PHASE_LABELS["repair"], "수리")
        self.assertNotIn("BROKEN", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        # brief에 verify.log 경로. 첫 실패의 로그는 다시 검증이 덮지 않는다
        first_log = self.rundir / "01/1/verify.log"
        self.assertIn(f"`{first_log}`", (self.bin / "repair_brief_1").read_text())
        self.assertEqual((self.rundir / "01/1/repair/brief.md").read_text(), (self.bin / "repair_brief_1").read_text())
        self.assertTrue(first_log.exists())
        self.assertTrue((self.rundir / "01/1/repair/verify.log").exists())
        self.assertIn("같은 브랜치에서 수리한다", out)

    def test_repair_diff_is_reviewed_at_the_rereview_tier(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        prompt = (self.bin / "review.prompt").read_text()
        self.assertIn("수리 커밋 diff", prompt)
        self.assertIn(str(self.rundir / "01/1/verify.log"), prompt)
        rec = self.ts().review
        tier = config.load(self.repo)[0].tiers
        [done] = rec["rereviews"]
        self.assertEqual((done["round"], done["tier"]), (review.REPAIR_ROUND, tier.rereview))
        self.assertEqual(done["actual_model"], tier.worker("codex", tier.rereview)[1].model)
        self.assertEqual(rec["reviewed_head"], done["head"])
        patch = Path(done["dir"]) / "repair.patch"
        self.assertIn("deleted file", patch.read_text())  # 수리 diff만이다
        self.assertNotIn("file_01", patch.read_text())
        self.assertIn("수리 재리뷰: 지적 0개(보고만)", rec["fix"])

    def test_measurements_tell_repair_apart(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        data = state.load(self.rundir, "demo").metrics
        self.assertIn("repair", [x["phase"] for x in data["workers"]])
        self.assertEqual([x["round"] for x in data["reviewers"]], [0, review.REPAIR_ROUND])
        labels = [(x["label"], x["result"]) for x in data["validations"]]
        self.assertEqual(labels[:2], [("ticket-01", "failed"), ("ticket-01-repair", "passed")])

    def test_status_and_report_show_the_repair_and_its_result(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        text = "수리: 시도 1 커밋 1개 → 다시 검증 통과"
        self.assertEqual(state.repair_summary(self.ts()), text)
        self.assertIn(text, self.status("demo")[1])
        report_text = self.final_report()
        self.assertIn(text, report_text)
        self.assertIn("01/1/repair", report_text)  # 측정 표의 수리 worker 줄

    def test_diff_after_catch_up_holds_only_the_repair(self):
        # 수리 전 head는 catch-up 병합까지 합친 커밋이다. 다른 티켓의 변경이 수리 diff에 들지 않는다
        self.add_ticket("11")
        self.add_ticket("12")
        self.parallel(2)
        status = self.rundir / "state.json"
        (self.bin / "worker.sh").write_text(textwrap.dedent(f'''\
            if {IS_REPAIR}; then {REPAIRS}; exit $?; fi
            if [ "$GS_TICKET" = 12 ]; then  # 11이 병합된 뒤 끝난다: 12는 catch-up을 한다
              for i in $(seq 2000); do grep -q '"status": "merged"' "{status}" && break; sleep 0.02; done
              {BREAKS}
            else {GOOD}; fi
        '''))
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        ts = self.ts("12")
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("file_11", self.integration("ls-tree", "--name-only", ts.repairs[0]["base"]).split())
        patch = Path(ts.review["rereviews"][0]["dir"]) / "repair.patch"
        self.assertNotIn("file_11", patch.read_text())

    def test_repair_that_rewrites_earlier_commits_is_discarded(self):
        self.flaky_verify()
        self.worker(GOOD, 'git reset -q --hard HEAD~1; echo other > other; git add -A; git commit -qm "rewrote"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 수리 재리뷰는 없다. 둘째는 새 시도의 첫 리뷰다
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])  # 버린 수리 뒤에 다시 검증하지 않는다
        names = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", names)
        self.assertNotIn("other", names)
        self.assertIn("이전 커밋을 지웠다", state.repair_summary(self.ts()))

    def test_verify_left_files_is_a_failure_to_repair(self):
        # 검증은 통과했지만 파일을 남겼다: 통과를 믿을 수 없는 검증 실패다
        (self.bin / "verify.sh").write_text(f'[ -f "{self.bin}/verified" ] && exit 0\ntouch "{self.bin}/verified" junk\n')
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")
        self.worker(GOOD, USELESS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(ts.repairs[0]["reason"], f"검증 중 worktree가 바뀌었다(로그 {self.rundir / '01/1/verify.log'})")

    def test_repair_after_a_fix_worker_runs_in_the_attempt_directory(self):
        patch = self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX A", "evidence": "e"}])
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if {is_repair}; then {repairs}; exit $?; fi
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              [ -f "$here/fixed" ] && exit 0  # 2차 수정은 할 것이 없다
              touch "$here/fixed" BROKEN; git add -A; git commit -qm "fix breaks verify"; exit 0
            fi
            {good}
        ''').format(is_repair=IS_REPAIR, repairs=REPAIRS, good=GOOD))
        with patch:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("fix", self.phases())
        self.assertLess(self.phases().index("fix"), self.phases().index("repair"))
        self.assertTrue((self.rundir / "01/1/repair/brief.md").exists())
        self.assertIn(f"`{self.rundir / '01/1/fix/verify.log'}`", (self.rundir / "01/1/repair/brief.md").read_text())


class RepairReviewTest(Base):
    def reviewer(self, *found):
        """첫 리뷰는 지적이 없고 수리 재리뷰만 found를 낸다."""
        (self.bin / "repair_found.json").write_text(json.dumps({"findings": list(found)}, ensure_ascii=False))
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_REVIEWER" >> "$here/review.calls"
            cat > "$here/review.prompt"
            if grep -q '수리 커밋 diff' "$here/review.prompt"; then cat "$here/repair_found.json"
            else echo '{"findings": []}'; fi
        '''))

    def test_findings_of_the_repair_review_are_report_only(self):
        self.worker(BREAKS, REPAIRS)
        patch = self.review_with([])  # 판단 모델을 부르면 FIX를 fix로 나눈다. 부르지 않아야 한다
        self.reviewer({"severity": "high", "location": "file_01", "claim": "FIX 시험을 지웠다", "evidence": "e"})
        with patch:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual(ts.status, "merged")
        self.assertEqual(self.calls(), ["01", "01"])  # 수정 worker가 없다
        [f] = ts.review["findings"]
        self.assertEqual((f["action"], f["found_round"]), (review.REPORT, review.REPAIR_ROUND))
        self.assertEqual(report.finding_status(f), "보고만")
        self.assertEqual(len(review.remaining(ts.review)), 1)
        self.assertIn("FIX 시험을 지웠다", self.final_report())
        self.assertIn("수리 재리뷰: 지적 1개(보고만)", ts.review["fix"])

    def test_unreadable_answer_does_not_block_the_merge(self):
        self.worker(BREAKS, REPAIRS)
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_REVIEWER" >> "$here/review.calls"
            cat > "$here/review.prompt"
            if grep -q '수리 커밋 diff' "$here/review.prompt"; then echo '답이 아니다'
            else echo '{"findings": []}'; fi
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        rec = self.ts().review
        self.assertEqual(self.ts().status, "merged")
        self.assertEqual(rec["rereviews"][0]["failed"], review.REASON_FAILED)
        self.assertIn("수리 재리뷰: 실패", rec["fix"])

    def test_unexpected_error_does_not_block_the_merge(self):
        self.worker(BREAKS, REPAIRS)
        with mock.patch("gs.review.repair_review", side_effect=RuntimeError("뜻밖")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ts().status, "merged")
        self.assertIn("뜻밖의 오류", self.ts().review["fix"])

    def test_both_reviewers_see_the_repair(self):
        agy = self.bin / "agy"
        agy.write_text("#!/bin/sh\nexit 1\n")
        agy.chmod(0o755)
        (self.repo / ".goldstack/work/demo/tickets/01-t.md").write_text(
            '---\nid: "01"\ntitle: t01\nblocked_by: []\nmodel: claude\nreviewer: codex\nsecond_reviewer: agy\n---\n## 목표\n01\n')
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "second reviewer")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sorted(self.reviewers()), ["agy", "agy", "codex", "codex"])
        ts = self.ts()
        self.assertEqual(ts.review["rereviews"][0]["round"], review.REPAIR_ROUND)
        self.assertEqual(ts.second_review["rereviews"][0]["round"], review.REPAIR_ROUND)
        self.assertEqual(state.load(self.rundir, "demo").agy_calls, 2)  # 첫 리뷰 1 + 수리 재리뷰 1


class NoCommitTest(Base):
    """goldstack-v25 03: 커밋 없이 끝났거나 실패해 버린 수리는 같은 head를 다시 검증하지 않고 _fail로 간다. `브랜치 밖 원인:` 줄이면 재시도도 없다.

    검증은 첫 번만 떨어진다(flaky_verify): 같은 head를 다시 검증하면 통과해 버리니, 다시 검증하지 않았다는 것이 시도 수와 측정에 드러난다.
    """

    def last_file(self, attempt=1):
        return self.rundir / f"01/{attempt}/repair" / review.WORKER_LAST

    def test_no_commit_fails_the_attempt_without_verifying_the_same_head_again(self):
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))  # 실패·재시도 한 번
        self.assertEqual(self.calls(), ["01", "01", "01"])  # 구현 + 수리 + 새 시도의 구현
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])  # ticket-01-repair가 없다
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 수리 재리뷰는 없다
        self.assertEqual(self.phases()[:5], ["worker", "review", "verify", "repair", "worker"])
        self.assertFalse((self.rundir / "01/1/repair/verify.log").exists())
        # 이유: 첫 검증 실패, 수리 결과, 마지막 메시지 경로와 요약(한 줄)
        last = self.last_file()
        self.assertEqual(last.read_text(), NO_FIX + "\n")
        [rec] = ts.repairs
        first = f"검증 실패(로그 {self.rundir / '01/1/verify.log'})"
        reason = (f"{first} → 수리 커밋 없음: 같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지 `{last}`: "
                  "고칠 곳을 찾지 못했다. 이 티켓과 무관하게 불안정한 시험으로 보인다.")
        self.assertEqual((rec["worker"], rec["result"], rec["detail"]), ("커밋 없음", state.REPAIR_FAILED, reason))
        self.assertIn(f"[01] 실패: {reason}", out)
        self.assertIn("같은 head를 다시 검증하지 않고 이 시도를 실패로 끝낸다", out)
        self.assertIn("한 번 재시도", out)
        self.assertIn(f"수리: 시도 1 커밋 없음 → 실패: {reason}", self.status("demo")[1])
        # 실패 요약 입력(failure.log)에 마지막 메시지 파일과 첫 검증 로그가 실린다
        log = (self.rundir / "01/1/repair/failure.log").read_text()
        self.assertIn(f"## {last} (", log)
        self.assertIn(f"## {self.rundir / '01/1/verify.log'} (", log)
        self.assertEqual(Path((self.bin / "failure-judge.input").read_text().splitlines()[-1]), self.rundir / "01/1/repair/failure.log")
        # 다음 시도의 brief에 마지막 메시지 파일 경로가 들어간다
        brief = (self.rundir / "01/2/brief.md").read_text()
        self.assertIn("## 지난 시도 실패 요약", brief)
        self.assertIn(f"{failure.LAST_MESSAGE}: `{last}`", brief)

    def test_failed_repair_is_discarded_and_the_attempt_fails_without_verifying_again(self):
        self.flaky_verify()
        # 커밋을 남기고 실패한 수리 worker는 `브랜치 밖 원인:` 줄이 있어도 일반 실패다: 줄은 커밋 없이 끝난 수리 worker에서만 읽는다(goldstack-v27 03부터 종료 코드와 상관없이)
        self.worker(GOOD, 'echo bad > bad_fix; git add -A; git commit -qm "bad fix"; '
                    + said(f"{review.OUT_OF_BRANCH} {OUTSIDE}") + "; exit 3")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertNotIn("bad_fix", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        [rec] = ts.repairs
        self.assertEqual(rec["worker"], "수리 worker 실패(종료 코드 3), 수리 버림")
        self.assertIn("수리 worker 실패(종료 코드 3), 수리 버림: 같은 head를 다시 검증하지 않는다", rec["detail"])
        self.assertIn(f"수리 worker 마지막 메시지 `{self.last_file()}`", rec["detail"])
        self.assertIn(f"{failure.LAST_MESSAGE}: `{self.last_file()}`", (self.rundir / "01/2/brief.md").read_text())

    def test_no_message_says_so(self):
        self.flaky_verify()
        self.worker(GOOD, "echo not-json")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertTrue(ts.repairs[0]["detail"].endswith("같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지 없음"), ts.repairs[0])
        self.assertFalse(self.last_file().exists())
        self.assertNotIn(f"{failure.LAST_MESSAGE}: `", (self.rundir / "01/2/brief.md").read_text())

    def test_long_message_is_cut_in_the_reason_but_kept_in_the_file(self):
        self.flaky_verify()
        text = "가" * 1000
        self.worker(GOOD, said(text))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        detail = self.ts().repairs[0]["detail"]
        self.assertTrue(detail.endswith(": " + "가" * go.LAST_MESSAGE_CHARS + "…"), detail)
        self.assertIn(text, self.last_file().read_text())

    def test_out_of_branch_line_fails_the_ticket_without_a_retry(self):
        self.worker(BREAKS, said(f"integration을 확인했다.\n{review.OUT_OF_BRANCH} {OUTSIDE}\n커밋하지 않는다."), retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("failed", 1, 1, {}))
        self.assertEqual(self.calls(), ["01", "01"])  # 구현 + 수리. 새 시도가 없다
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed")])
        self.assertFalse((self.rundir / "01/2").exists())
        why = f"{review.OUT_OF_BRANCH} {OUTSIDE}"
        last = self.last_file()
        first = f"검증 실패(로그 {self.rundir / '01/1/verify.log'})"
        self.assertEqual(ts.reason, f"{first} → 수리 커밋 없음, {why} (재시도하지 않는다. 수리 worker 마지막 메시지 `{last}`)")
        self.assertEqual((ts.repairs[0]["result"], ts.repairs[0]["detail"]), (state.REPAIR_FAILED, ts.reason))
        self.assertIn(f"[01] 실패: {ts.reason}", out)
        self.assertIn("브랜치 밖 원인이라 재시도하지 않고 사람에게 넘긴다", out)
        self.assertNotIn("한 번 재시도", out)
        self.assertEqual(ts.failure_summary, "")  # 재시도가 없으니 요약도 없다
        self.assertIn(f"## {last} (", (self.rundir / "01/1/repair/failure.log").read_text())
        self.assertIn(why, self.status("demo")[1])
        self.assertIn(f"| failed | {report.cell(ts.reason)}", self.final_report())  # 보고서의 티켓별 결과

    def test_out_of_branch_line_with_a_commit_is_rereviewed_as_before(self):
        self.worker(BREAKS, said(f"{review.OUT_OF_BRANCH} {OUTSIDE}") + "; " + REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "rereview", "verify", "finish"])
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")
        self.assertFalse(self.last_file().exists())  # 커밋한 수리는 마지막 메시지를 실패 이유로 옮기지 않는다

    def test_summary_lost_with_gs_is_made_again_with_the_last_message_path(self):
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX))
        with mock.patch("gs.failure.summarize", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")  # 실패를 적은 뒤 요약 호출 중에 gs가 멈춘다
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures), ("pending", 1))
        self.assertFalse(Path(ts.failure_summary).exists())
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.ts().status, self.ts().attempts), ("merged", 2))
        self.assertIn(f"{failure.LAST_MESSAGE}: `{self.last_file()}`", (self.rundir / "01/2/brief.md").read_text())

    def test_old_state_with_the_verify_mark_after_a_no_commit_repair_is_read(self):
        # 옛 gs는 커밋 없는 수리 뒤 표시를 REPAIR_VERIFY로 바꾸고 다시 검증했다. 그 사이에 죽은 state를 새 gs가 잇는다
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX))
        with mock.patch("gs.go._end_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        path = state.path(self.rundir)
        raw = json.loads(path.read_text())
        ticket_state = raw["tickets"]["01"]
        self.assertEqual(ticket_state["network_resume"]["repair"], go.REPAIR_RUN)
        ticket_state["network_resume"].update(repair=go.REPAIR_VERIFY, done=True)
        ticket_state["repairs"][-1]["worker"] = "커밋 없음"
        path.write_text(json.dumps(raw, ensure_ascii=False))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("지난 수리를 같은 worktree에서 잇는다: 다시 검증부터", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("merged", 1, 0, {}))
        self.assertEqual(self.calls(), ["01", "01"])  # 수리 worker를 다시 띄우지 않는다
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01-repair", "passed")])
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 없음 → 다시 검증 통과")


class EndAndResumeTest(Base):
    """goldstack-v27 03: 실패로 끝난 수리 worker의 `브랜치 밖 원인:` 줄과, 다시 띄우지 못한 수리 worker 자리의 앞 실행 메시지.

    앞 실행 메시지는 gs가 수리 worker의 끝을 보기 전에 멈춘 뒤(stop_before_end) 다음 gs go가 그 worker를 다시 띄우지 못하게 해서 만든다.
    """

    def repair_dir(self, name="repair"):
        return self.rundir / "01/1" / name

    def prior_file(self, name="repair"):
        """다시 띄우지 못한 자리(repair_dir(name))가 남기는 앞 실행 메시지 파일의 첫 줄. 앞 실행은 처음 수리 worker의 디렉터리다."""
        return f"{go.PRIOR_RUN} {self.repair_dir() / 'worker.log'}의 마지막 메시지다. 이번 실행에서는 수리 worker를 시작하지 않았다.\n"

    def stop_before_end(self):
        """수리 worker가 끝난 것을 보기 전에 gs가 멈춘다. 표시는 아직 돈다고 말한다: 다음 gs go가 처음 수리 디렉터리를 앞 실행으로 보고 다시 띄운다."""
        with mock.patch("gs.go._end_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        mark = self.ts().network_resume
        self.assertEqual((mark["repair"], mark["done"], Path(mark["rundir"])), (go.REPAIR_RUN, False, self.repair_dir()))

    def no_new_dir(self):
        """다시 띄울 수리 worker의 새 디렉터리(repair-net<n>)를 만들지 못한다. 대신 세운 자리는 앞 실행의 디렉터리를 그대로 쓰고, 거기에 앞 worker의 로그가 있다."""
        real = Path.mkdir

        def mkdir(path, *args, **kwargs):
            if path.name.startswith("repair-net"):
                raise OSError("disk full")
            return real(path, *args, **kwargs)

        return mock.patch.object(Path, "mkdir", mkdir)

    def no_brief(self):
        """새 디렉터리(repair-net<n>)는 만들었지만 brief를 쓰지 못한다. 대신 세운 자리의 디렉터리에는 로그가 없다."""
        real = worker.write_brief

        def write(job, *args, **kwargs):
            if job.rundir.name.startswith("repair-net"):
                raise OSError("disk full")
            return real(job, *args, **kwargs)

        return mock.patch("gs.worker.write_brief", side_effect=write)

    def test_out_of_branch_line_of_a_failed_worker_fails_the_ticket_without_a_retry(self):
        self.worker(BREAKS, said(f"integration을 확인했다.\n{review.OUT_OF_BRANCH} {OUTSIDE}") + "; exit 1", retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("failed", 1, 1, {}))
        self.assertEqual(self.calls(), ["01", "01"])  # 구현 + 수리. 새 시도가 없다
        self.assertFalse((self.rundir / "01/2").exists())
        last = self.repair_dir() / review.WORKER_LAST
        first = f"검증 실패(로그 {self.rundir / '01/1/verify.log'})"
        self.assertEqual(ts.reason, f"{first} → 수리 수리 worker 실패(종료 코드 1), 수리 버림, {review.OUT_OF_BRANCH} {OUTSIDE} "
                                    f"(재시도하지 않는다. 수리 worker 마지막 메시지 `{last}`)")
        self.assertEqual((ts.repairs[0]["result"], ts.repairs[0]["detail"]), (state.REPAIR_FAILED, ts.reason))
        self.assertIn("브랜치 밖 원인이라 재시도하지 않고 사람에게 넘긴다", out)
        self.assertNotIn("한 번 재시도", out)
        self.assertEqual(ts.failure_summary, "")
        self.assertNotIn(go.PRIOR_RUN, last.read_text())  # 이번 실행에서 띄운 worker의 메시지다

    def test_failed_worker_without_the_line_is_retried_as_before(self):
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX) + "; exit 1")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01", "01"])  # 구현 + 수리 + 새 시도의 구현
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "passed")])
        last = self.repair_dir() / review.WORKER_LAST
        self.assertEqual(last.read_text(), NO_FIX + "\n")
        self.assertEqual(ts.repairs[0]["detail"],
                         f"검증 실패(로그 {self.rundir / '01/1/verify.log'}) → 수리 수리 worker 실패(종료 코드 1), 수리 버림: "
                         f"같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지 `{last}`: "
                         "고칠 곳을 찾지 못했다. 이 티켓과 무관하게 불안정한 시험으로 보인다.")
        self.assertIn("한 번 재시도", out)
        self.assertIn(f"{failure.LAST_MESSAGE}: `{last}`", (self.rundir / "01/2/brief.md").read_text())

    def test_resume_failing_before_a_new_directory_carries_the_prior_message(self):
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX))
        self.stop_before_end()
        with self.no_new_dir():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("[01] 수리 worker를 다시 띄우지 못했다: worker를 다시 띄우지 못했다: OSError: disk full", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))  # 재시도는 그대로다
        self.assertEqual(self.calls(), ["01", "01", "01"])  # 구현 + 수리 + 새 시도의 구현. 수리를 다시 띄우지 않았다
        self.assertFalse(self.repair_dir("repair-net1").exists())
        # 대신 세운 자리는 앞 실행의 디렉터리다. 앞 worker의 로그가 거기 있어도 이번 실행에서 띄운 worker로 보지 않는다
        last = self.repair_dir() / review.WORKER_LAST
        self.assertEqual(last.read_text(), self.prior_file() + NO_FIX + "\n")
        self.assertTrue(ts.repairs[0]["detail"].endswith(
            f"수리 버림: 같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지{go.PRIOR_RUN} `{last}`: "
            "고칠 곳을 찾지 못했다. 이 티켓과 무관하게 불안정한 시험으로 보인다."), ts.repairs[0])
        self.assertIn("한 번 재시도", out)
        self.assertIn(f"## {last} (", (self.repair_dir() / "failure.log").read_text())
        self.assertIn(f"{failure.LAST_MESSAGE}: `{last}`", (self.rundir / "01/2/brief.md").read_text())

    def test_out_of_branch_line_in_the_prior_message_keeps_the_retry(self):
        self.worker(BREAKS, said(f"{review.OUT_OF_BRANCH} {OUTSIDE}"), retry=GOOD)
        self.stop_before_end()
        with self.no_new_dir():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))  # 끊긴 실행의 표식이라 재시도한다
        self.assertEqual(self.calls(), ["01", "01", "01"])
        last = self.repair_dir() / review.WORKER_LAST
        detail = ts.repairs[0]["detail"]
        self.assertTrue(detail.endswith(f"같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지{go.PRIOR_RUN} `{last}`: "
                                        f"{review.OUT_OF_BRANCH} {OUTSIDE}"), detail)
        self.assertNotIn("재시도하지 않는다", detail)
        self.assertNotIn("브랜치 밖 원인이라", out)
        self.assertIn("한 번 재시도", out)
        self.assertEqual(last.read_text(), self.prior_file() + f"{review.OUT_OF_BRANCH} {OUTSIDE}\n")

    def test_two_failed_resumes_in_a_row_carry_the_message_of_the_last_worker_that_ran(self):
        self.flaky_verify()
        self.worker(GOOD, said(NO_FIX))
        self.stop_before_end()
        # 첫 다시 띄우기는 새 디렉터리를 만들고 실패한다. 그 끝을 보기 전에 gs가 또 멈춘다
        with self.no_brief(), mock.patch("gs.go._end_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertTrue(self.repair_dir("repair-net1").is_dir())
        self.assertFalse((self.repair_dir("repair-net1") / "worker.log").exists())
        mark = self.ts().network_resume
        self.assertEqual((mark["repair"], mark["done"], Path(mark["rundir"])), (go.REPAIR_RUN, False, self.repair_dir()))
        with self.no_brief():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01", "01"])
        # 메시지는 마지막으로 돈 처음 수리 worker의 것이다. 파일은 대신 세운 자리(repair-net2)에 failure.log와 함께 있다
        last = self.repair_dir("repair-net2") / review.WORKER_LAST
        self.assertEqual(last.read_text(), self.prior_file() + NO_FIX + "\n")
        self.assertFalse((self.repair_dir() / review.WORKER_LAST).exists())
        self.assertIn(f"수리 worker 마지막 메시지{go.PRIOR_RUN} `{last}`: 고칠 곳을 찾지 못했다.", ts.repairs[0]["detail"])
        self.assertIn(f"## {last} (", (self.repair_dir("repair-net2") / "failure.log").read_text())
        self.assertIn(f"{failure.LAST_MESSAGE}: `{last}`", (self.rundir / "01/2/brief.md").read_text())

    def test_no_prior_message_says_so(self):
        self.flaky_verify()
        self.worker(GOOD, "echo not-json")
        self.stop_before_end()
        with self.no_new_dir():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertTrue(ts.repairs[0]["detail"].endswith("같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지 없음"), ts.repairs[0])
        self.assertNotIn(go.PRIOR_RUN, ts.repairs[0]["detail"])
        self.assertFalse((self.repair_dir() / review.WORKER_LAST).exists())
        self.assertNotIn(f"{failure.LAST_MESSAGE}: `", (self.rundir / "01/2/brief.md").read_text())


class FailAgainTest(Base):
    def test_failure_after_repair_starts_a_new_attempt(self):
        self.worker(BREAKS, USELESS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        # 실패는 다시 검증에서 한 번만 셌다
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual((ts.branch, ts.failed_worktrees), ("gs/demo/01-retry-1", [str(self.rundir / "wt/01")]))
        self.assertEqual(self.calls(), ["01", "01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])
        [rec] = ts.repairs
        self.assertEqual((rec["attempt"], rec["worker"], rec["result"]), (1, "커밋 1개", state.REPAIR_FAILED))
        log = self.rundir / "01/1/repair/verify.log"
        self.assertEqual(rec["detail"], f"검증 실패(로그 {log})")
        self.assertIn(f"시도 1 커밋 1개 → 실패: 검증 실패(로그 {log})", self.status("demo")[1])
        self.assertIn(f"[01] 실패: 검증 실패(로그 {log})", out)
        self.assertIn("한 번 재시도", out)
        self.assertTrue((self.rundir / "01/1/repair/failure.log").exists())
        brief = (self.rundir / "01/2/brief.md").read_text()
        self.assertIn("판단 모델의 실패 요약", brief)
        self.assertNotIn("## 검증 실패(고칠 것)", brief)

    def test_repair_uses_the_attempt_tier_and_only_the_failure_raises_it(self):
        self.worker(BREAKS, USELESS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        tiers = [(p["attempt"], p["phase"], p["tier"]) for p in self.ts().phases if p["phase"] in ("worker", "repair")]
        self.assertEqual(tiers, [(1, "worker", "medium"), (1, "repair", "medium"), (2, "worker", "large")])

    def test_each_attempt_repairs_once_then_the_ticket_fails(self):
        self.worker(BREAKS, USELESS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 2, 2))
        self.assertEqual(self.calls(), ["01"] * 4)  # 구현 + 수리가 두 번. 시도마다 수리는 한 번이다
        self.assertEqual([r["attempt"] for r in ts.repairs], [1, 2])
        self.assertEqual({r["result"] for r in ts.repairs}, {state.REPAIR_FAILED})
        self.assertEqual(ts.network_resume, {})
        summary = state.repair_summary(ts)
        self.assertIn("시도 1", summary)
        self.assertIn("시도 2", summary)
        self.assertIn(summary.splitlines()[0], self.final_report().replace("\\|", "|").replace("<br>", "\n"))

    def test_conflict_after_repair_goes_to_the_new_attempt(self):
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        with mock.patch("gs.go._catch_up", side_effect=[True, False, True]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual((ts.repairs[0]["result"], ts.repairs[0]["detail"]), (state.REPAIR_FAILED, go.CONFLICT))

    def test_timeout_after_repair_goes_to_the_new_attempt(self):
        self.hang_verify("ticket")
        self.worker(BREAKS, 'git rm -q BROKEN; echo x > HANG; git add -A; git commit -qm "repair hangs verify"', retry=AFTER_HANG)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}), support.times_out_once_ready(self.bin / "hung"):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertIn("검증 시간 초과", ts.repairs[0]["detail"])


class NotRepairedTest(Base):
    def assert_no_repair(self, tid="01"):
        ts = self.ts(tid)
        self.assertEqual(ts.repairs, [])
        self.assertNotIn("repair", self.phases(tid))
        self.assertFalse((self.rundir / tid / "1/repair").exists())

    def test_catch_up_conflict(self):
        for tid in ("21", "22"):
            self.add_ticket(tid)
        self.parallel(2)
        (self.bin / "barrier").write_text("2")  # 21과 22가 같은 integration 끝에서 시작한다
        code, out, err = self.go("--only", "21,22")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo").tickets
        second = max(("21", "22"), key=lambda tid: st[tid].attempts)
        self.assertEqual((st[second].attempts, st[second].failures), (2, 1))
        self.assert_no_repair("21")
        self.assert_no_repair("22")
        self.assertIn("conflict", (self.rundir / second / "1/failure.log").read_text())

    def test_integration_merge_conflict(self):
        for tid in ("21", "22"):
            self.add_ticket(tid)
        self.parallel(2)
        (self.bin / "barrier").write_text("2")
        with mock.patch("gs.go._catch_up", return_value=True):  # catch-up을 건너뛰면 integration 병합에서 부딪친다
            code, out, err = self.go("--only", "21,22")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo").tickets
        second = max(("21", "22"), key=lambda tid: st[tid].attempts)
        self.assert_no_repair("21")
        self.assert_no_repair("22")
        self.assertIn("integration 병합 충돌", (self.rundir / second / "1/failure.log").read_text())

    def test_verify_timeout(self):
        self.hang_verify("ticket")
        self.worker('echo x > HANG; ' + GOOD, REPAIRS, retry=AFTER_HANG)
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}), support.times_out_once_ready(self.bin / "hung"):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assert_no_repair()
        self.assertIn("검증 시간 초과", (self.rundir / "01/1/failure.log").read_text())

    def integration_moves(self, then):
        """첫 검증이 integration의 index를 바꾸고 then으로 끝난다(다른 worker가 바꾼 것과 구별되지 않는다)."""
        (self.bin / "verify.sh").write_text(textwrap.dedent(f'''\
            if [ -f "{self.bin}/moved" ]; then exit 0; fi
            touch "{self.bin}/moved" moved; git add moved
            {then}
        '''))
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")
        self.worker(GOOD, REPAIRS)

    def test_integration_changed_during_passing_verify(self):
        self.integration_moves("exit 0")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assert_no_repair()
        self.assertIn("검증하는 동안 integration이 바뀌었다", (self.rundir / "01/1/failure.log").read_text())

    def test_integration_changed_during_interrupted_verify(self):
        self.integration_moves(TERM_SELF)  # 끊겼어도 검증한 트리가 달라졌다: 다시 검증하지 않고 바로 실패다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assert_no_repair()
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        self.assertIn(f"실패 이유: 검증 실패(로그 {self.rundir / '01/1/verify.log'})", (self.rundir / "01/1/failure.log").read_text())
        self.assertNotIn("다시 검증한다", out)

    def test_integration_changed_during_failing_verify(self):
        self.integration_moves("exit 1")  # 브랜치의 결함인지 모른다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assert_no_repair()

    def test_failed_worker_is_not_repaired(self):
        self.worker("echo boom; exit 1", REPAIRS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_no_repair()
        self.assertEqual(self.calls(), ["01", "01"])

    def test_passing_verify_needs_no_repair(self):
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_no_repair()
        self.assertEqual(state.repair_summary(self.ts()), "")
        self.assertNotIn("수리", self.status("demo")[1])


class SeatTest(Base):
    def test_repair_waits_for_a_worker_seat_ahead_of_new_tickets(self):
        for tid in ("11", "12", "13"):
            self.add_ticket(tid)
        status = self.rundir / "state.json"
        # 11의 리뷰 동안 자리를 얻은 12는 11이 수리 자리를 기다리기 시작해야 끝난다
        (self.bin / "worker.sh").write_text(textwrap.dedent(f'''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if {IS_REPAIR}; then {REPAIRS}; exit $?; fi
            case "$GS_TICKET" in
              11) {BREAKS} ;;
              12) for i in $(seq 2000); do grep -q '"repair_wait"' "{status}" && break; sleep 0.02; done
                  {GOOD} ;;
              *) {GOOD} ;;
            esac
        '''))
        code, out, err = self.go("--only", "11,12,13")
        self.assertEqual(code, 0, out + err)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("repair_wait", self.phases("11"))
        self.assertEqual(state.PHASE_LABELS["repair_wait"], "수리 대기")
        # 빈 자리는 기다리던 수리가 먼저 얻는다: 13보다 앞이다
        self.assertEqual(self.calls(), ["11", "12", "11", "13"])

    def test_fix_waiting_counts_repair_seats(self):
        reviews = go.Reviews(1)
        self.addCleanup(reviews.executor.shutdown)
        reviews.tickets["01"] = go.Reviewing(None)
        self.assertFalse(reviews.fix_waiting())
        reviews.tickets["02"] = go.Reviewing(None, finished=True, repair=True)
        self.assertTrue(reviews.fix_waiting())


class ResumeTest(Base):
    def assert_same_attempt(self):
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.branch), ("merged", 1, 0, "gs/demo/01"))
        self.assertEqual((ts.failed_worktrees, ts.network_resume), ([], {}))

    def test_killed_gs_during_repair_continues_in_the_same_worktree(self):
        self.worker(BREAKS, textwrap.dedent('''\
            if [ "$n" = 1 ]; then
                echo $$ > "$here/repair.pid"; touch "$here/in_repair"
                for i in $(seq 1200); do sleep 0.05; done; exit 1
              fi
              grep -q '네트워크로 끊겼다' "$GS_BRIEF" || exit 9
              git rm -q BROKEN; git commit -qm repaired'''))
        log = Path(self.tmp.name) / "first.log"
        with log.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "go", "demo", "--only", "01"],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        old = None
        try:
            deadline = time.monotonic() + 60
            while not (self.bin / "in_repair").exists():
                self.assertIsNone(proc.poll(), log.read_text())
                self.assertLess(time.monotonic(), deadline, log.read_text())
                time.sleep(0.05)
            old = int((self.bin / "repair.pid").read_text())
            os.kill(proc.pid, signal.SIGKILL)  # gs만 죽는다. 수리 worker는 살아 남는다
            proc.wait()
            self.assertTrue(alive(old))
            ts = self.ts()
            self.assertEqual((ts.status, ts.network_resume["repair"], ts.network_resume["done"]), ("running", go.REPAIR_RUN, False))
            self.assertIn("수리: 시도 1 수리 중", self.status("demo")[1])
            self.assertIn("01 수리 중(claude)", state.load(self.rundir, "demo").progress["line"])
            code, out, err = self.go("--only", "01")
            self.assertEqual(code, 0, out + err)
            self.assertIn("수리를 같은 worktree에서 잇는다", out)
            self.assertIn("[01] 지난 실행의 worker가 아직 돌고 있어 끝냈다", out)
            self.assertFalse(alive(old))
            self.assert_same_attempt()
            self.assertEqual(self.calls(), ["01", "01", "01"])  # 구현 + 수리 + 이은 수리. 구현을 다시 하지 않는다
            brief = (self.rundir / "01/1/repair-net1/brief.md").read_text()
            self.assertIn(f"`{self.rundir / '01/1/verify.log'}`", brief)
            self.assertIn(worker.NETWORK_RESUME, brief)
            self.assertEqual(self.reviewers(), ["codex", "codex"])
        finally:
            if old:
                kill_quietly(old)

    def test_stopped_while_waiting_for_the_seat(self):
        self.worker(BREAKS, REPAIRS)
        with mock.patch("gs.go._start_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        ts = self.ts()
        self.assertEqual((ts.status, ts.network_resume["repair"], ts.network_resume["done"]), ("running", go.REPAIR_SEAT, True))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 첫 리뷰를 다시 하지 않는다

    def test_stopped_during_the_repair_rereview(self):
        self.worker(BREAKS, REPAIRS)
        with mock.patch("gs.go._apply_repair_reviews", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        ts = self.ts()
        self.assertEqual((ts.network_resume["repair"], ts.network_resume["done"]), (go.REPAIR_REVIEW, True))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])  # 수리 worker를 다시 띄우지 않는다
        self.assertEqual(self.reviewers(), ["codex", "codex", "codex"])  # 끝나지 않은 재리뷰만 다시 한다

    def test_stopped_after_the_repair_rereview_ended(self):
        self.worker(BREAKS, REPAIRS)
        real = go._leave_review

        def leave(r, rv, active, runner):
            if rv.a.repair == go.REPAIR_REVIEW:
                raise KeyboardInterrupt
            return real(r, rv, active, runner)

        with mock.patch("gs.go._leave_review", side_effect=leave), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertTrue(self.ts().network_resume["reviewed"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex"])  # 끝난 재리뷰를 다시 부르지 않는다

    def test_stopped_during_verify_after_a_repair_commit(self):
        self.worker(BREAKS, REPAIRS)
        self.stop_at_verify()
        ts = self.ts()
        self.assertEqual((ts.network_resume["repair"], ts.network_resume["done"]), (go.REPAIR_VERIFY, True))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertIn("다시 검증부터", out)
        self.assertEqual(state.repair_summary(self.ts()), "수리: 시도 1 커밋 1개 → 다시 검증 통과")

    def test_failure_after_resumed_verify_counts_once_and_does_not_repair_again(self):
        self.worker(BREAKS, USELESS, retry=GOOD)
        self.stop_at_verify()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01", "01"])  # 이어 간 다시 검증이 떨어져도 수리를 또 띄우지 않는다
        self.assertEqual(len(ts.repairs), 1)

    def test_merged_mark_lost_before_save_closes_the_repair(self):
        self.worker(BREAKS, REPAIRS)
        real = go._cleanup_merged  # 병합 저장 뒤라 먼저 표시를 되살려 "커밋 뒤 저장 전에 죽음"을 만든다

        def lost(r, tid):
            ts = r.st.ticket(tid)
            ts.status = state.RUNNING
            ts.repairs[-1]["result"] = ""
            ts.network_resume = {"branch": ts.branch, "worktree": ts.worktree, "base": "x", "fix": 0, "done": True,
                                 "rundir": str(Path(ts.log).parent), "repair": go.REPAIR_VERIFY}
            r.save()
            raise KeyboardInterrupt

        with mock.patch("gs.go._cleanup_merged", side_effect=lost), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.assertEqual(self.ts().status, "running")
        with mock.patch("gs.go._cleanup_merged", side_effect=real):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.network_resume, ts.repairs[-1]["result"]), ("merged", {}, state.REPAIR_PASSED))
        self.assertEqual(self.calls(), ["01", "01"])

    def test_missing_worktree_starts_a_new_attempt_and_closes_the_repair(self):
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        with mock.patch("gs.go._start_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        sh(self.repo, "git", "worktree", "remove", "--force", str(self.rundir / "wt/01"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual(ts.status, "merged")
        self.assertIn("이어 갈 worktree가 없거나", out)
        self.assertEqual((ts.repairs[0]["result"], ts.repairs[0]["detail"]), (state.REPAIR_FAILED, "이어 갈 worktree가 없어 새로 시작"))


class OldStateTest(Base):
    def test_old_state_is_read_and_resumes_as_before(self):
        self.worker(BREAKS, REPAIRS)
        with mock.patch("gs.go._apply_review", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        path = state.path(self.rundir)
        raw = json.loads(path.read_text())
        ticket_state = raw["tickets"]["01"]
        del ticket_state["repairs"]  # 옛 gs가 쓴 state: 수리 기록도, 표시의 repair도 없다
        self.assertTrue(ticket_state["network_resume"]["done"])
        self.assertNotIn("repair", ticket_state["network_resume"])
        path.write_text(json.dumps(raw, ensure_ascii=False))
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].repairs, [])
        self.assertEqual(state.repair_summary(state.load(self.rundir, "demo").tickets["01"]), "")
        self.assertEqual(self.status("demo")[0], 0)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01", "01"])  # 리뷰부터 이어 가고 첫 검증 실패는 수리한다
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)


class InterruptedTest(Base):
    def assert_second_run_merges(self, run):
        self.verifies(run)
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume, ts.repairs), ("merged", 1, 0, {}, []))
        self.assertEqual(self.calls(), ["01"])  # 수리 worker도 새 시도도 없다
        self.assertEqual(self.reviewers(), ["codex"])  # 재리뷰도 없다
        self.assertEqual(self.phases(), ["worker", "review", "verify", "verify", "finish"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        self.assertIn("file_01", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertIn("수리 없이 같은 트리로 한 번 다시 검증한다", out)
        self.assertFalse((self.rundir / "01/1/repair").exists())
        return ts, out

    def test_verify_killed_by_a_signal_is_verified_again_on_the_same_tree(self):
        ts, out = self.assert_second_run_merges(TERM_SELF)
        log = self.rundir / "01/1/verify.log"
        self.assertIn(f"[01] 검증 끊김(종료 코드 ", out)
        self.assertIn(f", 로그 {log}) → 수리 없이", out)
        rows = [x for x in state.load(self.rundir, "demo").metrics["validations"] if x["label"].startswith("ticket-01")]
        self.assertEqual(rows[0]["tree_sha"], rows[1]["tree_sha"])
        self.assertEqual(rows[0]["ticket_head"], rows[1]["ticket_head"])
        # 끊긴 증거를 덮지 않고 이어 쓴다. 로그 끝은 다시 검증의 종료 코드다
        text = log.read_text()
        self.assertEqual(text.count("종료 코드: "), 2, text)
        self.assertIn("끊긴 검증을 같은 트리로 다시 돌린다\n$ bash", text)
        self.assertTrue(text.endswith("\n종료 코드: 0\n"), text)

    def test_report_and_status_say_it_was_interrupted(self):
        ts, _ = self.assert_second_run_merges(TERM_SELF)
        reason = f"검증 끊김 뒤 다시 검증 통과(로그 {self.rundir / '01/1/verify.log'})"
        self.assertEqual(ts.reason, reason)
        self.assertIn(reason, self.status("demo")[1])
        text = self.final_report()
        self.assertIn(f"| merged | {reason}", text)  # 티켓별 결과
        self.assertIn("| ticket-01-끊김 | 1 | 1 |", text)  # 검증별 측정

    def test_child_killed_by_a_signal(self):
        _, out = self.assert_second_run_merges(KILL_CHILD)
        self.assertIn("[01] 검증 끊김(종료 코드 137, ", out)

    def test_xargs_line_with_exit_code_1(self):
        _, out = self.assert_second_run_merges(XARGS)
        self.assertIn("[01] 검증 끊김(종료 코드 1, ", out)

    def test_files_the_interrupted_verify_left_do_not_fail_the_second_run(self):
        self.assert_second_run_merges(f"touch stray_from_verify; {TERM_SELF}")
        log = (self.rundir / "01/1/verify.log").read_text()
        self.assertNotIn("검증 중 worktree가 바뀌었다", log)
        self.assertNotIn("stray_from_verify", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_ordinary_failure_on_the_second_run_goes_to_repair(self):
        # 로그에 첫 실행의 xargs 줄이 남아 있어도 판단에 쓰지 않는다
        self.verifies(XARGS)
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.phases(), ["worker", "review", "verify", "verify", "repair", "rereview", "verify", "finish"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01", "failed"), ("ticket-01-repair", "passed")])
        [rec] = ts.repairs
        log = self.rundir / "01/1/verify.log"
        self.assertEqual((rec["verify_log"], rec["reason"], rec["result"]), (str(log), f"검증 실패(로그 {log})", state.REPAIR_PASSED))
        self.assertIn("terminated with signal 15", log.read_text())
        self.assertIn("같은 브랜치에서 수리한다", out)
        self.assertIn("검증 끊김", out)
        self.assertIn("| ticket-01-끊김 | 1 | 1 |", self.final_report())

    def test_interrupted_twice_fails_the_ticket_and_says_so(self):
        self.verifies(TERM_SELF, KILL_CHILD, XARGS, TERM_SELF)
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume, ts.repairs), ("failed", 2, 2, {}, []))
        self.assertEqual(self.calls(), ["01", "01"])  # 시도마다 구현뿐이다. 수리 worker가 없다
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed")] * 4)
        log = self.rundir / "01/2/verify.log"
        self.assertRegex(ts.reason, r"^검증 끊김\(종료 코드 -?\d+, 로그 " + str(log) + r"\): 다시 검증도 끊겼다$")
        self.assertIn(f"[01] 실패: {ts.reason}", out)
        self.assertIn("실패 이유: 검증 끊김(종료 코드 137, ", (self.rundir / "01/1/failure.log").read_text())
        self.assertIn(ts.reason, self.status("demo")[1])
        self.assertIn(f"| failed | {ts.reason}", self.final_report())

    def test_a_new_attempt_gets_its_own_second_run(self):
        self.verifies(TERM_SELF, TERM_SELF, TERM_SELF)
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.repairs), ("merged", 2, 1, []))
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed")] * 3 + [("ticket-01", "passed")])

    def test_verify_interrupted_after_a_repair_runs_again_without_another_repair(self):
        self.verifies(NOTHING, TERM_SELF)
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01-repair-끊김", "failed"), ("ticket-01-repair", "passed")])
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")
        self.assertIn("검증 끊김 뒤 다시 검증 통과", ts.reason)
        first, second = self.rundir / "01/1/verify.log", self.rundir / "01/1/repair/verify.log"
        self.assertTrue(first.exists())
        self.assertEqual(second.read_text().count("종료 코드: "), 2)

    def test_ordinary_failure_after_a_repair_and_an_interruption_fails_the_attempt(self):
        self.verifies(NOTHING, TERM_SELF)
        self.worker(BREAKS, USELESS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01", "01"])  # 시도마다 수리는 한 번이다
        [rec] = ts.repairs
        self.assertEqual((rec["result"], rec["detail"]), (state.REPAIR_FAILED, f"검증 실패(로그 {self.rundir / '01/1/repair/verify.log'})"))

    def test_interrupted_twice_after_a_repair_fails_the_attempt(self):
        self.verifies(NOTHING, TERM_SELF, TERM_SELF)
        self.worker(BREAKS, REPAIRS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01", "01"])
        [rec] = ts.repairs
        self.assertEqual(rec["result"], state.REPAIR_FAILED)
        self.assertIn("검증 끊김", rec["detail"])
        self.assertIn("다시 검증도 끊겼다", rec["detail"])

    def test_commit_left_during_the_interrupted_verify_is_reviewed_first(self):
        # 다시 검증하기 전의 대조가 늦은 커밋을 본다. 재리뷰 뒤의 검증은 다른 트리의 새 검증이다
        wt = self.rundir / "wt/01"
        self.verifies(f'echo late > "{wt}/late"; git -C "{wt}" add -A; git -C "{wt}" commit -qm late; {TERM_SELF}', TERM_SELF)
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("merged", 1, 0, {}))
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        self.assertIn("late", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())


class StaleResumeTest(Base):
    def test_stale_ticket_verify_is_ended_and_its_files_do_not_fail_the_new_one(self):
        # 옛 검증이 트리에 계속 쓴다. 트리를 되돌리기 전에 끝내야 티켓이 `worker가 integration worktree를 바꿨다`로 실패하지 않는다
        self.verifies(HANG.replace("sleep 0.05", "echo x > stale_file; sleep 0.05"))
        self.worker(GOOD, REPAIRS)
        other = subprocess.Popen(["bash", "-c", f"sleep 300{verify.KEEP_BASH}", verify.mark(self.repo / ".goldstack/work/other/run/01/1/verify.log")],
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        self.addCleanup(other.wait)
        self.addCleanup(kill_group_quietly, other.pid)
        group = self.gs_killed_in_verify("01/1/verify.log")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_stale_ended(group, out)
        self.assertTrue(group_alive(other.pid), "다른 feature의 검증을 끝냈다")
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.repairs), ("merged", 0, []))
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "passed")])
        self.assertNotIn("stale_file", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_stale_finish_verify_is_ended(self):
        self.verifies(NOTHING, HANG)  # 첫 검증은 티켓, 둘째는 마무리의 integration이다
        self.worker(GOOD, REPAIRS)
        group = self.gs_killed_in_verify("finish/integration-verify.log")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_stale_ended(group, out)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual((self.ts().status, state.load(self.rundir, "demo").finish["phase"]), ("merged", "verified"))
        self.assertTrue((self.rundir / "finish/integration-verify.log").read_text().endswith("\n종료 코드: 0\n"))

    def test_no_stale_verify_prints_nothing(self):
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(STALE_LINE, out)
        self.assertNotIn("경고: 지난 실행의 검증", out)

    def test_ps_failing_warns_and_the_run_goes_on(self):
        self.worker(GOOD, REPAIRS)
        with mock.patch("gs.verify._ps", side_effect=OSError("ps 없음")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("■ 경고: 지난 실행의 검증을 찾지 못했다: OSError: ps 없음", out)
        self.assertEqual(self.ts().status, "merged")


class InterruptedResumeTest(Base):
    def assert_same_attempt(self):
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.branch, ts.network_resume), ("merged", 1, 0, "gs/demo/01", {}))
        return ts

    def test_gs_killed_during_the_second_run_continues_with_it(self):
        self.verifies(TERM_SELF, HANG)
        self.worker(GOOD, REPAIRS)
        group = self.gs_killed_in_verify("01/1/verify.log")  # 다시 검증은 끊긴 검증의 로그에 이어 쓴다
        mark = self.ts().network_resume
        self.assertEqual((self.ts().status, mark["verify_again"], mark["done"]), ("running", True, True))
        code, out, err = self.go("--only", "01")
        self.assert_stale_ended(group, out)
        self.assertEqual(code, 0, out + err)
        self.assertIn("끊긴 검증을 같은 worktree에서 다시 한다", out)
        self.assertIn("지난 검증이 끊겼다. 같은 worktree에서 다시 검증부터 잇는다", out)
        ts = self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01"])  # 구현을 다시 하지 않는다
        self.assertEqual(self.reviewers(), ["codex"])  # 리뷰도 다시 하지 않는다
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        self.assertIn("검증 끊김 뒤 다시 검증 통과", ts.reason)
        self.assertEqual((self.rundir / "01/1/verify.log").read_text().count("끊긴 검증을 같은 트리로 다시 돌린다"), 2)

    def test_second_run_interrupted_after_a_restart_is_still_the_second_run(self):
        self.verifies(TERM_SELF, TERM_SELF)
        self.worker(GOOD, REPAIRS)
        self.stop_at_verify()
        self.assertTrue(self.ts().network_resume["verify_again"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))  # 재시작해도 한 번을 다시 쓰지 않았다
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        self.assertIn("다시 검증도 끊겼다", (self.rundir / "01/1/failure.log").read_text())

    def test_ordinary_failure_after_a_restart_goes_to_repair(self):
        self.verifies(TERM_SELF)
        self.worker(BREAKS, REPAIRS)
        self.stop_at_verify()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)

    def test_restart_keeps_the_repair_mark(self):
        self.verifies(NOTHING, TERM_SELF)
        self.worker(BREAKS, REPAIRS)
        self.stop_at_verify(3)
        mark = self.ts().network_resume
        self.assertEqual((mark["repair"], mark["verify_again"]), (go.REPAIR_VERIFY, True))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.assert_same_attempt()
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.reviewers(), ["codex", "codex"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01-repair-끊김", "failed"), ("ticket-01-repair", "passed")])
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")

    def test_old_state_without_the_new_mark_is_read(self):
        self.verifies(TERM_SELF)
        self.worker(GOOD, REPAIRS)
        with mock.patch("gs.go._apply_review", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        path = state.path(self.rundir)
        raw = json.loads(path.read_text())
        ticket_state = raw["tickets"]["01"]
        del ticket_state["repairs"]  # 옛 gs가 쓴 state
        self.assertNotIn("verify_again", ticket_state["network_resume"])
        path.write_text(json.dumps(raw, ensure_ascii=False))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_same_attempt()
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed"), ("ticket-01", "passed")])


class NetworkRepairTest(support.GoTest):
    """가짜 claude를 실제 어댑터로 돌린다: 수리 worker의 일시 오류 판별과 대기까지 진짜 경로다."""
    N = test_network_wait.NetworkTest
    fake, limit = N.fake, N.limit

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.N.MINUTE})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")

    def ts(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid]

    def phases(self, tid):
        return [p["phase"] for p in self.ts(tid).phases]

    def repair_cut_once(self):
        """1회차 구현은 BROKEN을 커밋한다. 2회차(수리)는 연결 오류로 끝나고 3회차가 고친다."""
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then touch BROKEN; echo x > file_01; git add -A; git commit -qm t01; exit 0; fi
            if [ "$n" = 2 ]; then echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
            cat "$GS_BRIEF" > "$here/brief_$n"
            git rm -q BROKEN; git commit -qm repaired
        '''))

    def test_cut_repair_waits_and_continues_in_the_same_worktree(self):
        self.repair_cut_once()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.attempts, ts.branch), ("merged", 0, 1, "gs/demo/01"), out)
        self.assertEqual((ts.transient_errors, ts.network_resume), (1, {}))
        self.assertIn("일시 오류(", out)
        self.assertIn("■ 네트워크 회복", out)
        self.assertTrue((self.rundir / "01/1/repair/worker.log").exists())
        self.assertTrue((self.rundir / "01/1/repair-net1/worker.log").exists())
        brief = (self.bin / "brief_3").read_text()
        self.assertIn(f"`{self.rundir / '01/1/verify.log'}`", brief)
        self.assertIn(worker.NETWORK_RESUME, brief)
        self.assertEqual(state.repair_summary(ts), "수리: 시도 1 커밋 1개 → 다시 검증 통과")
        self.assertIn("repair", [x["phase"] for x in state.load(self.rundir, "demo").metrics["workers"]])

    def test_network_abort_during_repair_is_continued_by_the_next_run(self):
        self.fake("claude", textwrap.dedent(f'''\
            if [ "$n" = 1 ]; then touch BROKEN; echo x > file_01; git add -A; git commit -qm t01; exit 0; fi
            if [ "$n" -le 3 ]; then echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
            git rm -q BROKEN; git commit -qm repaired
        '''))
        self.limit(1)  # 대기 1번(0.05초) 뒤 다시 끊기면 넘는다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, go.EXIT_NETWORK, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.reason, ts.failures), ("pending", go.NETWORK_ABORT, 0))
        self.assertEqual((ts.network_resume["repair"], ts.network_resume["done"]), (go.REPAIR_RUN, False))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.failures, ts.attempts, ts.branch), ("merged", 0, 1, "gs/demo/01"), out)
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)

    def test_repair_finished_during_an_outage_is_parked_before_its_rereview(self):
        # 다른 티켓이 끊긴 동안 수리 worker가 커밋하고 끝났다. 재리뷰는 회복 뒤로 미뤄진다.
        # 파일 신호로 순서를 잡는다: 12는 11의 수리가 돌 때 끊기고, 11은 끊긴 뒤 끝나고, 다시 띄운 12는 11이 미뤄진 뒤 끝난다.
        status = self.rundir / "state.json"
        self.fake("claude", textwrap.dedent(f'''\
            await() {{ for i in $(seq 2000); do grep -q "$1" "{status}" && return; sleep 0.02; done; }}
            case "$GS_TICKET" in
              11) if [ "$n" = 1 ]; then touch BROKEN; echo x > file_11; git add -A; git commit -qm t11; exit 0; fi
                  await '네트워크 대기'
                  git rm -q BROKEN; git commit -qm repaired ;;
              12) if [ "$n" = 1 ]; then await '"phase": "repair"'; echo '{test_network_wait.ERROR_RESULT}'; exit 1; fi
                  await '"done": true'
                  echo x > file_12; git add -A; git commit -qm t12 ;;
            esac
        '''))
        for tid in ("11", "12"):
            self.add_ticket(tid)
        self.parallel(2)
        with mock.patch.object(transient, "RECOVERY_MINUTES", 10 ** 6):  # 회복은 다시 띄운 12가 끝나는 것으로만 일어난다
            code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        self.assertIn("[11] 네트워크 대기 중이라 리뷰를 회복 뒤로 미룬다", out)
        ts = self.ts("11")
        self.assertEqual((ts.status, ts.failures, ts.attempts), ("merged", 0, 1))
        self.assertIn("rereview", self.phases("11"))
        self.assertEqual(self.ts("12").status, "merged")


def codex_said(text):
    """codex worker가 text를 마지막 메시지로 남기는 셸 명령(agent_message 한 줄. streamfmt.last_message가 읽는다)."""
    return "echo " + shlex.quote(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}}, ensure_ascii=False))


# codex가 응답 도중 끊긴 이벤트(goldstack-v27-03-1의 재현). transient.reason이 일시 오류 `stream disconnected before completion`으로 본다
CUT_EVENT = {"type": "turn.failed", "error": {"message": "stream disconnected before completion: "
                                                         "error sending request for url (https://chatgpt.com/backend-api/codex/responses)"}}
CUT = "echo " + shlex.quote(json.dumps(CUT_EVENT)) + "; exit 1"
CUT_REASON = "stream disconnected before completion"
MARKED = f"integration을 확인했다.\n{review.OUT_OF_BRANCH} {OUTSIDE}"  # 표식을 남긴 수리 worker의 마지막 메시지


class MarkerBeforeNetworkTest(support.GoTest):
    """goldstack-v30 01: 이번 실행에서 띄운 수리 worker가 `브랜치 밖 원인:` 표식을 남기고 네트워크로 끊겨도 다시 띄우지 않는다.

    _check_worker가 일시 오류 처리(_net_hold)보다 표식을 먼저 본다. 가짜 codex를 실제 어댑터로 돌린다: 끊김 판별(turn.failed)과
    마지막 메시지(agent_message)가 진짜 경로다. 가짜 codex의 n회차는 runs[n-1]을 돈다(1회차는 구현, 2회차부터 수리).
    넘으면 BROKEN이 있으면 고치고(수리), 없으면 그냥 커밋한다(새 시도의 구현).
    """
    N = test_network_wait.NetworkTest
    fake, tickets = N.fake, N.tickets
    repair_dir, prior_file, no_new_dir = EndAndResumeTest.repair_dir, EndAndResumeTest.prior_file, EndAndResumeTest.no_new_dir

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": self.N.MINUTE})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD")
        self.tickets({"01": test_network_wait.worker_ticket("01", model="codex", reviewer="claude")})

    def codex(self, *runs):
        cases = "".join(f"  {n}) {run}; exit $? ;;\n" for n, run in enumerate(runs, 1))
        self.fake("codex", f'case "$n" in\n{cases}esac\n'
                           'if [ -f BROKEN ]; then git rm -q BROKEN; git commit -qm repaired; exit 0; fi\n' + GOOD + "\n")

    def ts(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid]

    def starts(self):
        return [line for line in self.lines("events.log") if line.startswith("start ")]

    def go_counting(self, *args):
        """gs go를 돌리고 (종료 코드, 출력, _net_hold 호출 수, _fail에 넘긴 retry 목록)을 돌려준다."""
        with mock.patch("gs.go._net_hold", wraps=go._net_hold) as hold, mock.patch("gs.go._fail", wraps=go._fail) as fail:
            code, out, err = self.go(*args)
        return code, out + err, hold.call_count, [c.kwargs.get("retry", True) for c in fail.call_args_list]

    def test_marked_repair_cut_by_the_network_fails_without_a_retry(self):
        self.codex(BREAKS, codex_said(MARKED) + "; " + CUT)
        code, out, holds, retries = self.go_counting("--only", "01")
        self.assertEqual(holds, 0, out)  # 표식을 일시 오류보다 먼저 본다: 끊겼어도 다시 띄우지 않는다
        self.assertEqual(retries, [False], out)
        self.assertEqual(code, 1, out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.transient_errors, ts.network_resume), ("failed", 1, 1, 0, {}))
        self.assertEqual(self.starts(), ["start 01 1", "start 01 2"])  # 구현 + 수리. 수리를 다시 띄우지 않았고 새 시도도 없다
        self.assertFalse(self.repair_dir("repair-net1").exists())
        self.assertFalse((self.rundir / "01/2").exists())
        # 실패 이유와 출력은 끊김 없이 표식을 남기고 실패한 수리 worker와 같다(EndAndResumeTest의 첫 시험)
        last = self.repair_dir() / review.WORKER_LAST
        first = f"검증 실패(로그 {self.rundir / '01/1/verify.log'})"
        self.assertEqual(ts.reason, f"{first} → 수리 수리 worker 실패(종료 코드 1), 수리 버림, {review.OUT_OF_BRANCH} {OUTSIDE} "
                                    f"(재시도하지 않는다. 수리 worker 마지막 메시지 `{last}`)")
        self.assertEqual((ts.repairs[0]["result"], ts.repairs[0]["detail"]), (state.REPAIR_FAILED, ts.reason))
        self.assertIn("[01] 수리 수리 worker 실패(종료 코드 1), 수리 버림: 브랜치 밖 원인이라 재시도하지 않고 사람에게 넘긴다", out)
        self.assertNotIn("일시 오류(", out)
        self.assertNotIn("한 번 재시도", out)
        self.assertEqual(last.read_text(), MARKED + "\n")

    def test_cut_without_the_marker_waits_for_the_network_as_before(self):
        self.codex(BREAKS, codex_said(NO_FIX) + "; " + CUT)
        code, out, holds, retries = self.go_counting("--only", "01")
        self.assertEqual(holds, 1, out)
        self.assertEqual(retries, [], out)
        self.assertEqual(code, 0, out)
        self.assertIn(f"[01] 일시 오류({CUT_REASON}): 실패로 세지 않는다", out)
        self.assertIn("■ 네트워크 회복", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.transient_errors), ("merged", 1, 0, 1))
        self.assertEqual(self.starts(), ["start 01 1", "start 01 2", "start 01 3"])  # 끊긴 수리를 같은 worktree에 다시 띄웠다
        self.assertTrue((self.repair_dir("repair-net1") / "worker.log").exists())
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)

    def test_marker_and_cut_left_by_a_prior_run_keep_the_retry(self):
        self.codex(BREAKS, codex_said(MARKED) + "; " + CUT)
        real = go._check_worker

        def stop_at_repair(r, a, *rest):
            if a.repair:
                raise KeyboardInterrupt  # 수리 worker의 끝을 보기 전에 gs가 멈춘다
            return real(r, a, *rest)

        with mock.patch("gs.go._check_worker", side_effect=stop_at_repair), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        mark = self.ts().network_resume
        self.assertEqual((mark["repair"], mark["done"], Path(mark["rundir"])), (go.REPAIR_RUN, False, self.repair_dir()))
        with self.no_new_dir():  # 다음 gs go가 수리 worker를 다시 띄우지 못한다: 이번 실행에서 띄우지 않은 자리다
            code, out, holds, retries = self.go_counting("--only", "01")
        self.assertEqual(code, 0, out)
        self.assertEqual((holds, retries), (0, [True]), out)  # 지금 동작 그대로: 끊긴 실행의 표식은 재시도 판단에 쓰지 않는다
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.starts(), ["start 01 1", "start 01 2", "start 01 3"])  # 구현 + 수리 + 새 시도의 구현
        last = self.repair_dir() / review.WORKER_LAST
        detail = ts.repairs[0]["detail"]
        self.assertTrue(detail.endswith(f"같은 head를 다시 검증하지 않는다. 수리 worker 마지막 메시지{go.PRIOR_RUN} `{last}`: "
                                        + " ".join(MARKED.split())), detail)
        self.assertNotIn("재시도하지 않는다", detail)
        self.assertNotIn("브랜치 밖 원인이라", out)
        self.assertEqual(last.read_text(), self.prior_file() + MARKED + "\n")

    def test_marked_repair_restarted_during_an_outage_is_not_a_recovery(self):
        # 수리 worker가 표식 없이 끊겨 다시 띄웠다(회복을 판정할 worker). 다시 띄운 worker가 표식을 남기고 또 끊겼다
        self.codex(BREAKS, CUT, codex_said(MARKED) + "; " + CUT)
        code, out, holds, retries = self.go_counting("--only", "01")
        self.assertEqual((holds, retries), (1, [False]), out)
        self.assertEqual(code, 1, out)
        self.assertNotIn("■ 네트워크 회복", out)  # 일시 오류로 끝난 worker는 회복의 근거가 아니다
        self.assertIn(go.NO_PROBE_LINE, out)
        self.assertLess(out.index(go.NO_PROBE_LINE), out.index("브랜치 밖 원인이라 재시도하지 않고 사람에게 넘긴다"), out)
        st = state.load(self.rundir, "demo")
        self.assertEqual(st.network["wait"], {})  # 끝난 대기를 진행 바에 남기지 않는다
        ts = st.tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.transient_errors), ("failed", 1, 1, 1))
        self.assertEqual(self.starts(), ["start 01 1", "start 01 2", "start 01 3"])
        last = self.repair_dir("repair-net1") / review.WORKER_LAST
        self.assertTrue(ts.reason.endswith(f"{review.OUT_OF_BRANCH} {OUTSIDE} (재시도하지 않는다. 수리 worker 마지막 메시지 `{last}`)"), ts.reason)


class MarkerOrderTest(unittest.TestCase):
    """goldstack-v30 01: _check_worker가 끊긴 worker를 _net_hold 대신 _end_repair로 보내는 조건. 끊김으로 판별된 worker를 직접 넘긴다(goldstack-v27-03-1의 재현과 같은 모양).

    표식은 이번 실행에서 띄운(launched) 수리 worker가 커밋 없이 끝났을 때만 일시 오류보다 먼저다. 나머지는 지금처럼 네트워크 대기다.
    """

    class Cut:
        """일시 오류로 끝난 worker. 판별은 로그와 상관없이 끊김이다: 메시지를 읽지 못하는 경우도 끊김 판별까지는 간다."""
        note = ""

        def __init__(self, job):
            self.job = job

        def transient_reason(self):
            return CUT_REASON

        def stop(self):
            pass

        def finish(self, ok):
            pass

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.rundir = self.root / "repair"
        self.rundir.mkdir()

    def log(self, message):
        (self.rundir / "worker.log").write_text(json.dumps(CUT_EVENT) + "\n" if message is None else
                                                f"{json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': message}}, ensure_ascii=False)}\n"
                                                f"{json.dumps(CUT_EVENT)}\n")

    def check(self, *, repair=go.REPAIR_RUN, fix=0, launched=True, commits=0, code=1):
        """_check_worker를 부르고 간 곳을 돌려준다: "hold"(_net_hold), "repair"(_end_repair), "fix"(_end_fix), "fail"(_fail_worker)."""
        t = feature.Ticket("01", "t", [], [], "codex", "claude", "", "", Path("01.md"))
        a = go.Active(t, self.Cut(worker.Job(t, self.root, self.rundir)), "b", self.root, "base", fix=fix, repair=repair, launched=launched)
        r = SimpleNamespace(repo=self.root, ihead="i", net=go.Outage(), st=mock.MagicMock())
        r.st.ticket.return_value.network_resume = {}
        with mock.patch("gs.go.metrics.worker_finished"), mock.patch("gs.go.git.count", return_value=commits), \
                mock.patch("gs.go._reset_integration", return_value=False), mock.patch("gs.go._net_hold") as hold, \
                mock.patch("gs.go._end_repair", return_value=False) as end, mock.patch("gs.go._end_fix", return_value=True) as end_fix, \
                mock.patch("gs.go._fail_worker") as fail, contextlib.redirect_stdout(io.StringIO()):
            go._check_worker(r, a, code, [], "")
        went = [name for name, m in (("hold", hold), ("repair", end), ("fix", end_fix), ("fail", fail)) if m.called]
        self.assertEqual(len(went), 1, went)
        if end.called:
            self.assertEqual(end.call_args.args[1:], (a, code, commits, ""))
        return went[0]

    def test_marked_repair_goes_to_end_repair(self):
        self.log(MARKED)
        self.assertEqual(self.check(), "repair")

    def test_without_the_marker_it_waits(self):
        self.log(NO_FIX)
        self.assertEqual(self.check(), "hold")

    def test_marker_not_at_a_line_start_does_not_count(self):
        self.log(f"- {review.OUT_OF_BRANCH} {OUTSIDE}")
        self.assertEqual(self.check(), "hold")

    def test_no_message_waits(self):
        self.log(None)
        self.assertEqual(self.check(), "hold")

    def test_missing_log_waits(self):
        self.assertEqual(self.check(), "hold")

    def test_unreadable_log_waits(self):
        (self.rundir / "worker.log").mkdir()  # 읽기 오류(IsADirectoryError)
        self.assertEqual(self.check(), "hold")

    def test_slot_not_launched_in_this_run_waits(self):
        self.log(MARKED)
        self.assertEqual(self.check(launched=False), "hold")

    def test_repair_with_a_commit_waits(self):
        self.log(MARKED)
        self.assertEqual(self.check(commits=1), "hold")

    def test_fix_and_implementation_workers_wait(self):
        self.log(MARKED)
        self.assertEqual(self.check(repair="", fix=1), "hold")
        self.assertEqual(self.check(repair="", fix=0), "hold")


class AgyLimitTest(Base):
    """수정 worker의 agy 상한 처리와 같다: 띄우지 않고 티켓을 실패시키지 않고 다음 단계로 간다."""

    def setUp(self):
        super().setUp()
        agy = self.bin / "agy"
        agy.write_text("#!/bin/sh\nexit 1\n")
        agy.chmod(0o755)
        (self.repo / ".goldstack/work/demo/tickets/01-t.md").write_text(
            '---\nid: "01"\ntitle: t01\nblocked_by: []\nmodel: agy\nreviewer: codex\n---\n## 목표\n01\n')
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "agy worker")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def limit(self, n):
        path = self.repo / config.CONFIG_PATH
        text = path.read_text()
        path.write_text(text.replace("max_calls_per_run = 3", f"max_calls_per_run = {n}"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", f"agy limit {n}")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def test_counted_like_other_workers(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").agy_calls, 2)  # 구현 1 + 수리 1

    def test_limit_skips_the_worker_and_verifies_again(self):
        self.limit(1)
        self.flaky_verify()
        self.worker(GOOD, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01"])  # 수리 worker를 띄우지 않았다
        self.assertEqual(self.reviewers(), ["codex"])
        self.assertEqual(state.load(self.rundir, "demo").agy_calls, 1)
        self.assertTrue(ts.repairs[0]["worker"].startswith(review.LIMIT), ts.repairs)
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)
        self.assertIn(review.LIMIT, self.status("demo")[1])
        self.assertTrue((self.rundir / "01/1/verify.log").exists())  # 다시 검증이 첫 실패의 로그를 덮지 않는다
        self.assertTrue((self.rundir / "01/1/repair/verify.log").exists())

    def test_limit_then_failed_verify_stops_at_the_limit(self):
        self.limit(1)
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual(ts.status, "failed")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("agy 한도", ts.reason)  # 새 시도도 상한에 막힌다

    def test_limit_on_resume_is_a_failed_repair(self):
        self.flaky_verify()
        self.worker(GOOD, 'echo bad > bad_fix; git add -A; git commit -qm "남은 수리"')
        with mock.patch("gs.go._end_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")  # 수리 worker가 끝난 것을 보기 전에 gs가 멈춘다. 표시는 아직 돈다고 말한다
        self.assertEqual((self.ts().network_resume["repair"], self.ts().network_resume["done"]), (go.REPAIR_RUN, False))
        self.limit(0)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        # 버린 수리 뒤에는 다시 검증하지 않고 시도가 실패한다. 새 시도도 상한에 막힌다
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 1, 2))
        self.assertIn("수리 worker를 다시 띄우지 못했다: agy 한도", out)
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed")])
        self.assertNotIn("bad_fix", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertIn("수리 worker 실패", ts.repairs[0]["worker"])
        self.assertIn("수리 버림", ts.repairs[0]["worker"])
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_FAILED)
        self.assertIn("agy 한도", ts.reason)

    def test_limit_on_resume_carries_the_prior_message_and_keeps_the_retry(self):
        # agy 한도면 새 디렉터리를 만들기 전에 그만둔다: 대신 세운 자리가 앞 실행 디렉터리라 앞 worker의 로그가 있다. 이번 실행에서 띄운 worker로 보지 않는다
        self.flaky_verify()
        self.worker(GOOD, said(f"{review.OUT_OF_BRANCH} {OUTSIDE}"))
        with mock.patch("gs.go._end_repair", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")
        self.limit(0)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 1, 2))  # 재시도했고 새 시도가 상한에 막혔다
        self.assertIn("수리 worker를 다시 띄우지 못했다: agy 한도", out)
        self.assertIn("한 번 재시도", out)
        self.assertNotIn("브랜치 밖 원인이라", out)
        last = self.rundir / "01/1/repair" / review.WORKER_LAST
        detail = ts.repairs[0]["detail"]
        self.assertTrue(detail.endswith(f"수리 worker 마지막 메시지{go.PRIOR_RUN} `{last}`: {review.OUT_OF_BRANCH} {OUTSIDE}"), detail)
        self.assertNotIn("재시도하지 않는다", detail)
        self.assertTrue(last.read_text().startswith(f"{go.PRIOR_RUN} {self.rundir / '01/1/repair/worker.log'}의 마지막 메시지다."))


class StartFailureTest(Base):
    def test_worker_that_cannot_start_verifies_again(self):
        self.flaky_verify()
        self.worker(GOOD, REPAIRS)
        real = worker.write_brief

        def write(job, *args, **kwargs):
            if job.rundir.name == "repair":
                raise OSError("disk full")
            return real(job, *args, **kwargs)

        with mock.patch("gs.worker.write_brief", side_effect=write):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("띄우지 못함: OSError: disk full", ts.repairs[0]["worker"])
        self.assertEqual(self.lines("review.calls"), ["codex"])


class SummaryTest(unittest.TestCase):
    def summary(self, *recs):
        return state.repair_summary(state.TicketState(repairs=list(recs)))

    def test_no_repair(self):
        self.assertEqual(self.summary(), "")

    def test_each_stage(self):
        self.assertEqual(self.summary({"attempt": 1, "worker": "", "result": ""}), "수리: 시도 1 수리 중")
        self.assertEqual(self.summary({"attempt": 1, "worker": "커밋 2개", "result": ""}), "수리: 시도 1 커밋 2개 → 다시 검증 중")
        self.assertEqual(self.summary({"attempt": 1, "worker": "커밋 2개", "result": "passed"}), "수리: 시도 1 커밋 2개 → 다시 검증 통과")
        self.assertEqual(self.summary({"attempt": 2, "worker": "커밋 없음", "result": "failed", "detail": "conflict"}),
                         "수리: 시도 2 커밋 없음 → 실패: conflict")
        self.assertEqual(self.summary({"attempt": 1, "worker": "", "result": "failed", "detail": "x"},
                                      {"attempt": 2, "worker": "커밋 1개", "result": "passed"}),
                         "수리: 시도 1 실패: x · 시도 2 커밋 1개 → 다시 검증 통과")

    def test_brief_points_at_the_log_and_allows_no_commit(self):
        brief = review.repair_brief("/x/verify.log")
        self.assertIn("## 검증 실패(고칠 것)", brief)
        self.assertIn("`/x/verify.log`", brief)
        self.assertIn("커밋 없이 끝나면 gs는 같은 head를 다시 검증하지 않는다", brief)
        self.assertIn("처음부터 다시 하지 말고", brief)

    def test_brief_lets_environment_differences_be_a_cause_and_asks_for_the_out_of_branch_line(self):
        brief = review.repair_brief("/x/verify.log")
        self.assertNotIn("그 위치를 원인으로 보지 마라", brief)
        self.assertIn("integration의 병합 트리에서 도는 것 자체는 정상이다", brief)
        self.assertIn("환경 차이(setup을 돌린 시각, 설치 메타데이터 같은 것)는 원인 후보로 확인한다", brief)
        self.assertIn("브랜치 안에서 고칠 수 없으면", brief)
        self.assertIn(f"커밋하지 말고\n마지막 메시지에 `{review.OUT_OF_BRANCH} <이유>`로 시작하는 줄을 쓴다", brief)
        self.assertIn("재시도 없이 사람에게 넘긴다", brief)

    def test_summary_rules_let_environment_differences_be_a_cause(self):
        self.assertNotIn("그 위치를 원인으로 지목하지 마라", failure.SUMMARY_RULES)
        self.assertIn("integration의 병합 트리에서 도는 것 자체는 정상이다", failure.SUMMARY_RULES)
        self.assertIn("환경 차이(setup을 돌린 시각, 설치 메타데이터 같은 것)는 원인 후보로 확인하라", failure.SUMMARY_RULES)
        self.assertIn("모른다고 적어라", failure.SUMMARY_RULES)

    def test_out_of_branch_line(self):
        self.assertEqual(review.out_of_branch("확인했다.\n브랜치 밖 원인: .venv가 낡았다\n끝"), ".venv가 낡았다")
        self.assertEqual(review.out_of_branch("  브랜치 밖 원인:  앞뒤 공백  "), "앞뒤 공백")
        self.assertEqual(review.out_of_branch("브랜치 밖 원인: 첫째\n브랜치 밖 원인: 둘째"), "첫째")
        for text in (None, "", "브랜치 밖 원인:", "브랜치 밖 원인:   ", "원인은 브랜치 밖 원인: 아님", "- 브랜치 밖 원인: 글머리표"):
            with self.subTest(text=text):
                self.assertEqual(review.out_of_branch(text), "")


class RetroLogTest(Base):
    def test_repair_runs_are_in_the_retro_log(self):
        self.worker(BREAKS, 'echo "수리 worker 출력"; ' + USELESS, retry=GOOD)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo")
        self.assertTrue(retrolog._attempt_failed(self.rundir / "01/1"))  # 다시 검증 실패는 repair/failure.log에 있다
        text = retrolog.build(self.repo, "demo", st)
        self.assertIn("수리: 시도 1 커밋 1개 → 실패", text)
        self.assertIn("#### 수리 worker repair (실패)", text)
        self.assertIn("rereview-repair-codex", text)
        keys = [retrolog._sub_key(Path(name)) for name in ("review", "fix", "rereview1-codex", "fix2", "repair", "rereview-repair-codex")]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
