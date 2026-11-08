"""config `[worktree] setup_when`: 병합이 걸리는 파일을 바꾸면 integration에서 setup을 다시 돌리고 검증한다(goldstack-v25 02).

시험 레포의 `uv.lock`이 의존성 파일 역할이다. setup은 그 내용을 `installed`(gitignore)에 복사하고, 검증은 둘이 같은지 본다:
환경이 검증하는 트리의 것이 아니면 검증이 떨어진다.
"""
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import support
from gs import config, setup, state
from gs import go as gs_go
from support import sh

ENV_MATCHES = 'test "$(cat installed)" = "$(cat uv.lock)" && test ! -f BROKEN'


class MatchTest(unittest.TestCase):
    def test_glob_is_rooted_and_star_does_not_cross_slash(self):
        cases = [("uv.lock", "uv.lock", True), ("uv.lock", "sub/uv.lock", False),
                 ("**/uv.lock", "uv.lock", True), ("**/uv.lock", "a/b/uv.lock", True),
                 ("*.lock", "uv.lock", True), ("*.lock", "sub/uv.lock", False),
                 ("docs/**", "docs/a/b.md", True), ("docs/**", "src/docs.md", False),
                 ("requirements*.txt", "requirements-dev.txt", True), ("pyproject.toml", "pyproject.toml.bak", False)]
        for glob, path, expected in cases:
            with self.subTest(glob=glob, path=path):
                self.assertEqual(setup.matches([glob], path), expected)
        self.assertTrue(setup.matches(["pyproject.toml", "uv.lock"], "uv.lock"))
        self.assertFalse(setup.matches([], "uv.lock"))


class StaleTest(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.wt = Path(tmp.name)
        sh(self.wt, "git", "init", "-q")
        self.commit("uv.lock", "v1\n")
        self.cfg = config.Config(config.GitConfig("origin", "main"), config.ModelsConfig("opus", "opus", "agy", ""),
                                 config.TimeoutsConfig(30, 10, 60), config.NotifyConfig(False))

    def commit(self, name, text):
        (self.wt / name).write_text(text)
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", name)
        return sh(self.wt, "git", "rev-parse", "HEAD")

    def test_compares_globbed_files_with_last_prepared_commit(self):
        globs = ("uv.lock",)
        self.assertEqual(setup.stale(self.wt, (), "HEAD"), "", "setup_when이 비면 대조하지 않는다")
        self.assertIn("기록 없음", setup.stale(self.wt, globs, "HEAD"), "옛 표지만 있으면 어느 커밋의 준비인지 모른다")
        prepared = sh(self.wt, "git", "rev-parse", "HEAD")
        setup.remember(self.wt)
        self.assertEqual(setup.stale(self.wt, globs, "HEAD"), "")
        self.commit("other.txt", "x\n")
        self.assertEqual(setup.stale(self.wt, globs, "HEAD"), "", "걸리지 않는 파일만 바뀌었다")
        lock = self.commit("uv.lock", "v2\n")
        self.assertEqual(setup.stale(self.wt, globs, "HEAD"), "uv.lock")
        self.assertEqual(setup.stale(self.wt, globs, sh(self.wt, "git", "rev-parse", "HEAD^{tree}")), "uv.lock")
        self.assertEqual(setup.stale(self.wt, globs, prepared), "", "준비한 커밋으로 돌아가면 맞다")
        setup.remember(self.wt)
        self.assertEqual(setup.stale(self.wt, globs, lock), "")
        setup._prepared(self.wt).write_text("0" * 40)
        self.assertIn("읽지 못함", setup.stale(self.wt, globs, "HEAD"))

    def test_run_forgets_prepared_commit_and_note_appends_to_log(self):
        cfg = replace(self.cfg, worktree=config.WorktreeConfig("echo second; exit 3"))
        log = self.wt / "attempt/setup.log"
        log.parent.mkdir()
        log.write_text("ticket worktree setup\n")
        setup.remember(self.wt)
        self.assertFalse(setup.run(cfg, self.wt, log, note="--- again ---").ok)
        self.assertIn("기록 없음", setup.stale(self.wt, ("uv.lock",), "HEAD"), "실패한 준비 뒤의 환경은 믿지 않는다")
        text = log.read_text()
        self.assertTrue(text.startswith("ticket worktree setup\n"), text)
        self.assertLess(text.index("--- again ---"), text.index("second"))
        self.assertFalse(setup.run(cfg, self.wt, log).ok)
        self.assertNotIn("ticket worktree setup", log.read_text(), "note가 없으면 지금처럼 덮어쓴다")


class SetupWhenTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    setUp, tearDown, go, calls, rundir, integration = G.setUp, G.tearDown, G.go, G.calls, G.rundir, G.integration

    def configure(self, command, verify_command, when=("uv.lock",)):
        (self.repo / "uv.lock").write_text("v1\n")
        path = self.repo / config.CONFIG_PATH
        line = "setup = " + json.dumps(f'echo "$(basename "$PWD") $(cat uv.lock)" >> {self.bin / "setups"}; {command}')
        if when is not None:
            line += "\nsetup_when = " + json.dumps(list(when))
        path.write_text(path.read_text().replace('setup = ""', line))
        with (self.repo / ".gitignore").open("a") as stream:
            stream.write("installed\n")
        spec = self.repo / ".goldstack/work/demo/spec.md"
        spec.write_text(spec.read_text().replace("test ! -f BROKEN", verify_command))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "setup_when")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def worker(self, tid, script):
        """FAKE_WORKER의 티켓별 동작 앞에 tid의 동작을 끼운다(호출 기록은 그대로 남는다)."""
        path = self.bin / "worker.sh"
        text = path.read_text()
        anchor = 'case "$GS_TICKET" in\n  02)'
        self.assertIn(anchor, text)
        path.write_text(text.replace(anchor, f'if [ "$GS_TICKET" = {tid} ]; then\n{script}\nexit 0\nfi\n' + anchor, 1))

    def setups(self):
        """(worktree, 그때의 uv.lock). 기본 worktree 이름은 임시라 base로 적는다."""
        path = self.bin / "setups"
        rows = [line.split() for line in path.read_text().splitlines()] if path.exists() else []
        return [("base" if name.startswith("gs-main-") else name, lock) for name, lock in rows]

    def spy(self):
        """setup.run을 부른 순간 그 worktree가 미완 병합(MERGE_HEAD)이었는지 남긴다."""
        seen, real = [], setup.run

        def run(cfg, wt, log, **kw):
            merging = subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=wt,
                                     capture_output=True).returncode == 0
            seen.append((Path(wt).name, merging))
            return real(cfg, wt, log, **kw)

        return seen, mock.patch.object(setup, "run", side_effect=run)

    def test_matching_merge_reruns_setup_on_merge_commit_and_other_merge_does_not(self):
        self.configure("cat uv.lock > installed; echo v1 > uv.lock", ENV_MATCHES)  # uv sync처럼 lockfile도 고친다
        self.worker("01", "echo v2 > uv.lock; git add -A; git commit -qm lock")
        seen, patch = self.spy()
        with patch:
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets
        self.assertEqual((ts["01"].status, ts["04"].status), (state.MERGED, state.MERGED), out)
        self.assertEqual(ts["01"].repairs, [], "첫 검증이 다시 준비한 환경에서 통과했다")
        # integration은 처음 한 번과 01 병합 뒤 한 번. 04 병합은 uv.lock을 바꾸지 않는다
        self.assertEqual(self.setups(), [("integration", "v1"), ("01", "v1"), ("integration", "v2"), ("04", "v2"),
                                         ("base", "v2")])
        self.assertEqual([merging for _, merging in seen], [False] * 5, "미완 병합 중에 setup.run을 불렀다")
        self.assertIn("setup_when에 걸림(uv.lock)", out)
        # 시도 디렉터리의 setup.log: 티켓 worktree의 준비 기록 뒤에 integration 준비가 이어진다
        log = (self.rundir / "01/1/setup.log").read_text()
        self.assertEqual(log.count("종료 코드: 0"), 2, log)
        self.assertIn("integration에서 다시 준비", log)
        self.assertNotIn("integration에서 다시 준비", (self.rundir / "04/1/setup.log").read_text())
        # setup이 고친 uv.lock은 병합 커밋으로 되돌아갔다. 병합한 내용이 integration·base에 그대로다
        self.assertIn("setup이 추적 파일을 바꿨다", log)
        self.assertEqual(self.integration("show", "gs/demo/integration:uv.lock"), "v2")
        self.assertEqual(sh(self.remote, "git", "show", f"{self.BASE}:uv.lock"), "v2")
        merge = state.load(self.rundir, "demo").metrics["validations"]
        first = next(v for v in merge if v["label"] == "ticket-01")
        self.assertTrue(first["ticket_head"] and first["integration_head"], first)
        self.assertNotEqual(first["ticket_head"], first["integration_head"])

    def test_empty_setup_when_keeps_single_integration_setup(self):
        self.configure("cat uv.lock > installed", "test -f installed && test ! -f BROKEN", when=None)
        self.worker("01", "echo v2 > uv.lock; git add -A; git commit -qm lock")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.setups(), [("integration", "v1"), ("01", "v1"), ("base", "v2")])
        self.assertNotIn("setup_when", out)

    def test_cancelled_merge_resyncs_environment_before_next_verify(self):
        """첫 검증이 떨어져 v2 환경이 남는다. 수리가 uv.lock을 되돌리면 다음 검증 전에 v1로 다시 준비한다."""
        self.configure("cat uv.lock > installed", ENV_MATCHES)
        self.worker("01", f'if [ ! -f "{self.bin}/a01" ]; then touch "{self.bin}/a01"; echo v2 > uv.lock; touch BROKEN\n'
                          'else git rm -q BROKEN; echo v1 > uv.lock; echo 1 > file_01; fi\n'
                          'git add -A; git commit -qm "t01 $(date +%s%N)"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.status, state.MERGED)
        self.assertEqual([r["result"] for r in ts.repairs], [state.REPAIR_PASSED])
        self.assertEqual(self.setups(), [("integration", "v1"), ("01", "v1"), ("integration", "v2"),
                                         ("integration", "v1"), ("base", "v1")])
        self.assertEqual(self.integration("show", "gs/demo/integration:uv.lock"), "v1")

    def test_failed_resetup_is_a_verify_failure_with_log_path(self):
        self.configure('cat uv.lock > installed; case "$PWD" in */wt/integration) '
                       'if grep -q v2 uv.lock; then echo lock-boom; exit 9; fi;; esac', ENV_MATCHES)
        self.worker("01", f'if [ ! -f "{self.bin}/a01" ]; then touch "{self.bin}/a01"; echo v2 > uv.lock\n'
                          'else echo v1 > uv.lock; echo 1 > file_01; fi\n'
                          'git add -A; git commit -qm "t01 $(date +%s%N)"')
        with mock.patch.object(gs_go, "_verify", wraps=gs_go._verify) as verify:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.status, state.MERGED)
        log = self.rundir / "01/1/setup.log"
        self.assertEqual(len(ts.repairs), 1)
        self.assertEqual(ts.repairs[0]["reason"], f"integration setup 실패(로그 {log})")
        self.assertEqual(ts.repairs[0]["verify_log"], str(log))
        self.assertIn("lock-boom", log.read_text())
        self.assertEqual(verify.call_count, 1, "실패한 setup 뒤에는 검증하지 않고 수리 뒤 한 번만 검증한다")
        # 실패한 준비 뒤에는 기록이 없어 수리한 병합(uv.lock 그대로)도 다시 준비한다
        self.assertEqual(self.setups(), [("integration", "v1"), ("01", "v1"), ("integration", "v2"),
                                         ("integration", "v1"), ("base", "v1")])

    def test_finish_verify_resyncs_after_last_merge_was_cancelled(self):
        """01은 끝내 실패한다. 마지막 병합 취소가 남긴 환경을 마무리 검증 전에 integration 끝에 다시 맞춘다."""
        self.configure("cat uv.lock > installed", ENV_MATCHES)
        self.worker("01", 'echo v2 > uv.lock; touch BROKEN; echo "$(date +%s%N)" >> file_01; '
                          'git add -A; git commit -qm t01')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, state.FAILED)
        rows = self.setups()
        self.assertEqual(rows[-1], ("integration", "v1"), rows)
        self.assertIn(("integration", "v2"), rows[:-1])
        self.assertNotIn(("base", "v1"), rows, "병합한 티켓이 없어 base 검증은 없다")
        verify_log = (self.rundir / "finish/integration-verify.log").read_text()
        self.assertTrue(verify_log.rstrip().endswith("종료 코드: 0"), verify_log)

    def test_resume_reattaches_detached_integration_and_resetups_without_record(self):
        """검증 전에 만든 병합 커밋(분리 HEAD)에서 gs가 죽은 자리와 옛 gs의 표지(준비 커밋 기록 없음)에서 잇는다."""
        self.configure("cat uv.lock > installed", ENV_MATCHES)
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        wt = self.rundir / "wt/integration"
        head = sh(wt, "git", "rev-parse", "HEAD")
        sh(wt, "git", "checkout", "-q", "--detach", "HEAD^")
        setup._prepared(wt).unlink()
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("integration 준비 다시(setup_when: 준비한 커밋 기록 없음)", out)
        self.assertEqual(self.calls(), ["01"], "분리 HEAD에서 이어도 병합한 티켓을 다시 하지 않는다")
        self.assertIn(head, self.integration("rev-list", "gs/demo/integration").split())
        self.assertEqual(self.setups(), [("integration", "v1"), ("01", "v1"), ("integration", "v1"), ("base", "v1")])


    def test_setup_that_moves_head_fails_ticket_before_verify(self):
        """다시 돈 setup이 integration에 커밋하면 검증할 트리가 병합 커밋과 다르다. 검증하지 않고 티켓 실패로 되돌린다."""
        moved = self.bin / "moved"
        self.configure('cat uv.lock > installed; case "$PWD" in */wt/integration) '
                       f'if grep -q v2 uv.lock && [ ! -f "{moved}" ]; then touch "{moved}"; echo x > extra; git add extra; '
                       'git -c user.name=t -c user.email=t@t commit -qm extra; fi;; esac', ENV_MATCHES)
        self.worker("01", 'echo v2 > uv.lock; git add -A; git commit -qm "lock $(date +%s%N)"')
        with mock.patch.object(gs_go, "_verify", wraps=gs_go._verify) as verify:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(moved.exists(), "setup이 커밋하지 않았다")
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), (state.MERGED, 2, 1), out)
        failure = (self.rundir / "01/1/failure.log").read_text()
        self.assertIn(f"setup하는 동안 integration이 바뀌었다(되돌림, 로그 {self.rundir / '01/1/setup.log'})", failure)
        self.assertEqual(ts.repairs, [], "브랜치의 결함이 아니니 수리하지 않는다")
        self.assertEqual(verify.call_count, 1, "setup이 HEAD를 옮긴 시도는 검증하지 않는다")
        # 실패한 준비 뒤의 환경은 믿지 않는다: 두 번째 시도의 병합에서 다시 준비한다
        self.assertEqual([s for s in self.setups() if s[0] == "integration"],
                         [("integration", "v1"), ("integration", "v2"), ("integration", "v2")])
        self.assertEqual(self.integration("show", "gs/demo/integration:uv.lock"), "v2")
        self.assertNotIn("extra", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())


if __name__ == "__main__":
    unittest.main()
