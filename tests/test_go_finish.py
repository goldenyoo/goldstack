"""`gs go`의 마무리 병합·되돌리기·정리 시나리오."""
import os
import unittest
from unittest import mock

from gs import state
import support
from support import FAKE_WORKER, git_clean, sh, ticket


class GoFinishTest(support.GoTest):
    def test_merged_ticket_is_cleaned_before_next_worker(self):
        (self.bin / "worker.sh").write_text(FAKE_WORKER + '''
if [ "$GS_TICKET" = 04 ]; then
  test ! -d "$GS_WORKTREE/../01" || exit 9
  test -z "$(git branch --list gs/demo/01)" || exit 10
fi
''')
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        for tid in ("01", "04"):
            self.assert_ticket_cleaned(tid)
            self.assertIn(f"[{tid}] worktree 정리: {self.rundir / 'wt' / tid}", out)
        self.assertFalse((self.rundir / "wt/integration").exists())
        self.assertEqual(self.integration("branch", "--list", "gs/demo/integration"), "")
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/demo/integration"), "")

    def test_dirty_merged_ticket_is_kept_and_reported_until_clean(self):
        (self.bin / "worker.sh").write_text(FAKE_WORKER + '\necho unfinished > pending.txt\n')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = self.rundir / "wt/01"
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.kept_worktrees), ("merged", [str(wt)]))
        self.assertTrue((wt / "pending.txt").exists())
        self.assertIn("gs/demo/01", self.integration("branch", "--list", "gs/demo/01"))
        self.assertIn(f"남긴 worktree: {wt} (미커밋 변경)", self.final_report())
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [str(wt)])
        self.assertEqual(self.calls(), ["01"])
        (wt / "pending.txt").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [])

    def test_resume_cleans_after_merge_before_cleanup(self):
        with mock.patch("gs.go._cleanup_merged", side_effect=RuntimeError("gs interrupted")):
            with self.assertRaisesRegex(RuntimeError, "gs interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertTrue((self.rundir / "wt/01").exists())
        # 이번 --only 범위 밖에 있는 merged 티켓도 시작할 때 회수한다.
        self.add_ticket("11")
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertIn("[01] worktree 정리:", out)
        self.assertEqual(self.calls(), ["01", "11"])

    def test_resume_cleans_merge_not_yet_saved_in_state(self):
        from gs.go import _set as real_set

        def interrupted(r, tid, **fields):
            if fields.get("status") == state.MERGED:
                raise RuntimeError("gs interrupted before state save")
            return real_set(r, tid, **fields)

        with mock.patch("gs.go._set", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "running")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertEqual(self.calls(), ["01"])

    def test_cleanup_keeps_branch_with_unmerged_tip(self):
        with mock.patch("gs.go._cleanup_merged"):
            self.assertEqual(self.go("--only", "01")[0], 0)
        wt = self.rundir / "wt/01"
        (wt / "extra").write_text("unmerged")
        sh(wt, "git", "add", "extra")
        sh(wt, "git", "commit", "-qm", "unmerged tip")
        tip = sh(wt, "git", "rev-parse", "HEAD")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("브랜치 끝이 integration에 포함되지 않아 남긴다: gs/demo/01", out)
        self.assertFalse(wt.exists())
        self.assertEqual(self.integration("rev-parse", "gs/demo/01"), tip)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")

    def test_worktree_cleanup_failure_only_warns_and_resumes(self):
        self.cleanup_failure("worktree")

    def test_branch_cleanup_failure_only_warns_and_resumes(self):
        self.cleanup_failure("branch")

    def test_finish_merges_and_verifies_main_in_temporary_worktree(self):
        initial = self.integration("rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertTrue(f["integration_ok"] and f["main_ok"])
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(self.integration("rev-parse", "main"), initial)  # 호출 worktree는 움직이지 않는다
        self.assertEqual(len(self.integration("rev-list", "--parents", "-n", "1", f["merge_sha"]).split()), 3)
        self.assertEqual(self.integration("show", "origin/main:file_01"), "01 worker")
        report = self.final_report()
        for text in ("## Summary", "## Evidence", "## Merge Danger", "| 01 | t01 | merged |",
                     "main-verify.log", "main: 통과 · 종료 코드 0",'git -C "$dir" revert', "mktemp -d", f["merge_sha"]):
            self.assertIn(text, report)
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), report)
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])
        self.assertNotIn("gs-main-", self.integration("worktree", "list"))
        self.assertEqual(len(out.strip().splitlines()[-4:]), 4)
        self.assertTrue(out.strip().splitlines()[-4].startswith("■ 요약:"))
        self.assertIn("-p --model opus", (self.bin / "judge.calls").read_text())
        self.assertIn("report-input.md", (self.bin / "judge.input").read_text())
        self.assertNotIn("01 worker", (self.bin / "judge.input").read_text())
        merges = self.lines("gh.log").count(next(x for x in self.lines("gh.log") if x.startswith("pr merge ")))
        self.assertEqual(self.go("--only", "01")[0], 0)  # 결과 보고서만 새 PR로 병합하지 않는다
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), merges)

    def test_finish_main_failure_pushes_revert_and_records_it(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertTrue(f["integration_ok"])
        self.assertFalse(f["main_ok"])
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        self.assertIn(f["revert_sha"], self.final_report())
        self.assertIn("종료 코드: 1", self.final_report())
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())
        self.assertIn("revert", out)
        self.assertEqual(self.go("--only", "01")[0], 1)  # 같은 병합을 두 번 revert하지 않는다
        self.assertEqual(self.under_report(), f["revert_sha"])

    def test_finish_no_merged_ticket_keeps_report_pr_without_merging(self):
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "02,03")
        self.assertEqual(code, 1, out + err)
        self.assertFalse(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        self.assertIn("merged 티켓 없음", self.final_report())
        self.assertRegex(self.final_report(), r"\| 02 \| t02 \| failed \| worker 종료 코드 1(?:<br>| \|)")
        self.assertIn("| 03 | t03 | skipped | 막힘: 02 |", self.final_report())
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())

    def test_finish_skips_verify_when_only_report_changed(self):
        self.parallel(1, verify='test ! -f .goldstack/work/demo/report.md || test "${PWD##*/}" = base')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertTrue(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertIn("integration-final: 보고서만 바뀜, 건너뜀", self.final_report())
        self.assertIn("integration-final-verify.log", self.final_report())

    def test_finish_merge_queue_is_not_success_and_resume_rechecks_pr(self):
        (self.bin / "gh.queue").touch()
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        log = self.lines("gh.log")
        ix = next(i for i, line in enumerate(log) if line.startswith("pr merge "))
        self.assertTrue(log[ix + 1].startswith("pr view "))
        self.assertFalse((self.rundir / "finish/main-verify.log").exists())
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])

    def test_finish_resumes_after_merge_before_main_verify(self):
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)
        self.assertEqual(self.calls(), ["01"])

    def test_finish_checks_actual_merge_even_if_command_returns_error(self):
        (self.bin / "gh.badexit").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertTrue((self.rundir / "finish/main-verify.log").exists())

    def test_finish_resumes_revert_push_without_another_revert(self):
        from gs import git
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        real_run = git.run

        def run(cwd, *args, **kw):
            if args == ("push", "origin", "HEAD:refs/heads/main"):
                raise git.GitError("push interrupted")
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=run):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "main_failed")
        revert = f["revert_sha"]
        self.assertNotEqual(sh(self.remote, "git", "rev-parse", "main"), revert)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.under_report(), revert)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "reverted")

    def test_finish_updates_existing_open_pr(self):
        for _ in range(2):
            code, out, err = self.go("--only", "06")
            self.assertEqual(code, 1, out + err)
        self.assertEqual(sum(x.startswith("pr create ") for x in self.lines("gh.log")), 1)
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())

    def test_finish_rebuilds_rejected_revert_on_latest_main(self):  # high: 거부된 revert push가 영구히 막힘
        self.break_main(advance=True)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "main_failed")
        stale, moved = f["revert_sha"], sh(self.remote, "git", "rev-parse", "main")
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", "main"), "someone else")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", f)
        self.assertNotEqual(f["revert_sha"], stale)
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), moved)  # force 없이 최신 main 위에
        self.assertNotIn("file_01", self.remote_files())
        self.assertIn("other.txt", self.remote_files())
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)

    def test_finish_records_revert_already_done_by_someone(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = state.load(self.rundir, "demo").finish
        theirs = self.someone(f"git revert --no-edit -m 1 {f['merge_sha']}")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", f)
        self.assertEqual(f["revert_sha"], theirs)
        self.assertEqual(self.under_report(), theirs)  # gs는 다시 revert하지 않는다(보고서 커밋만 위에)
        self.assertIn("이미", f["outcome"])

    def test_finish_moves_on_when_someone_fixed_main(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        fixed = self.someone("git rm -q file_01", "git commit -qm 'fix main'")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified", f)
        self.assertTrue(f["main_ok"])
        self.assertNotIn("revert_sha", f)
        self.assertEqual(self.under_report(), fixed)

    def test_finish_revert_keeps_feature_code_in_integration(self):  # medium: revert 뒤 integration에서 코드가 사라짐
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        [again] = f["reintroduced"]
        self.assertEqual(again["revert"], f["revert_sha"])
        self.assertIn(f"This reverts commit {f['revert_sha']}",
                      self.integration("log", "-1", "--format=%B", again["commit"]))
        self.assertIn(again["commit"], self.final_report())
        self.assertEqual(self.go("--only", "01")[0], 1)  # 다시 돌아도 코드가 남고 revert의 revert를 또 만들지 않는다
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        self.assertEqual(len(state.load(self.rundir, "demo").finish["reintroduced"]), 1)

    def test_prepare_keeps_feature_code_after_main_reverted(self):  # medium: 일반 준비 경로도 같은 방식으로 잃지 않는다
        self.assertEqual(self.go("--only", "01")[0], 0)
        merge = state.load(self.rundir, "demo").finish["merge_sha"]
        # 위에 gs의 최종 보고서 커밋이 있어 report.md가 충돌한다. 보고서의 되돌리는 법대로 지금 보고서를 남긴다.
        self.assertIn("revert --continue --no-edit", self.final_report())
        self.someone(f"! git revert --no-edit -m 1 {merge}",
                     "git checkout HEAD -- .goldstack/work/demo/report.md", "git revert --continue --no-edit")
        self.assertNotIn("file_01", self.remote_files())
        self.add_ticket("09")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        self.assertIn("file_01", self.remote_files())  # 다음 PR이 feature 코드를 다시 들였다
        self.assertIn("file_09", self.remote_files())
        self.assertIn("되돌렸", self.final_report())

    def test_finish_closed_pr_is_recorded_and_next_go_opens_new_pr(self):  # medium: 닫힌 PR에 영구히 갇힘
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        (self.bin / "gh.queue").unlink()
        (self.bin / "gh.open").unlink()
        (self.bin / "gh.closed").touch()  # 사람이 PR을 닫았다
        merges = sum(x.startswith("pr merge ") for x in self.lines("gh.log"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "closed", f)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), merges)
        self.assertIn("닫혔다", self.final_report())
        self.assertIn("닫혔다", out)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(sum(x.startswith("pr create ") for x in self.lines("gh.log")), 2)
        self.assertIn("file_01", self.remote_files())
        self.assertIn("닫혔다", self.final_report())  # 이전 PR이 닫혔다는 기록을 새 PR에도 남긴다
        self.assertEqual(self.calls(), ["01"])

    def test_report_body_stays_below_github_limit(self):  # medium: 본문 길이 초과로 마무리가 반복 실패
        self.parallel(1, verify="head -c 100000 /dev/zero | tr '\\0' x; echo; echo LAST-LINE; test ! -f BROKEN")
        old = self.rundir / "01" / "1" / "verify.log"
        old.parent.mkdir(parents=True)
        old.write_text("OLD-ATTEMPT\n" + "y" * 100000)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        body = (self.bin / "pr-body.md").read_text()
        self.assertLess(len(body), 65536)
        self.assertEqual(body.strip(), self.final_report())
        self.assertNotIn("OLD-ATTEMPT", body)  # 지난 시도 로그는 붙이지 않는다
        self.assertIn("LAST-LINE", body)  # 로그의 끝을 남긴다
        self.assertIn(str((self.rundir / "finish" / "main-verify.log").resolve()), body)  # 전체 로그 경로

    def test_integration_verify_timeout_does_not_merge(self):
        self.hang_verify("integration")
        initial = sh(self.remote, "git", "rev-parse", "main")
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}), support.times_out_once_ready(self.bin / "hung"):  # 멈춘 verify만 시간 초과
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual((f["phase"], f["integration_ok"]), ("not_merged", False))
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertFalse(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        log = (self.rundir / "finish/integration-verify.log").read_text()
        self.assertTrue(log.startswith(f"$ bash {self.bin / 'verify.sh'}\nHEAD: "), log)
        self.assertRegex(log, r"\n시간 초과: 0\.02분\n\n종료 코드: -?\d+\n\Z")
        self.assertFalse((self.rundir / "finish/integration-final-verify.log").exists())
        self.assertTrue(git_clean(self.rundir / "wt/integration"))
        self.assert_children_dead()

    def test_main_verify_timeout_reverts_merge(self):
        self.hang_verify("main")
        initial = sh(self.remote, "git", "rev-parse", "main")
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}), support.times_out_once_ready(self.bin / "hung"):  # 멈춘 verify만 시간 초과
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertTrue(f["integration_ok"])
        self.assertFalse(f["main_ok"])
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        log = (self.rundir / "finish/main-verify.log").read_text()
        self.assertRegex(log, r"\n시간 초과: 0\.02분\n\n종료 코드: -?\d+\n\Z")
        self.assertIn("시간 초과: 0.02분", self.final_report())
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])
        self.assert_children_dead()


class TrunkUpstreamTest(unittest.TestCase):
    """git.base·git.remote가 main·origin이 아닌 레포. origin 원격도 main 브랜치도 없으니 남은 가정은 바로 실패한다."""
    BASE, REMOTE = "trunk", "upstream"
    setUp, tearDown, go = support.GoTest.setUp, support.GoTest.tearDown, support.GoTest.go
    rundir, integration, parallel, lines, final_report = (support.GoTest.rundir, support.GoTest.integration, support.GoTest.parallel,
                                                          support.GoTest.lines, support.GoTest.final_report)
    under_report = support.GoTest.under_report

    def test_go_merges_and_verifies_on_configured_base_and_remote(self):
        initial = sh(self.remote, "git", "rev-parse", "trunk")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertTrue(f["integration_ok"] and f["main_ok"])
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['merge_sha']}^1"), initial)
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "main"), "")
        self.assertEqual(self.integration("remote"), "upstream")
        self.assertEqual(self.integration("show", "upstream/trunk:file_01"), "01 worker")
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/*"), "")
        gh = self.lines("gh.log")
        self.assertTrue(any(x.startswith("pr create --base trunk ") for x in gh), gh)
        self.assertTrue(any(x.startswith("pr list ") and "--base trunk" in x for x in gh), gh)
        report = self.final_report()
        for text in ("git fetch upstream trunk", 'git worktree add --detach "$dir" upstream/trunk',
                     'git -C "$dir" push upstream HEAD:refs/heads/trunk', "trunk verify: True"):
            self.assertIn(text, report)
        self.assertNotIn("origin", report)
        self.assertEqual(self.go("--only", "01")[0], 0)  # 재실행도 trunk·upstream으로 끝난다

    def test_base_failure_reverts_on_configured_base(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        initial = sh(self.remote, "git", "rev-parse", "trunk")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", out + err)
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        self.assertIn("trunk에 push함", f["outcome"])

    def test_require_committed_compares_with_configured_base(self):
        (self.repo / ".goldstack/work/demo/tickets/01-t.md").write_text(ticket("01") + "more\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1)
        self.assertIn(".goldstack/work/demo가 upstream/trunk와 다르다", err)


if __name__ == "__main__":
    unittest.main()
