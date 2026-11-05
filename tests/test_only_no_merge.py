"""goldstack-v10 03: `gs go --only`는 integration까지만 하고 병합하지 않는다. 병합은 옵션 없는 `gs go`만 한다.

이 파일만 `support.ONLY_MERGES` 없이 돈다. 다른 시험의 `--only`는 그 변수로 마무리까지 간다.
"""
import contextlib
import io
import json
import os
from unittest import mock

import support
from gs import cli, config, git, go, state, transient
from support import sh
from test_squash import squash_gh

REPORT = ".goldstack/work/demo/report.md"
LINE = "■ --only 범위만 돌았다: 병합하지 않음 → 이어서 gs go demo"


class OnlyTest(support.GoTest):
    def setUp(self):
        super().setUp()
        os.environ.pop(support.ONLY_MERGES)

    def keep(self, *tids):
        """이 티켓만 남겨 커밋·push한다(가짜 worker가 실패시키는 티켓을 뺀다)."""
        tickets = self.repo / ".goldstack/work/demo/tickets"
        for path in tickets.glob("*.md"):
            if path.name.split("-")[0] not in tids:
                path.unlink()
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "keep")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def tip(self):
        return sh(self.remote, "git", "rev-parse", self.BASE)

    def finish_state(self):
        return state.load(self.rundir, "demo").finish

    def base_report(self):
        return sh(self.remote, "git", "show", f"{self.BASE}:{REPORT}")

    def assert_stopped(self, out, tip, gh=()):
        """멈춤의 공통 증거: 끝 줄, 원격 base 그대로, gs가 부른 gh 없음, 원격에 올린 gs 브랜치 없음."""
        self.assertEqual(out.strip().splitlines()[-1], LINE)
        self.assertEqual(self.tip(), tip)
        self.assertEqual(self.lines("gh.log"), list(gh))
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/demo/*"), "")

    def assert_no_report(self):
        self.assertFalse((self.rundir / "finish").exists())
        self.assertNotIn(REPORT, self.integration("ls-tree", "-r", "--name-only", "gs/demo/integration").split())
        self.assertFalse((self.repo / REPORT).exists())
        self.assertEqual(self.finish_state(), {})

    def assert_reads_unmerged(self, out):
        summary = [line for line in out.splitlines() if line.startswith("■ ")]
        self.assertIn("■ 마무리: 병합하지 않음(--only)", summary)
        self.assertIn("■ PR: 만들지 않음", summary)
        self.assertTrue(any(line.startswith("■ 보고서: 쓰지 않음") for line in summary), out)
        self.assertNotIn("병합 완료", out)
        self.assertNotIn("■ 요약: 병합", out)
        self.assertNotIn("■ 요약: 이미 병합", out)

    # --- 일부 범위 ---
    def test_partial_range_merges_to_integration_only(self):
        tip = self.tip()
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04"])
        self.assertEqual(self.merged(), ["01", "04"])
        self.assertIn("■ 요약: integration 병합 2", out)
        self.assert_stopped(out, tip)
        self.assert_no_report()
        self.assert_reads_unmerged(out)
        # 병합·검증은 했다
        self.assertIn("[01] 검증 통과 → integration 병합", out)
        self.assertIn("[04] 검증 통과 → integration 병합", out)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_04"), "04 worker")

    # --- 전체 범위 ---
    def test_full_range_stops_too(self):
        self.keep("01", "04")
        tip = self.tip()
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01", "04"])
        self.assert_stopped(out, tip)
        self.assert_no_report()
        self.assert_reads_unmerged(out)

    # --- 실패한 티켓이 있는 범위의 종료 코드 ---
    def test_failed_ticket_in_range_exits_1_without_merging(self):
        tip = self.tip()
        code, out, err = self.go("--only", "01,02")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), ["01", "02", "02"])  # 실패는 한 번 재시도한다
        self.assertEqual(self.merged(), ["01"])
        tickets = state.load(self.rundir, "demo").tickets
        self.assertEqual((tickets["01"].status, tickets["02"].status), (state.MERGED, state.FAILED))
        self.assertIn("■ 요약: integration 병합 1, 실패 1", out)
        self.assert_stopped(out, tip)
        self.assert_no_report()
        self.assert_reads_unmerged(out)

    def test_nothing_merged_exits_1(self):
        tip = self.tip()
        code, out, err = self.go("--only", "02,03")
        self.assertEqual(code, 1, out + err)
        tickets = state.load(self.rundir, "demo").tickets
        self.assertEqual((tickets["02"].status, tickets["03"].status), (state.FAILED, state.SKIPPED))
        self.assertEqual(self.merged(), [])
        self.assert_stopped(out, tip)
        self.assert_no_report()

    def test_verify_failure_in_range_exits_1(self):
        tip = self.tip()
        code, out, err = self.go("--only", "05")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["05"].status, state.FAILED)
        self.assertEqual(self.merged(), [])
        self.assert_stopped(out, tip)

    # --- 이어서 치는 옵션 없는 gs go ---
    def test_plain_go_runs_the_rest_merges_and_reports_all_tickets(self):
        self.add_ticket("09")
        self.keep("01", "04", "09")
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04", "09"])  # merged 티켓을 다시 돌리지 않는다
        self.assertNotIn(LINE, out)
        self.assertIn("■ 요약: 병합 1, 이미 병합 2", out)
        self.assertIn("[01] 이미 병합됨", out)
        self.assertEqual(self.finish_state()["phase"], "verified")
        gh = "\n".join(self.lines("gh.log"))
        self.assertIn("pr create", gh)
        self.assertIn("pr merge", gh)
        self.assertLessEqual({"file_01", "file_04", "file_09"}, set(self.remote_files()))
        report = self.base_report()
        for tid in ("01", "04", "09"):
            self.assertIn(f"| {tid} | t{tid} | merged |", report)

    def test_plain_go_after_full_range_merges_without_workers(self):
        self.keep("01", "04")
        self.go("--only", "01,04")
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04"])
        self.assertIn("■ 요약: 이미 병합 2", out)
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertLessEqual({"file_01", "file_04"}, set(self.remote_files()))
        report = self.base_report()
        for tid in ("01", "04"):
            self.assertIn(f"| {tid} | t{tid} | merged |", report)

    # --- 병합 없는 재실행의 멱등성 ---
    def test_rerun_changes_nothing(self):
        tip = self.tip()
        self.go("--only", "01,04")
        head = self.integration("rev-parse", "gs/demo/integration")
        before = state.load(self.rundir, "demo")
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04"])
        self.assertEqual(self.integration("rev-parse", "gs/demo/integration"), head)
        self.assertIn("■ 요약: integration에 이미 병합 2", out)
        self.assert_stopped(out, tip)
        self.assert_no_report()
        self.assert_reads_unmerged(out)
        after = state.load(self.rundir, "demo")
        self.assertEqual({tid: (ts.status, ts.attempts) for tid, ts in after.tickets.items()},
                         {tid: (ts.status, ts.attempts) for tid, ts in before.tickets.items()})

    # --- 남은 마무리의 회복은 그대로다 ---
    def test_pending_finish_is_recovered_first_and_may_merge(self):
        self.keep("01", "04")
        (self.bin / "gh.queue").touch()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish_state()["phase"], "merge_pending")
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(LINE, out)
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertIn("integration·main 검증 통과, PR 병합 완료", out)
        self.assertIn("pr merge", "\n".join(self.lines("gh.log")))
        self.assertLessEqual({"file_01", "file_04"}, set(self.remote_files()))
        self.assertEqual(self.calls(), ["01", "04"])

    # --- 끝난 마무리 뒤의 --only ---
    def finished_then_only(self):
        """verified로 끝난 feature에 새 티켓을 더해 --only로 돌린다."""
        self.keep("01")
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.add_ticket("09")
        tip, gh = self.tip(), self.lines("gh.log")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_stopped(out, tip, gh)
        self.assert_reads_unmerged(out)  # 지난 verified의 "PR 병합 완료"를 이번 결과로 보이지 않는다
        self.assertNotIn("file_09", self.remote_files())
        self.assertEqual(self.finish_state()["phase"], "only_stopped")

    def test_after_finish_plain_go_merges_the_new_ticket(self):
        self.finished_then_only()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "09"])
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertIn("file_09", self.remote_files())
        report = self.base_report()
        for tid in ("01", "09"):
            self.assertIn(f"| {tid} | t{tid} | merged |", report)

    def clean(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            return cli.main(["--repo", str(self.repo), "clean", "demo", *extra]), err.getvalue()

    def test_after_finish_clean_needs_force_and_go_does_not_call_it_finished(self):
        self.finished_then_only()
        code, err = self.clean()
        self.assertEqual(code, 1, err)  # base에 없는 티켓이 integration에만 있다
        self.assertIn("only_stopped", err)
        self.assertEqual(self.merged(), ["01", "09"])
        code, err = self.clean("--force")
        self.assertEqual(code, 0, err)
        code, out, err = self.go()  # state는 09를 merged로 적고 있지만 base에는 없다. 끝났다고 멈추면 09를 잃는다
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("이미 끝남", out)
        self.assertEqual(self.calls(), ["01", "09", "09"])
        self.assertIn("file_09", self.remote_files())

    # --- 끝난 마무리 뒤의 병합과 중단 ---
    def finished_with_new_ticket(self):
        """verified로 끝난 feature에 새 티켓 09를 더한다. 지난 마무리 기록을 돌려준다."""
        self.keep("01")
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish_state()["phase"], "verified")
        before = self.finish_state()
        self.add_ticket("09")
        return before

    def die_after_merge(self, *args):
        """09의 merged를 저장한 바로 뒤에 죽는다. 이어지는 worktree 정리·마무리·_stop_only를 건너뛴다."""
        real = go._cleanup_merged

        def dying(r, tid):
            if tid == "09":
                raise KeyboardInterrupt
            real(r, tid)

        with mock.patch("gs.go._cleanup_merged", dying), self.assertRaises(KeyboardInterrupt):
            self.go(*args)

    def die_before_save(self, *args):
        """09의 integration 커밋 뒤, 무효화·merged를 메모리에 적기 전에 죽는다. 첫 실행의 _resume_merged는 이것을 부르지 않는다."""
        with mock.patch("gs.go._reopen_finished", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.go(*args)

    def assert_reopened(self, before):
        """완료 상태만 무효화했다: 다음 마무리가 읽는 기록(head 등)은 그대로고, --only로 멈췄다고 적지 않는다."""
        after = self.finish_state()
        self.assertEqual(after["phase"], "reopened")
        self.assertNotEqual(after["outcome"], go.ONLY_NOT_MERGED)
        self.assertTrue(after["head"])
        rest = {k: v for k, v in before.items() if k not in ("phase", "outcome")}
        self.assertEqual({k: v for k, v in after.items() if k not in ("phase", "outcome")}, rest)

    def assert_only_stopped(self, out, tip, gh):
        """--only가 09를 다시 돌리지 않고 멈췄다. 그때만 --only로 멈췄다고 적는다."""
        self.assertEqual(self.calls(), ["01", "09"])
        self.assertIn("■ 요약: integration에 이미 병합 1", out)
        self.assert_stopped(out, tip, gh)
        self.assert_reads_unmerged(out)
        self.assertNotIn("file_09", self.remote_files())
        self.assertEqual(self.finish_state()["phase"], "only_stopped")
        self.assertEqual(self.finish_state()["outcome"], go.ONLY_NOT_MERGED)

    def assert_landed(self, out):
        """옵션 없는 gs go가 09를 다시 돌리지 않고 base까지 병합했다."""
        self.assertNotIn("이미 끝남", out)
        self.assertEqual(self.calls(), ["01", "09"])
        self.assertIn("file_09", self.remote_files())
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertIn("| 09 | t09 | merged |", self.base_report())

    @contextlib.contextmanager
    def saves(self):
        """state.json에 쓸 때마다 (finish phase, 09의 status)를 모은다."""
        seen, real = [], state.save

        def spy(rundir, st):
            real(rundir, st)
            seen.append((st.finish.get("phase"), st.tickets["09"].status if "09" in st.tickets else ""))

        with mock.patch("gs.state.save", spy):
            yield seen

    def first_merged_save(self, seen):
        return next(i for i, (_, status) in enumerate(seen) if status == state.MERGED)

    def assert_same_save(self, seen):
        """merged와 무효화가 한 번의 저장에 함께 들어갔다: 바로 앞 저장은 둘 다 전이다."""
        first = self.first_merged_save(seen)
        self.assertEqual(seen[first][0], "reopened")
        self.assertEqual(seen[first - 1][0], "verified")

    def test_only_merge_saves_merged_and_invalidation_together(self):
        self.finished_with_new_ticket()
        with self.saves() as seen:
            self.die_after_merge("--only", "09")
        self.assert_same_save(seen)

    def test_plain_merge_saves_merged_and_invalidation_together(self):
        self.finished_with_new_ticket()
        with self.saves() as seen:
            self.die_after_merge()
        self.assert_same_save(seen)

    def test_interrupted_after_merge_only_rerun_stops_then_plain_go_merges(self):
        before = self.finished_with_new_ticket()
        tip, gh = self.tip(), self.lines("gh.log")
        self.die_after_merge("--only", "09")
        self.assert_reopened(before)
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_only_stopped(out, tip, gh)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_landed(out)

    def test_interrupted_after_merge_plain_rerun_merges(self):
        before = self.finished_with_new_ticket()
        self.die_after_merge()
        self.assert_reopened(before)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_landed(out)

    def test_interrupted_plain_go_then_only_says_only_stopped(self):
        """옵션 없는 gs go가 넣어 두고 죽었어도 --only로 멈춘 실행은 그렇게 적는다."""
        self.finished_with_new_ticket()
        tip, gh = self.tip(), self.lines("gh.log")
        self.die_after_merge()
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_only_stopped(out, tip, gh)

    def test_interrupted_before_save_only_rerun_invalidates(self):
        before = self.finished_with_new_ticket()
        tip, gh = self.tip(), self.lines("gh.log")
        self.die_before_save("--only", "09")
        self.assertEqual(self.finish_state(), before)  # 아직 무효화 전이다: 표시만 있다
        self.assertEqual(state.load(self.rundir, "demo").tickets["09"].status, state.RUNNING)
        self.assertIn("09", self.merged())
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_only_stopped(out, tip, gh)
        code, err = self.clean()
        self.assertEqual(code, 1, err)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_landed(out)

    def test_interrupted_before_save_plain_rerun_merges(self):
        self.finished_with_new_ticket()
        self.die_before_save()
        with self.saves() as seen:
            code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(seen[self.first_merged_save(seen)][0], "reopened")  # 회복도 완료 상태로 merged를 저장하지 않는다
        self.assert_landed(out)

    def test_recovering_a_ticket_of_the_finished_scope_keeps_finished_phase(self):
        """끝난 범위 안의 티켓은 표시로 회복해도 무효화하지 않는다."""
        self.keep("01")
        self.assertEqual(self.go()[0], 0)
        st = state.load(self.rundir, "demo")
        before, gh = dict(st.finish), self.lines("gh.log")
        st.tickets["01"].status = state.RUNNING  # 범위 안 티켓을 잃은 state
        state.save(self.rundir, st)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertEqual(self.finish_state()["url"], before["url"])
        self.assertNotIn("pr create", "\n".join(self.lines("gh.log")[len(gh):]))

    def test_clean_before_recovery_only_costs_a_rerun(self):
        """저장 전에 죽었으면 state가 아직 모른다: clean이 --force 없이 지워도 09가 merged가 아니니 gs go가 다시 돌려 base까지 간다."""
        self.finished_with_new_ticket()
        self.die_before_save("--only", "09")
        code, err = self.clean()
        self.assertEqual(code, 0, err)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("이미 끝남", out)
        self.assertEqual(self.calls(), ["01", "09", "09"])
        self.assertIn("file_09", self.remote_files())
        self.assertEqual(self.finish_state()["phase"], "verified")

    # --- squash: 범위 안 티켓의 병합 커밋이 base에 없다 ---
    def use_squash(self):
        (self.bin / "gh").write_text("#!/bin/bash\n" + squash_gh())
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('merge_method = "merge"', 'merge_method = "squash"'))
        sh(self.repo, "git", "commit", "-qam", "squash only")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def test_squash_keeps_finished_phase_for_its_own_tickets(self):
        self.use_squash()
        self.keep("01")
        self.assertEqual(self.go()[0], 0)
        st = state.load(self.rundir, "demo")
        before, gh = dict(st.finish), self.lines("gh.log")
        self.assertEqual((before["phase"], before["merge_method"]), ("verified", "squash"))
        st.tickets["01"].status = state.RUNNING
        state.save(self.rundir, st)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assertNotIn("pr create", "\n".join(self.lines("gh.log")[len(gh):]))

    def test_squash_interrupted_before_save_merges_the_new_ticket(self):
        self.use_squash()
        self.finished_with_new_ticket()
        self.die_before_save("--only", "09")
        tip, gh = self.tip(), self.lines("gh.log")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_only_stopped(out, tip, gh)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_landed(out)

    def test_interrupted_after_merge_clean_refuses_and_go_does_not_call_it_finished(self):
        self.finished_with_new_ticket()
        self.die_after_merge("--only", "09")
        code, err = self.clean()
        self.assertEqual(code, 1, err)
        self.assertIn("reopened", err)
        self.assertTrue((self.rundir / "wt/integration").exists())
        self.assertIn("09", self.merged())  # 미병합 변경이 그대로 있다
        code, err = self.clean("--force")
        self.assertEqual(code, 0, err)
        code, out, err = self.go()  # state는 09를 merged로 적고 있지만 base에는 없다. 끝났다고 멈추면 09를 잃는다
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("이미 끝남", out)
        self.assertEqual(self.calls(), ["01", "09", "09"])
        self.assertIn("file_09", self.remote_files())

    def test_reverted_phase_is_invalidated_too(self):
        self.keep("01")
        self.break_main()
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        before = self.finish_state()
        self.assertEqual(before["phase"], "reverted")
        self.add_ticket("09")
        self.die_after_merge("--only", "09")
        self.assert_reopened(before)
        code, err = self.clean()
        self.assertEqual(code, 1, err)
        self.assertIn("reopened", err)

    def test_finished_run_without_new_ticket_stays_finished(self):
        self.keep("01")
        self.assertEqual(self.go()[0], 0)
        before, gh = self.finish_state(), self.lines("gh.log")
        for args in ((), ("--only", "01")):
            with self.subTest(args=args):
                code, out, err = self.go(*args)
                self.assertEqual(code, 0, out + err)
                self.assertIn("■ 이미 끝남: demo (verified)", out)
                self.assertEqual(self.finish_state(), before)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(self.lines("gh.log"), gh)
        code, err = self.clean()
        self.assertEqual(code, 0, err)

    def old_state_after_merge(self, *args):
        """이 변경 전의 gs가 남긴 state: 끝난 마무리인 채로 09만 merged다."""
        before = self.finished_with_new_ticket()
        self.die_after_merge(*args)
        st = state.load(self.rundir, "demo")
        st.finish = dict(before)
        state.save(self.rundir, st)
        self.assertEqual(st.tickets["09"].status, state.MERGED)
        return before

    def test_old_state_with_merged_ticket_only_rerun_invalidates(self):
        self.old_state_after_merge("--only", "09")
        tip, gh = self.tip(), self.lines("gh.log")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assert_only_stopped(out, tip, gh)
        code, err = self.clean()
        self.assertEqual(code, 1, err)

    def test_old_state_with_merged_ticket_plain_rerun_merges(self):
        self.old_state_after_merge()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_landed(out)

    def test_failed_ticket_after_finish_keeps_finished_phase(self):
        """새로 들어간 티켓이 없으면 끝난 마무리는 그대로 끝난 것이다."""
        self.keep("01")
        self.go()
        self.add_ticket("02")  # 가짜 worker는 02를 늘 실패시킨다
        tip = self.tip()
        code, out, err = self.go("--only", "02")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.tip(), tip)
        self.assertEqual(self.finish_state()["phase"], "verified")
        self.assert_reads_unmerged(out)

    # --- 루프가 도중에 끝난 --only ---
    def test_git_error_does_not_read_as_merged(self):
        self.keep("01")
        self.go()
        self.add_ticket("09")
        with mock.patch("gs.go._loop", side_effect=git.GitError("boom")):
            code, out, err = self.go("--only", "09")
        self.assertEqual(code, 1, out + err)
        self.assertIn("git 오류: boom", err)
        self.assertEqual(out.strip().splitlines()[-1], LINE)
        self.assert_reads_unmerged(out)
        self.assertEqual(self.finish_state()["phase"], "verified")

    def test_network_abort_keeps_its_exit_code_and_line(self):
        tip = self.tip()
        with mock.patch("gs.go._loop", side_effect=transient.NetworkAbort("끊김")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertIn("■ 마무리: 중단(네트워크)", out)
        self.assertIn("■ PR: 만들지 않음", out)
        self.assertNotIn(LINE, out)
        self.assertEqual(self.tip(), tip)

    # --- integration 준비가 실패한 --only ---
    def integration_setup(self, command):
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('setup = ""', "setup = " + json.dumps(command)))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "integration setup")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def test_setup_failure_on_first_run_writes_no_report(self):
        self.integration_setup("echo integration-boom; exit 8")
        tip = self.tip()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), [])
        self.assert_stopped(out, tip)
        self.assert_no_report()
        self.assertFalse((self.rundir / "wt/integration" / REPORT).exists())
        self.assert_reads_unmerged(out)
        self.assertIn("integration 준비 실패", out)
        self.assertIn("integration-boom", (self.rundir / "integration/1/setup.log").read_text())

    def test_setup_failure_after_finish_does_not_read_as_merged(self):
        blocked = self.bin / "setup-blocked"
        self.keep("01")
        self.assertEqual(self.go()[0], 0)
        self.add_ticket("09")
        self.integration_setup(f"test ! -f {blocked} || exit 8")
        blocked.touch()
        tip, gh, before = self.tip(), self.lines("gh.log"), self.finish_state()
        self.assertEqual(before["phase"], "verified")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assert_stopped(out, tip, gh)
        self.assert_reads_unmerged(out)  # 지난 verified의 "PR 병합 완료"를 이번 결과로 보이지 않는다
        self.assertEqual(self.finish_state(), before)
        self.assertEqual(sh(self.rundir / "wt/integration", "git", "status", "--porcelain"), "")  # 보고서를 쓰지 않았다
        # 준비를 고치면 옵션 없는 gs go가 그 티켓까지 병합한다
        blocked.unlink()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "09"])
        self.assertIn("file_09", self.remote_files())

    def test_git_error_while_preparing_does_not_read_as_merged(self):
        self.keep("01")
        self.go()
        self.add_ticket("09")
        with mock.patch("gs.finish.merge_base", side_effect=git.GitError("boom")):
            code, out, err = self.go("--only", "09")
        self.assertEqual(code, 1, out + err)
        self.assertIn("git 오류: boom", err)
        self.assertEqual(out.strip().splitlines()[-1], LINE)
        self.assert_reads_unmerged(out)
        self.assertEqual(self.finish_state()["phase"], "verified")

    def test_setup_failure_while_recovering_keeps_the_old_path(self):
        """남은 마무리를 회복하는 --only는 준비가 실패해도 지금처럼 보고서를 쓰고 그 마무리를 보인다."""
        blocked = self.bin / "setup-blocked"
        self.keep("01", "04")
        self.integration_setup(f"test ! -f {blocked} || exit 8")
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go()[0], 1)
        before = self.finish_state()
        self.assertEqual(before["phase"], "merge_pending")
        wt = self.rundir / "wt/integration"
        sh(self.repo, "git", "worktree", "remove", "--force", str(wt))
        blocked.touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertNotIn(LINE, out)
        self.assertEqual(self.finish_state(), before)
        self.assertIn(f"■ 마무리: {before['outcome']}", out)
        self.assertIn(f"■ 보고서: {REPORT.rsplit('/', 1)[0]}/report.md", out)
        self.assertIn("integration 준비 실패", (wt / REPORT).read_text())

    # --- 텔레그램 ---
    def enable_telegram(self):
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        cfg = self.repo / config.CONFIG_PATH
        cfg.write_text(cfg.read_text().replace("telegram = false", "telegram = true"))
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n.goldstack/local.env\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "notify on")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=t\nTG_CHAT_ID=42\n")

    def telegram(self, *args):
        with mock.patch("gs.notify.send", return_value=(True, "")) as send:
            code, out, err = self.go(*args)
        send.assert_called_once()
        return code, send.call_args.args[2], out + err

    def test_telegram_success_does_not_read_as_merged(self):
        self.enable_telegram()
        code, text, output = self.telegram("--only", "01")
        self.assertEqual(code, 0, output)
        self.assertEqual(text, "⏸ demo · 병합하지 않음(--only)\n티켓 1/1 integration 병합 · 0분 · 남은 지적 0\n이어서 gs go demo")

    def test_telegram_failure_does_not_read_as_merged(self):
        self.enable_telegram()
        code, text, output = self.telegram("--only", "01,02")
        self.assertEqual(code, 1, output)
        self.assertEqual(text, "❌ demo · 병합하지 않음(--only) · 티켓 1/2 (02 실패: worker 종료 코드 1) · 이어서 gs go demo")

    def test_telegram_setup_failure_after_finish_does_not_read_as_merged(self):
        self.keep("01")
        self.enable_telegram()
        self.assertEqual(self.telegram()[0], 0)
        self.add_ticket("09")
        self.integration_setup("exit 8")
        code, text, output = self.telegram("--only", "09")
        self.assertEqual(code, 1, output)
        self.assertEqual(text, "❌ demo · 병합하지 않음(--only) · 티켓 0/1 · 이어서 gs go demo")

    # --- 도움말 ---
    def test_help_says_it_does_not_merge(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stop:
            cli.main(["go", "--help"])
        self.assertEqual(stop.exception.code, 0)
        self.assertIn("병합하지 않는다", " ".join(out.getvalue().split()))  # argparse가 줄을 나눈다


class OnlyMergesVariableTest(support.GoTest):
    def test_the_variable_keeps_the_old_flow_for_other_tests(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(LINE, out)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertIn("file_01", self.remote_files())
