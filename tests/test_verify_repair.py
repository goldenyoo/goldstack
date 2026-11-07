"""goldstack-v12 02: 티켓 검증 실패를 새 시도 대신 같은 브랜치·worktree에서 수리한다.

가짜 worker는 brief로 수리 worker를 알아본다(`## 검증 실패(고칠 것)`). 수리 뒤 통과, 커밋 없는 재검증, 수리 뒤 실패의 새 시도,
수리 중 재개(gs가 죽음, 네트워크), 수리하지 않는 실패, agy 상한, 옛 state를 끝까지 돌려 본다. 시간에 기대지 않고 파일 신호로 순서를 잡는다.
"""
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

import support
import test_network_wait
from support import alive, kill_quietly, sh

from gs import config, go, report, retrolog, review, state, transient, worker

IS_REPAIR = 'grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"'
BREAKS = 'touch BROKEN; echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"'
GOOD = 'echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"'
REPAIRS = 'git rm -q BROKEN; git commit -qm "repair $GS_TICKET"'
USELESS = 'echo tried >> "repair_$GS_TICKET"; git add -A; git commit -qm "useless $GS_TICKET"'
AFTER_HANG = 'rm -f "$here/hung"; ' + GOOD  # times_out_once_ready는 hung이 있는 동안 도는 명령을 시간 초과로 본다. 멈춘 검증 뒤에는 치운다


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

    def test_no_commit_reverifies_at_once_without_review(self):
        self.flaky_verify()
        self.worker(GOOD, 'echo "불안정한 시험이다"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.reviewers(), ["codex"])  # 첫 리뷰뿐이다
        self.assertEqual(self.phases(), ["worker", "review", "verify", "repair", "verify", "finish"])
        self.assertNotIn("rereviews", ts.review)
        self.assertIn("수리: 시도 1 커밋 없음 → 다시 검증 통과", self.status("demo")[1])
        self.assertIn("재리뷰 없이 바로 다시 검증한다", out)
        self.assertTrue((self.rundir / "01/1/repair/verify.log").exists())

    def test_failed_repair_is_discarded_and_verified_without_review(self):
        self.flaky_verify()
        self.worker(GOOD, 'echo bad > bad_fix; git add -A; git commit -qm "bad fix"; exit 3')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(self.reviewers(), ["codex"])
        self.assertNotIn("bad_fix", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertIn("시도 1 수리 worker 실패(종료 코드 3), 수리 버림 → 다시 검증 통과", state.repair_summary(ts))

    def test_repair_that_rewrites_earlier_commits_is_discarded(self):
        self.flaky_verify()
        self.worker(GOOD, 'git reset -q --hard HEAD~1; echo other > other; git add -A; git commit -qm "rewrote"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.reviewers(), ["codex"])
        names = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", names)
        self.assertNotIn("other", names)
        self.assertIn("이전 커밋을 지웠다", state.repair_summary(self.ts()))

    def test_verify_left_files_is_a_failure_to_repair(self):
        # 검증은 통과했지만 파일을 남겼다: 통과를 믿을 수 없는 검증 실패다
        (self.bin / "verify.sh").write_text(f'[ -f "{self.bin}/verified" ] && exit 0\ntouch "{self.bin}/verified" junk\n')
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")
        self.worker(GOOD, 'echo "고칠 것이 없다"')
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

    def stop_at_second_verify(self):
        real, seen = go._verify, []

        def stopping(r, t):
            seen.append(t.id)
            if len(seen) == 2:
                raise KeyboardInterrupt
            return real(r, t)

        with mock.patch("gs.go._verify", side_effect=stopping), self.assertRaises(KeyboardInterrupt):
            self.go("--only", "01")

    def test_stopped_during_verify_after_a_repair_commit(self):
        self.worker(BREAKS, REPAIRS)
        self.stop_at_second_verify()
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
        self.stop_at_second_verify()
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
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertIn("수리 worker를 다시 띄우지 못했다: agy 한도", out)
        self.assertEqual(self.calls(), ["01", "01"])
        self.assertNotIn("bad_fix", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertIn("수리 worker 실패", ts.repairs[0]["worker"])
        self.assertIn("수리 버림", ts.repairs[0]["worker"])


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
        self.assertIn("커밋이 없어도 실패가 아니다", brief)
        self.assertIn("처음부터 다시 하지 말고", brief)


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
