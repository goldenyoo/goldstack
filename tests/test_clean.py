"""실제 worktree·로컬 bare 원격으로 정리, 잠금, 재개를 검증한다."""
import contextlib
import io
import shutil
import unittest
from pathlib import Path
from unittest import mock

import support
from gs import cli, git, state
from support import sh


class CleanTest(unittest.TestCase):
    BASE, REMOTE = "trunk", "upstream"
    G = support.GoTest
    setUp, tearDown, go, rundir, parallel = G.setUp, G.tearDown, G.go, G.rundir, G.parallel

    def clean(self, *args, repo=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo if repo is None else repo), "clean", "demo", *args])
        return code, out.getvalue(), err.getvalue()

    def prepare(self, phase="verified"):
        st = state.State(feature="demo", finish={"phase": phase})
        state.save(self.rundir, st)
        log = self.rundir / "01/attempt-1/worker.log"
        log.parent.mkdir(parents=True)
        log.write_text("keep this evidence\n")
        for name in ("integration", "01", "01-retry-2"):
            wt = self.rundir / "wt" / name
            branch = f"gs/demo/{name}"
            git.ensure_worktree(self.repo, wt, branch, "HEAD")
            (wt / "uncommitted.txt").write_text("discard\n")
            sh(self.repo, "git", "push", "-q", self.REMOTE, branch)
        # tracking ref가 없는 원격 브랜치도 찾는다. 다른 feature와 비슷한 prefix는 보존한다.
        sh(self.remote, "git", "branch", "gs/demo/remote-only", self.BASE)
        for branch in ("gs/demo-other/01", "gs/demo2/integration"):
            sh(self.repo, "git", "branch", branch)
            sh(self.repo, "git", "push", "-q", self.REMOTE, branch)
        return log

    def assert_integration_removed(self):
        self.assertFalse((self.rundir / "wt/integration").exists())
        self.assertFalse(git.branch_exists(self.repo, "gs/demo/integration"))
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/demo/integration"), "")

    def test_clean_removes_dirty_worktrees_and_all_feature_branches_keeps_records(self):
        log = self.prepare()
        recorded = (self.rundir / "state.json").read_bytes()
        # 이미 디렉터리가 사라진 등록도 정리한다.
        gone = self.rundir / "wt/02"
        git.ensure_worktree(self.repo, gone, "gs/demo/02", "HEAD")
        shutil.rmtree(gone)
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertIn("지움: worktree 4, 로컬 브랜치 4, 원격 브랜치 4 · 실행 기록은 남김", out)
        for name in ("integration", "01", "01-retry-2", "02"):
            self.assertIn(str(self.rundir / "wt" / name), out)
        self.assertEqual(list((self.rundir / "wt").iterdir()), [])
        self.assertEqual((self.rundir / "state.json").read_bytes(), recorded)
        self.assertEqual(log.read_text(), "keep this evidence\n")
        self.assert_integration_removed()
        for branch in ("gs/demo-other/01", "gs/demo2/integration"):
            self.assertTrue(git.branch_exists(self.repo, branch))
            self.assertIn(branch, sh(self.remote, "git", "branch", "--list", branch))
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assertIn("지움: worktree 0, 로컬 브랜치 0, 원격 브랜치 0 · 실행 기록은 남김", out)

    def test_refuses_unfinished_without_force(self):
        for phase in ("preparing", "not_merged", "merge_pending", "main_failed", None):
            with self.subTest(phase=phase):
                state.save(self.rundir, state.State(feature="demo", finish={"phase": phase}))
                code, out, err = self.clean()
                self.assertEqual(code, 1)
                self.assertIn("--force", err)
                self.assertEqual(out, "")

    def test_clean_normalizes_relative_and_symlink_repo_paths(self):
        alias = self.repo.with_name("repo-link")
        alias.symlink_to(self.repo, target_is_directory=True)
        for cwd, repo in ((self.repo, Path(".")), (self.repo.parent, Path("repo")),
                          (self.repo.parent, alias)):
            with self.subTest(cwd=cwd, repo=repo):
                state.save(self.rundir, state.State(feature="demo", finish={"phase": "verified"}))
                wt = self.rundir / "wt/01"
                branch = "gs/demo/01"
                git.ensure_worktree(self.repo, wt, branch, "HEAD")
                (wt / "uncommitted.txt").write_text("discard\n")
                sh(self.repo, "git", "push", "-q", self.REMOTE, branch)
                with contextlib.chdir(cwd):
                    code, out, err = self.clean(repo=repo)
                self.assertEqual(code, 0, out + err)
                self.assertEqual(err, "")
                self.assertIn("지움: worktree 1, 로컬 브랜치 1, 원격 브랜치 1 · 실행 기록은 남김", out)
                self.assertEqual(out.splitlines().count(f"지움: worktree {wt} (미커밋 변경도 지움)"), 1)
                self.assertFalse(wt.exists())
                self.assertNotIn(wt, git.worktrees(self.repo))

    def test_force_removes_unfinished_but_never_bypasses_running_lock(self):
        self.prepare("main_failed")
        with state.Lock(self.rundir):
            for args in ((), ("--force",)):
                code, out, err = self.clean(*args)
                self.assertEqual(code, 1)
                self.assertIn("이미 다른 gs go가 돌고 있다", err)
                self.assertTrue((self.rundir / "wt/integration").exists())
        code, out, err = self.clean("--force")
        self.assertEqual(code, 0, out + err)
        self.assert_integration_removed()

    def test_verified_auto_cleanup_runs_after_base_report_then_go_resumes(self):
        real_run = git.run
        seen = []

        def observe(cwd, *args, **kw):
            if args[:2] == ("worktree", "remove") and str(self.rundir / "wt/integration") in args:
                seen.append(state.load(self.rundir, "demo").finish.get("base_report_tried"))
                self.assertIn("마무리: verified", sh(self.remote, "git", "show", f"{self.BASE}:.goldstack/work/demo/report.md"))
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(seen, [True])
        self.assert_integration_removed()
        self.assertTrue((self.rundir / "state.json").exists())
        self.assertTrue(list((self.rundir / "01").rglob("worker.log")))
        self.assertEqual(self.clean()[0], 0)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("이미 끝남", out)
        self.assert_integration_removed()

    def test_cleanup_failure_only_warns_and_keeps_verified(self):
        real_run = git.run

        def fail(cwd, *args, **kw):
            if (args[:2] == ("worktree", "remove") and str(self.rundir / "wt/integration") in args
                    or args[:2] == ("push", self.REMOTE) and "--delete" in args):
                raise git.GitError("cleanup denied")
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=fail):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("경고: 정리 실패", out)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertTrue((self.rundir / "wt/integration").exists())
        self.assertIn("gs/demo/integration", sh(self.remote, "git", "branch", "--list", "gs/demo/integration"))

    def test_auto_cleanup_only_removes_integration(self):
        wt = self.rundir / "wt/99-retry-2"
        git.ensure_worktree(self.repo, wt, "gs/demo/99-retry-2", "HEAD")
        (wt / "unfinished").write_text("keep\n")
        for branch in ("gs/demo/99-retry-2", "gs/demo/integration-old", "gs/other/integration"):
            if not git.branch_exists(self.repo, branch):
                sh(self.repo, "git", "branch", branch)
            sh(self.repo, "git", "push", "-q", self.REMOTE, branch)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_integration_removed()
        self.assertEqual((wt / "unfinished").read_text(), "keep\n")
        for branch in ("gs/demo/99-retry-2", "gs/demo/integration-old", "gs/other/integration"):
            self.assertTrue(git.branch_exists(self.repo, branch))
            self.assertIn(branch, sh(self.remote, "git", "branch", "--list", branch))

    def test_report_push_failure_is_attempted_before_auto_cleanup(self):
        with mock.patch("gs.finish._report_commit", side_effect=git.GitError("report push denied")) as push:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(push.call_count, 2)
        self.assertIn("최종 보고서를 trunk에 push하지 못했다", out)
        self.assertTrue(state.load(self.rundir, "demo").finish["base_report_tried"])
        self.assert_integration_removed()

    def test_verified_before_report_attempt_keeps_integration_for_resume(self):
        from gs import finish
        real_update = finish._update

        def fail(r, summary):
            if r.st.finish.get("phase") == "verified":
                raise git.GitError("report update denied")
            return real_update(r, summary)

        with mock.patch("gs.finish._update", side_effect=fail):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("base_report_tried", state.load(self.rundir, "demo").finish)
        self.assertTrue((self.rundir / "wt/integration").exists())
        self.assertTrue(git.branch_exists(self.repo, "gs/demo/integration"))

    def test_invalid_feature_name_is_refused(self):
        for name in ("../demo", "demo/../demo", "/tmp", ".."):
            with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.main(["--repo", str(self.repo), "clean", name, "--force"]), 1)

    def test_reverted_is_kept_until_manual_clean_and_go_still_resumes(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "reverted")
        self.assertTrue((self.rundir / "wt/integration").exists())
        self.assertTrue(git.branch_exists(self.repo, "gs/demo/integration"))
        self.assertIn("gs/demo/integration", sh(self.remote, "git", "branch", "--list", "gs/demo/integration"))
        code, out, err = self.clean()
        self.assertEqual(code, 0, out + err)
        self.assert_integration_removed()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn("이미 끝남", out)
        self.assertNotIn("git 오류", err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "reverted")

    def test_failed_finish_is_not_automatically_cleaned(self):
        self.parallel(1, verify="git rev-parse -q --verify MERGE_HEAD >/dev/null")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "not_merged")
        self.assertTrue((self.rundir / "wt/integration").exists())
        self.assertTrue(git.branch_exists(self.repo, "gs/demo/integration"))
        self.assertIn("gs/demo/integration", sh(self.remote, "git", "branch", "--list", "gs/demo/integration"))


if __name__ == "__main__":
    unittest.main()
