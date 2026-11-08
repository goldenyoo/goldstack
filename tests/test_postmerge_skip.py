"""병합 뒤 첫 base 검증 건너뛰기: integration에서 검증한 코드 그대로면 main 검증을 다시 돌리지 않는다.

`finish._same_as_verified`가 사실을 읽고 `revert_decision.next_step`이 첫 검증(`VERIFY_MAIN`) 자리에서만 `SKIP_MAIN`으로 답한다.
"""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import finish, findings, state
import support
from support import sh

REPORT = ".goldstack/work/demo/report.md"


class SameCodeTest(unittest.TestCase):
    """임시 레포에 통과한 integration → 보고서·아이디어 파일 커밋 → base 병합을 만들고 `_postmerge`를 부른다.

    git·fetch·worktree·revert push는 진짜다. 검증 명령을 돌리는 `_verify`만 부른 라벨을 적는 대역이다."""

    def setUp(self):
        support.isolate_git_env(self)  # 아래 환경 변수도 시험이 끝나면 되돌린다
        os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
                           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.remote = root / "remote.git"
        sh(root, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        self.write("code.py", "a = 1\n")
        self.write(".goldstack/config.toml", "[git]\nbase = \"main\"\n")
        self.commit("init")
        sh(self.repo, "git", "remote", "add", "origin", str(self.remote))
        sh(self.repo, "git", "push", "-q", "-u", "origin", "main")
        self.rundir = root / "run"
        (self.rundir / "finish").mkdir(parents=True)
        self.r = SimpleNamespace(
            repo=self.repo, iwt=self.repo, remote="origin", base="main", base_ref="origin/main", rundir=self.rundir,
            name="demo", order=["01"], save=lambda: None,
            st=SimpleNamespace(finish={}, phase="finish", metrics={}, push_record={}, tickets={
                "01": state.TicketState(status=state.MERGED, review={"findings": [{"severity": "high", findings.NUMBER: 1}]})}),
            cfg=SimpleNamespace(git=SimpleNamespace(direct_push=True), worktree=SimpleNamespace(setup="")))
        (self.idea,) = findings.paths(self.r)  # 보고만 high 지적의 아이디어 파일
        # integration: 티켓 코드를 검증해 통과했고(verified_head), 그 위에 보고서와 아이디어 파일을 커밋했다(PR head).
        sh(self.repo, "git", "checkout", "-q", "-b", "gs/demo/integration")
        self.write("code.py", "a = 2\n")
        self.commit("ticket 01")
        self.passed = sh(self.repo, "git", "rev-parse", "HEAD")
        self.write(REPORT, "# demo 결과\n")
        self.write(self.idea, "---\nstatus: open\n---\n지적\n")
        self.commit("gs: demo 최종 보고서")
        self.head = sh(self.repo, "git", "rev-parse", "HEAD")
        sh(self.repo, "git", "checkout", "-q", "main")

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, message):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", message)
        return sh(self.repo, "git", "rev-parse", "HEAD")

    def push_main(self):
        sh(self.repo, "git", "push", "-q", "origin", "main")
        return sh(self.repo, "git", "rev-parse", "HEAD")

    def merge(self, *, before=None, **stored):
        """PR을 병합한다. before={경로: 내용}이면 그 전에 base가 그 변경으로 움직였다(병합 커밋에 함께 든다)."""
        if before:
            for rel, text in before.items():
                self.write(rel, text)
            self.commit("someone else")
        sh(self.repo, "git", "merge", "-q", "--no-ff", "gs/demo/integration", "-m", "Merge feature")
        self.merge_sha = self.push_main()
        self.r.st.finish.update({"phase": "merged", "merge_sha": self.merge_sha, "merge_head": self.head,
                                 "merge_method": "merge", "verified_head": self.passed, **stored})
        return self.merge_sha

    def revert_commit(self):
        """병합 커밋을 되돌린 커밋을 base 끝 위에 만들기만 한다(push하지 않는다)."""
        sh(self.repo, "git", "revert", "--no-edit", "-m", "1", self.merge_sha)
        sha = sh(self.repo, "git", "rev-parse", "HEAD")
        sh(self.repo, "git", "reset", "-q", "--hard", self.merge_sha)
        return sha

    def postmerge(self, *, verify_ok=True, **patches):
        self.labels = []

        def verify(r, wt, label):
            self.labels.append(label)
            return verify_ok

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch("gs.finish._verify", side_effect=verify))
            for name, value in patches.items():
                stack.enter_context(mock.patch(f"gs.finish.{name}", value))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return finish._postmerge(self.r)

    @property
    def f(self) -> dict:
        return self.r.st.finish

    def log(self) -> Path:
        return self.rundir / "finish" / "main-verify.log"

    def remote_main(self) -> str:
        return sh(self.remote, "git", "rev-parse", "main")

    def assert_skip_condition(self):
        """아래 시험의 base는 건너뛸 조건이 참이다: 받아 온 끝이 병합 커밋이고 차이는 보고서·아이디어 파일뿐이다."""
        sh(self.repo, "git", "fetch", "-q", "origin", "main")
        changed = set(sh(self.repo, "git", "diff", "--name-only", self.passed, self.merge_sha).split())
        self.assertEqual(changed, {REPORT, self.idea})
        self.assertTrue(finish._same_as_verified(self.r, self.remote_main()))

    def test_report_and_idea_only_skips_verify(self):
        merge = self.merge()
        self.assert_skip_condition()
        self.assertTrue(self.postmerge(verify_ok=False))  # 검증을 돌렸다면 실패해 revert했을 것이다
        self.assertEqual(self.labels, [])
        self.assertEqual((self.f["phase"], self.f["main_ok"], self.f["main_head"]), ("verified", True, merge))
        self.assertEqual(self.f["outcome"], "integration·main 검증 통과, PR 병합 완료")  # 검증을 통과했을 때와 같다
        self.assertEqual(self.log().read_text(), f"integration과 같은 코드({self.passed}), 건너뜀\n")
        self.assertEqual(self.remote_main(), merge)
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])
        self.assertNotIn("gs-main-", sh(self.repo, "git", "worktree", "list"))
        # 끝난 마무리는 다시 읽지도 검증하지도 않는다.
        self.assertTrue(self.postmerge(verify_ok=False))
        self.assertEqual(self.labels, [])

    def test_one_code_line_runs_verify(self):
        self.merge(before={"other.py": "b = 1\n"})
        self.assertTrue(self.postmerge())
        self.assertEqual(self.labels, ["main"])
        self.assertEqual(self.f["phase"], "verified")
        self.assertFalse(self.log().exists())  # 대역 `_verify`는 로그를 쓰지 않는다. 건너뜀 글이 남지 않았다

    def test_other_goldstack_file_runs_verify(self):
        # `.goldstack/` 전체를 허용하는 `_code_same`이면 같은 코드다. 건너뛰기는 그 기준을 쓰지 않는다.
        self.merge(before={".goldstack/config.toml": "[git]\nbase = \"main\"\ndirect_push = false\n"})
        self.assertTrue(finish._code_same(self.r))
        self.assertTrue(self.postmerge())
        self.assertEqual(self.labels, ["main"])

    def test_moved_base_runs_verify(self):
        merge = self.merge()
        # 병합 뒤 base가 움직였다. 보고서만 바꾼 커밋이라도 받아 온 끝이 병합 커밋이 아니니 검증한다.
        self.write(REPORT, "# demo 결과\n\n사람이 고침\n")
        self.commit("someone edits report")
        tip = self.push_main()
        self.assertTrue(self.postmerge())
        self.assertEqual(self.labels, ["main"])
        self.assertEqual((self.f["phase"], self.f["main_head"]), ("verified", tip))
        self.assertNotEqual(tip, merge)

    def test_old_state_without_verified_head_runs_verify(self):
        self.merge()
        del self.f["verified_head"]
        self.assertTrue(self.postmerge())
        self.assertEqual(self.labels, ["main"])

    def test_interrupted_run_skips_on_resume(self):
        merge = self.merge()
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            self.postmerge(_prepare_base=mock.Mock(side_effect=RuntimeError("interrupted")))
        self.assertEqual(self.f["phase"], "merged")
        self.assertFalse(self.log().exists())
        self.assertTrue(self.postmerge(verify_ok=False))
        self.assertEqual(self.labels, [])
        self.assertEqual((self.f["phase"], self.f["main_ok"], self.f["main_head"]), ("verified", True, merge))
        self.assertEqual(self.log().read_text(), f"integration과 같은 코드({self.passed}), 건너뜀\n")

    # 아래는 건너뛸 조건이 참이어도 이미 정한 길(재시도, 지난 실패, 만들어 둔 revert, 열린 revert PR, 외부 revert)을 따른다.
    def test_main_retry_still_retries(self):
        merge = self.merge(phase="main_retry", main_ok=False)
        self.f["main_head"] = merge  # 지난 실패와 같은 커밋
        self.assert_skip_condition()
        self.assertTrue(self.postmerge(verify_ok=True))
        self.assertEqual(self.labels, ["main-retry"])
        self.assertEqual(self.f["phase"], "verified")
        self.assertIn("flaky: main 재시도 1번 만에 통과", self.f["outcome"])
        self.assertFalse(self.log().exists())

    def test_main_failed_still_reverts(self):
        merge = self.merge(phase="main_failed", main_ok=False)
        self.f["main_head"] = merge  # 지난 실패를 믿는다
        self.assert_skip_condition()
        self.assertFalse(self.postmerge(verify_ok=True))
        self.assertEqual(self.labels, [])
        self.assertEqual(self.f["phase"], "reverted")
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main^"), merge)
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), self.f["revert_sha"])
        self.assertFalse(self.log().exists())

    def test_unpushed_revert_is_pushed(self):
        merge = self.merge(phase="main_failed", main_ok=False)
        self.f.update(main_head=merge, revert_sha=self.revert_commit())
        self.assert_skip_condition()
        self.assertFalse(self.postmerge(verify_ok=True))
        self.assertEqual(self.labels, [])
        self.assertEqual(self.f["phase"], "reverted")
        self.assertEqual(self.remote_main(), self.f["revert_sha"])
        self.assertFalse(self.log().exists())

    def test_open_revert_pr_is_kept(self):
        self.r.cfg.git.direct_push = False
        merge = self.merge(phase="revert_pending", main_ok=False)
        sha = self.revert_commit()
        self.f.update(main_head=merge, revert_sha=sha, revert_head=sha, revert_pr="https://github.com/t/r/pull/9")
        self.assert_skip_condition()
        revert_pr = mock.Mock(return_value=False)
        self.assertFalse(self.postmerge(verify_ok=True, _read_revert_pr=mock.Mock(return_value={"state": "OPEN"}),
                                        _revert_pr=revert_pr))
        self.assertEqual(self.labels, [])
        revert_pr.assert_called_once_with(self.r, sha)  # 같은 PR을 기다린다
        self.assertEqual(self.f["phase"], "revert_pending")
        self.assertEqual(self.remote_main(), merge)
        self.assertFalse(self.log().exists())

    def test_external_revert_is_recorded(self):
        merge = self.merge()
        # 누군가 병합을 되돌렸다. 그러면 받아 온 끝이 움직여 건너뛸 조건이 거짓이 되니, 그 사실을 참으로 고정해 순서만 본다.
        sh(self.repo, "git", "revert", "--no-edit", "-m", "1", merge)
        theirs = self.push_main()
        self.assertFalse(self.postmerge(verify_ok=True, _same_as_verified=mock.Mock(return_value=True)))
        self.assertEqual(self.labels, [])
        self.assertEqual((self.f["phase"], self.f["revert_sha"]), ("reverted", theirs))
        self.assertFalse(self.log().exists())


class GoSkipTest(support.GoTest):
    """진짜 `gs go`: 가짜 gh가 base를 옮기지 않고 병합하니 병합 커밋이 통과한 integration과 같은 코드다."""
    POSTMERGE_SKIP = True

    def setUp(self):
        super().setUp()
        self.runs = self.bin / "verify.pwd"
        # 검증 명령이 돈 곳을 남긴다. main 검증은 임시 base worktree(gs-main-*)에서 돈다.
        self.parallel(1, verify=f'echo "$PWD" >> {self.runs}')

    def assert_main_skipped(self):
        f = state.load(self.rundir, "demo").finish
        self.assertEqual((f["phase"], f["main_ok"]), ("verified", True), f)
        log = (self.rundir / "finish/main-verify.log").read_text()
        self.assertEqual(log, f"integration과 같은 코드({f['verified_head']}), 건너뜀\n")
        self.assertTrue(self.runs.exists())  # integration 검증은 돌았다
        self.assertNotIn("gs-main-", self.runs.read_text())

    def test_go_skips_main_verify_of_same_code(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_main_skipped()
        self.assertIn("■ main 검증: integration과 같은 코드(", out)

    def test_resumed_go_skips_too(self):
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_main_skipped()
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)


if __name__ == "__main__":
    unittest.main()
