"""Landlock 모드로 세 경로를 띄운다(goldstack-v32 03): codex worker·codex 리뷰·agy 리뷰를 `gs jail` 안에서 띄운다.

어디서나 도는 시험: os 모드 명령이 글자 그대로인 것, landlock 명령의 모양(jail 앞부분, 쓰기·거부 목록), 지운 환경 변수,
codex 리뷰 답 옮기기, 가둘 수 없을 때의 중단(SandboxAbort, 병합 안 함), 모드를 주 레포 local.env에서 읽는 것, 보고서 머리 줄.
가둘 수 없는 경우는 실제 `gs jail`이 쓰기·거부 겹침으로 `JAIL_FAILED`를 내게 해서 만든다(리눅스·맥 어디서나 같다).
실제 Landlock 시험(RealLandlockTest)은 `jail.abi() >= 1`인 리눅스에서만 돈다. 시험 레포와 거부 경로는 쓰기 목록(/tmp, $TMPDIR) 밖에 둔다.
"""
import os
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from support import sh

from gs import adapters, config, go, jail, report, review, state, transient, worker
from gs.adapters import WorkerInput
from gs.feature import Ticket

q = shlex.quote
MODELS = config.ModelsConfig("judge-test", "review-test", "agy-test", "codex-test")
SELECTION = config.ModelEffort("m-test", "high")
ANSWER = '{"findings": []}'
LANDLOCK_LINE = "샌드박스: landlock(네트워크 열림)"
DROPPED = ("GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "SSH_AUTH_SOCK")
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
NO_SECRETS = SimpleNamespace(sandbox=SimpleNamespace(secrets=[]))

# 가짜 codex: 인자·환경·지금 디렉터리를 남기고 `--output-last-message`가 있으면(리뷰) 거기에 답을 쓴다.
FAKE_CODEX = """\
#!/bin/bash
here="$(dirname "$0")"
cat > /dev/null
echo called >> "$here/codex.calls"
printf '%s\\n' "$@" > "$here/codex.args"
env > "$here/codex.env"
out=""
while [ $# -gt 0 ]; do if [ "$1" = --output-last-message ]; then out="$2"; fi; shift; done
if [ -n "$out" ]; then printf '%s\\n' '{"findings": []}' > "$out"; fi
"""
# 가짜 agy 리뷰어: 인자·환경을 남기고 답을 stdout에 낸다.
FAKE_AGY = """\
#!/bin/bash
here="$(dirname "$0")"
echo called >> "$here/agy.calls"
printf '%s\\n' "$@" > "$here/agy.args"
env > "$here/agy.env"
echo '{"findings": []}'
"""


def split_jail(argv):
    """jail 명령을 (앞 네 낱말, 쓰기 목록, 거부 목록, `--` 뒤 명령)으로 나눈다. 앞부분에 다른 낱말이 끼면 실패한다."""
    end = argv.index("--")
    head, inner = argv[:end], argv[end + 1:]
    writes = [head[i + 1] for i, a in enumerate(head) if a == "--write"]
    denies = [head[i + 1] for i, a in enumerate(head) if a == "--deny"]
    assert len(head) == 4 + 2 * (len(writes) + len(denies)), head
    return head[:4], writes, denies, inner


def env_file(path: Path) -> dict:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


class Fixture(unittest.TestCase):
    """임시 HOME, 주 레포(local.env에 GS_SANDBOX=landlock), `gs/demo/01` 브랜치의 worktree, 가짜 codex·agy."""

    def setUp(self):
        support.isolate_git_env(self)  # os.environ을 시험 뒤 되돌린다
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.shared = self.root / "shared"  # 시험의 SHARED_TMP(/tmp 대신). 리뷰 트리를 품지 않는다
        self.shared.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, body in (("codex", FAKE_CODEX), ("agy", FAKE_AGY)):
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        os.environ.update(GIT_ENV, HOME=str(self.home), PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}")
        for name in ("GS_REVIEWER_CMD", "GS_WORKER_CMD", "GS_AGY", "CODEX_HOME"):
            os.environ.pop(name, None)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / "a").write_text("a\n")
        (self.repo / ".gitignore").write_text(".goldstack/local.env\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        (self.repo / ".goldstack").mkdir()
        (self.repo / ".goldstack" / "local.env").write_text("GS_SANDBOX=landlock\n")
        self.wt = self.root / "wt"
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "gs/demo/01", str(self.wt))
        self.brief = self.root / "run" / "brief.md"
        self.brief.parent.mkdir()
        self.brief.write_text("brief\n")
        self.inp = WorkerInput(brief=self.brief, worktree=self.wt, log=self.root / "run" / "worker.log")
        self.out = self.root / "rdir" / "review.txt"
        self.out.parent.mkdir()

    def git_dirs(self) -> list[str]:
        """codex worker가 커밋에 쓰는 git 디렉터리(Codex.writable_dirs와 따로 git에 묻는다)."""
        common = sh(self.wt, "git", "rev-parse", "--path-format=absolute", "--git-common-dir")
        own = sh(self.wt, "git", "rev-parse", "--path-format=absolute", "--git-dir")
        return [own, f"{common}/objects", f"{common}/refs/heads/gs", f"{common}/logs/refs/heads/gs"]

    def landlock(self, secrets=()) -> adapters.Sandbox:
        """gs go가 시작할 때 계산하는 값(주 레포 local.env와 denies)."""
        box = go._sandbox(self.repo, SimpleNamespace(sandbox=SimpleNamespace(secrets=[str(s) for s in secrets])))
        self.assertEqual(box.mode, "landlock")
        return box

    def assert_denies(self, denies, own, others):
        self.assertIn(str(self.home / ".ssh"), denies)
        self.assertIn(str(self.home / ".config" / "gh"), denies)
        self.assertIn(str(self.repo / ".goldstack" / "local.env"), denies)  # 주 레포의 것
        for other in others:
            self.assertIn(str(self.home / other), denies)
        self.assertNotIn(str(self.home / own), denies)  # 자기 홈은 읽는다

    def commit_in_wt(self):
        (self.wt / "b").write_text("b\n")
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "commit", "-qm", "b")

    def run_review(self, reviewer, box, **extra):
        cfg = SimpleNamespace(models=MODELS, timeouts=config.TimeoutsConfig(30, 10, 60))
        return review.run(repo=self.repo, worktree=self.wt, rdir=self.out.parent, base="main", branch="gs/demo/01",
                          ticket=self.root / "ticket.md", spec=self.root / "spec.md", model="claude", reviewer=reviewer,
                          cfg=cfg, sandbox=box, **extra)


class OsModeUnchangedTest(Fixture):
    """os 모드(값 없음, 기본값, os에 거부 목록이 있어도)의 세 명령은 바꾸기 전과 글자 그대로 같다."""

    BOXES = {"없음": None, "기본": adapters.Sandbox(), "os": adapters.Sandbox("os", {"codex": [Path("/x")], "agy": [Path("/y")]})}

    def test_codex_worker_command(self):
        adds = " ".join(f"--add-dir {q(d)}" for d in self.git_dirs())
        expected = (f"codex exec --json -s workspace-write --model m-test -c model_reasoning_effort=high "
                    f"-c sandbox_workspace_write.network_access=false --skip-git-repo-check -C {q(str(self.wt))} "
                    f"{adds} {q(adapters.Codex.NOTE)} < {q(str(self.brief))}")
        self.assertEqual(adapters.Codex(MODELS, SELECTION).command(self.inp), expected)  # 옛 호출
        for name, box in self.BOXES.items():
            with self.subTest(name):
                adapter = adapters.for_model("codex", MODELS, SELECTION, sandbox=box)
                self.assertEqual(adapter.command(self.inp), expected)
                self.assertFalse(adapter.jailed)

    def test_reviewer_argv(self):
        scratch = self.root / "scratch"
        scratch.mkdir()
        codex = (["codex", "exec", "--json", "--model", "m-test", "-c", "model_reasoning_effort=high",
                  "-s", "workspace-write", "-c", "sandbox_workspace_write.network_access=false",
                  "--skip-git-repo-check", "-C", str(scratch), "--output-last-message", str(self.out), "-"], "P", True)
        agy = (["agy", "-p", "P", "--sandbox", "--dangerously-skip-permissions", "--disable-slash-commands",
                "--settings", '{"permissions":{"deny":["command(git push)","command(gh pr create)","command(gh pr merge)",'
                '"command(gh pr close)","command(gh api)","command(gh repo)","command(gh release)","command(gh auth)"]}}',
                "--model", "m-test", "--effort", "high"], None, False)
        self.assertEqual(review.reviewer_argv("codex", self.wt, "P", self.out, MODELS, SELECTION, scratch=scratch), codex)
        self.assertEqual(review.reviewer_argv("agy", self.wt, "P", self.out, MODELS, SELECTION), agy)
        for name, box in self.BOXES.items():
            with self.subTest(name):
                self.assertEqual(review.reviewer_argv("codex", self.wt, "P", self.out, MODELS, SELECTION, scratch=scratch,
                                                      sandbox=box), codex)
                self.assertEqual(review.reviewer_argv("agy", self.wt, "P", self.out, MODELS, SELECTION, sandbox=box), agy)

    def test_worker_script_keeps_tokens(self):
        job = worker.Job(ticket=Ticket(id="01", title="t", blocked_by=[], model="codex", reviewer="claude",
                                       path=Path("01-t.md")), worktree=self.wt, rundir=self.root / "run")
        worker.write_script(job, adapters.Codex(MODELS, SELECTION, sandbox=adapters.Sandbox()))
        self.assertIn("\nunset CLAUDECODE CLAUDE_CODE_ENTRYPOINT GS_NOEQUALS\n", job.script.read_text())

    def test_reviewer_env_keeps_tokens_and_tmpdir(self):
        os.environ.update({name: "tok" for name in DROPPED}, TMPDIR=str(self.shared))
        self.commit_in_wt()
        rec = self.run_review("codex", adapters.Sandbox())
        self.assertEqual(rec["note"], "")
        env = env_file(self.bin / "codex.env")
        self.assertEqual({name: env.get(name) for name in DROPPED}, {name: "tok" for name in DROPPED})
        self.assertEqual(env["TMPDIR"], str(self.shared))
        self.assertIn("workspace-write", (self.bin / "codex.args").read_text().splitlines())


class LandlockCommandTest(Fixture):
    def test_mode_is_read_once_from_the_main_repo(self):
        self.assertFalse((self.wt / ".goldstack" / "local.env").exists())  # gitignore라 worktree에 없다
        box = self.landlock()
        self.assertEqual(sorted(box.denies), ["agy", "codex"])
        self.assert_denies([str(d) for d in box.denies["codex"]], ".codex", (".gemini", ".claude"))
        self.assert_denies([str(d) for d in box.denies["agy"]], ".gemini", (".codex", ".claude"))
        (self.repo / ".goldstack" / "local.env").unlink()
        self.assertEqual(go._sandbox(self.repo, NO_SECRETS), adapters.Sandbox())  # 없으면 os, 거부 목록도 없다

    def test_agy_denies_custom_codex_home(self):
        codex_home = self.root / "codex-profile"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}\n")
        os.environ["CODEX_HOME"] = str(codex_home)
        box = self.landlock()
        self.assertIn(codex_home, box.denies["agy"])  # 기본 ~/.codex 밖의 codex 홈도 agy는 읽지 못한다
        self.assertIn(self.home / ".codex", box.denies["agy"])
        self.assertNotIn(codex_home, box.denies["codex"])  # codex는 자기 홈을 읽는다
        scratch = self.root / "scratch"
        scratch.mkdir()
        with mock.patch.object(adapters, "SHARED_TMP", self.shared):
            argv, _, _ = review.reviewer_argv("agy", self.wt, "P", self.out, MODELS, scratch=scratch, sandbox=box)
        _, writes, denies, _ = split_jail(argv)
        self.assertIn(str(codex_home), denies)
        self.assertEqual(jail.overlap(writes, denies), "")  # 가둘 수 있는 목록이다
        self.assertNotIn(codex_home, jail.read_cover(denies, self.root))

    def test_missing_cli_home_is_created_before_jailing(self):
        os.environ["CODEX_HOME"] = str(self.root / "new-codex-home")
        box = self.landlock()
        scratch = self.root / "scratch"
        scratch.mkdir()
        homes = (Path(os.environ["CODEX_HOME"]), self.home / ".gemini")
        for home in homes:
            self.assertFalse(home.exists())
        adapters.Codex(MODELS, sandbox=box).command(self.inp)
        with mock.patch.object(adapters, "SHARED_TMP", self.shared):
            review.reviewer_argv("agy", self.wt, "P", self.out, MODELS, scratch=scratch, sandbox=box)
        for home in homes:  # 없는 쓰기 경로에는 jail이 규칙을 걸지 못해 가둔 CLI가 홈을 만들 수 없다
            self.assertTrue(home.is_dir(), home)

    def test_codex_worker_command(self):
        os.environ["TMPDIR"] = str(self.root / "tmpdir")
        box = self.landlock()
        for codex_home in (None, self.root / "codex-home"):
            with self.subTest(codex_home=codex_home):
                if codex_home:
                    os.environ["CODEX_HOME"] = str(codex_home)
                adapter = adapters.for_model("codex", MODELS, SELECTION, sandbox=box)
                self.assertTrue(adapter.jailed)
                head, writes, denies, inner = split_jail(shlex.split(adapter.command(self.inp)))
                self.assertEqual(head, [sys.executable, "-m", "gs.cli", "jail"])
                self.assertEqual(writes, [str(self.wt), *self.git_dirs(), "/tmp", str(self.root / "tmpdir"), "/dev",
                                          str(codex_home or self.home / ".codex")])
                self.assertEqual(denies, [str(d) for d in box.denies["codex"]])
                self.assert_denies(denies, ".codex", (".gemini", ".claude"))
                self.assertEqual(inner, ["codex", "exec", "--json", "-s", "danger-full-access", "--model", "m-test",
                                         "-c", "model_reasoning_effort=high", "--skip-git-repo-check",
                                         "-C", str(self.wt), adapters.Codex.NOTE, "<", str(self.brief)])

    def test_worker_without_tmpdir(self):
        os.environ.pop("TMPDIR", None)
        _, writes, _, _ = split_jail(shlex.split(adapters.Codex(MODELS, sandbox=self.landlock()).command(self.inp)))
        self.assertEqual(writes, [str(self.wt), *self.git_dirs(), "/tmp", "/dev", str(self.home / ".codex")])

    def test_reviewer_argv(self):
        box = self.landlock()
        scratch = self.root / "scratch"
        scratch.mkdir()
        self.assertEqual(adapters.SHARED_TMP, Path("/tmp"))
        with mock.patch.object(adapters, "SHARED_TMP", self.shared):  # 리눅스의 임시 레포는 /tmp 아래다
            codex = review.reviewer_argv("codex", self.wt, "P", self.out, MODELS, SELECTION, scratch=scratch, sandbox=box)
            agy = review.reviewer_argv("agy", self.wt, "P", self.out, MODELS, SELECTION, scratch=scratch, sandbox=box)
        head, writes, denies, inner = split_jail(codex[0])
        self.assertEqual(head, [sys.executable, "-m", "gs.cli", "jail"])
        self.assertEqual(writes, [str(scratch), str(self.shared), "/dev", str(self.home / ".codex")])
        self.assert_denies(denies, ".codex", (".gemini", ".claude"))
        self.assertEqual(inner, ["codex", "exec", "--json", "--model", "m-test", "-c", "model_reasoning_effort=high",
                                 "-s", "danger-full-access", "--skip-git-repo-check", "-C", str(scratch),
                                 "--output-last-message", str(scratch / "review.txt"), "-"])
        self.assertEqual(codex[1:], ("P", True))

        head, writes, denies, inner = split_jail(agy[0])
        self.assertEqual(head, [sys.executable, "-m", "gs.cli", "jail"])
        self.assertEqual(writes, [str(scratch), str(self.shared), "/dev", str(self.home / ".gemini")])
        self.assert_denies(denies, ".gemini", (".codex", ".claude"))
        self.assertEqual(inner, ["agy", "-p", "P", "--dangerously-skip-permissions", "--disable-slash-commands",
                                 "--settings", adapters.Agy.settings(), "--model", "m-test", "--effort", "high"])
        self.assertNotIn("--sandbox", agy[0])
        self.assertEqual(agy[1:], (None, False))

    def test_claude_and_seam_are_not_jailed(self):
        box = self.landlock()
        self.assertFalse(adapters.for_model("claude", MODELS, sandbox=box).jailed)
        self.assertFalse(adapters.for_model("agy", MODELS, sandbox=box).jailed)  # agy worker는 범위 밖
        os.environ["GS_REVIEWER_CMD"] = "cat"
        self.assertEqual(review.reviewer_argv("codex", self.wt, "P", self.out, MODELS, sandbox=box),
                         (["bash", "-c", "cat"], "P", False))

    def test_worker_script_drops_tokens_and_keeps_push_guard(self):
        """가둔 worker의 실행 스크립트를 실제로 돌려 명령이 받는 환경을 본다(명령은 jail 대신 env를 찍는다)."""
        class Printer(adapters.Codex):
            def command(self, inp):
                return "env"

        os.environ.update({name: "tok" for name in DROPPED}, GH_TOKEN="real")
        t = Ticket(id="01", title="t", blocked_by=[], model="codex", reviewer="claude", path=Path("01-t.md"))
        for box, jailed in ((self.landlock(), True), (adapters.Sandbox(), False)):
            with self.subTest(jailed=jailed):
                job = worker.Job(ticket=t, worktree=self.wt, rundir=self.root / f"run-{jailed}")
                job.rundir.mkdir()
                worker.write_script(job, Printer(MODELS, sandbox=box))
                subprocess.run(["bash", str(job.script)], capture_output=True, check=True, timeout=60)
                env = env_file(job.log)
                self.assertEqual({name: env.get(name) for name in DROPPED},
                                 {name: None if jailed else "tok" for name in DROPPED})
                self.assertEqual(env["GH_TOKEN"], worker.GH_BLOCKED)  # gh 차단은 그대로
                self.assertEqual(env["GIT_CONFIG_KEY_0"], f"url.{worker.PUSH_BLOCKED}.pushInsteadOf")  # push 차단도

    def test_jailed_reviewers_get_fresh_tmpdir_without_tokens_and_answer_is_moved(self):
        """jail 앞부분만 떼고 같은 명령을 실제로 띄운다: 가짜 codex가 `--output-last-message`(scratch 안)에 쓴 답이 review.txt로 옮겨진다."""
        os.environ.update({name: "tok" for name in DROPPED}, GH_TOKEN="real")
        os.environ["GS_AGY"] = str(self.bin / "agy")
        self.commit_in_wt()
        box = self.landlock()
        real = review._call
        seen = []

        def unjailed(argv, **kw):
            seen.append((argv, kw))
            return real(argv[argv.index("--") + 1:], **kw)

        for reviewer in ("codex", "agy"):
            with self.subTest(reviewer), mock.patch.object(adapters, "SHARED_TMP", self.shared), \
                    mock.patch.object(review, "_call", side_effect=unjailed):
                rec = self.run_review(reviewer, box)
                self.assertEqual((rec["note"], rec["findings"]), ("", []))
                argv, kw = seen[-1]
                self.assertTrue(kw["jailed"])
                _, writes, _, _ = split_jail(argv)
                env = env_file(self.bin / f"{reviewer}.env")
                tmp = Path(env["TMPDIR"])
                self.assertEqual(writes[0], str(tmp))  # 호출마다 새로 만든 임시 폴더가 쓰기 목록의 처음이다
                self.assertFalse(tmp.exists())  # 호출 뒤 지웠다
                self.assertEqual({name: env.get(name) for name in DROPPED}, dict.fromkeys(DROPPED))
                self.assertEqual(env["GH_TOKEN"], worker.GH_BLOCKED)
                self.assertEqual(env["GS_REVIEWER"], reviewer)
                self.assertEqual(self.out.read_text().strip(), ANSWER)
                args = (self.bin / f"{reviewer}.args").read_text().splitlines()
                if reviewer == "codex":
                    last = Path(args[args.index("--output-last-message") + 1])
                    self.assertEqual(last.parent, tmp)  # 실행 디렉터리(rdir)가 아니라 scratch에 썼다
                    self.assertEqual(Path(args[args.index("-C") + 1]), tmp)
                else:
                    self.assertNotIn("--sandbox", args)
                    self.assertFalse((self.wt / adapters.AGY_HOOK_FILE).exists())  # 리뷰 트리에 hook 파일을 쓰지 않는다


class CannotJailTest(Fixture):
    """가둘 수 없으면 리뷰어 호출이 리뷰 실패(ReviewError)가 아니라 SandboxAbort다."""

    def test_tree_under_write_path_aborts_without_launching(self):
        self.commit_in_wt()
        box = self.landlock()
        for reviewer in ("codex", "agy"):
            os.environ["GS_AGY"] = str(self.bin / "agy")
            with self.subTest(reviewer), mock.patch.object(adapters, "SHARED_TMP", self.root):
                with self.assertRaises(transient.SandboxAbort) as caught:
                    self.run_review(reviewer, box)
                self.assertEqual(str(caught.exception),
                                 f"리뷰 트리 {self.wt}가 landlock 쓰기 경로 {self.root} 아래라 읽기 전용으로 가둘 수 없다")
                self.assertFalse((self.bin / f"{reviewer}.calls").exists())
                self.assertFalse((self.out.parent / "reviewer.log").exists())  # 리뷰어를 띄우지 않았다
        with mock.patch.object(adapters, "SHARED_TMP", self.root):  # os 모드는 그대로 부른다
            self.assertEqual(self.run_review("codex", adapters.Sandbox())["note"], "")

    def test_jail_failed_line_aborts_review(self):
        """쓰기 경로와 거부 경로를 겹치게 해 실제 gs jail이 JAIL_FAILED 줄로 못 띄우게 한다."""
        self.commit_in_wt()
        box = self.landlock(secrets=[self.shared])
        with mock.patch.object(adapters, "SHARED_TMP", self.shared):
            with self.assertRaises(transient.SandboxAbort) as caught:
                self.run_review("codex", box)
        self.assertIn(f"codex 리뷰어를 landlock으로 가두지 못했다: {jail.JAIL_FAILED}쓰기 경로 {self.shared}가 거부 경로 "
                      f"{self.shared}와 같다", str(caught.exception))
        self.assertFalse((self.bin / "codex.calls").exists())

    def test_jail_failed_line_only_counts_for_jailed_calls(self):
        argv = [sys.executable, "-c", f"import sys; print({jail.JAIL_FAILED + 'x'!r}, file=sys.stderr); sys.exit(2)"]
        common = dict(prompt=None, cwd=self.root, env=dict(os.environ), timeout=60, family="codex")
        with self.assertRaises(transient.SandboxAbort) as caught:
            review._call(argv, log=self.root / "a.log", jailed=True, **common)
        self.assertIn(f": {jail.JAIL_FAILED}x(로그 ", str(caught.exception))
        with self.assertRaises(review.ReviewError) as caught:
            review._call(argv, log=self.root / "b.log", **common)
        self.assertNotIsInstance(caught.exception, transient.SandboxAbort)

    def test_worker_log_jail_failed_line(self):
        log = self.root / "worker.log"
        failed = f"{jail.JAIL_FAILED}쓸 수 없다(리눅스 아님)"
        cases = {"줄 처음": (f"Reading prompt from stdin...\n{failed}\n", failed),
                 "줄 중간": (f"echo {failed}\n", ""),
                 "codex 이벤트 안": ('{"type":"item.completed","item":{"type":"command_execution","aggregated_output":'
                                   f'"{failed}","exit_code":2}}}}\n', "")}
        for jailed, box in ((True, self.landlock()), (False, adapters.Sandbox())):
            proc = SimpleNamespace(adapter=adapters.Codex(MODELS, sandbox=box), job=SimpleNamespace(log=log))
            for name, (text, why) in cases.items():
                with self.subTest(name, jailed=jailed):
                    log.write_text(text)
                    expected = f"(codex)의 명령이 샌드박스에서 돌지 못했다: {why}" if why and jailed else ""
                    self.assertEqual(go._sandbox_end(SimpleNamespace(proc=proc)), expected)


class ReportHeadTest(unittest.TestCase):
    def test_line_follows_the_run_value(self):
        self.assertEqual(report.sandbox_line(SimpleNamespace(sandbox=adapters.Sandbox("landlock"))), LANDLOCK_LINE + "\n\n")
        self.assertEqual(report.sandbox_line(SimpleNamespace(sandbox=adapters.Sandbox())), "")
        self.assertEqual(report.sandbox_line(SimpleNamespace()), "")  # 옛 호출


def codex_ticket(tid):
    return f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: []\nmodel: codex\nreviewer: claude\n---\n## 목표\n{tid}\n'


class LandlockGoTest(support.GoTest):
    """gs go 전체. local.env(gitignore)는 주 레포에만 있다."""

    def setUp(self):
        super().setUp()
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        os.environ["HOME"] = str(self.home)  # GoTest의 환경 patch가 끝에 되돌린다
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n.goldstack/local.env\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "local.env는 gitignore")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        (self.repo / ".goldstack" / "local.env").write_text("GS_SANDBOX=landlock\n")
        (self.bin / "codex").write_text(FAKE_CODEX)
        (self.bin / "codex").chmod(0o755)

    def ticket(self, tid, body):
        (self.repo / f".goldstack/work/demo/tickets/{tid}-t.md").write_text(body)
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "ticket")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def overlap(self):
        """config `[sandbox] secrets`에 SHARED_TMP를 넣어 쓰기·거부가 겹치게 한다: 실제 gs jail이 JAIL_FAILED로 못 띄운다."""
        shared = self.root / "shared"
        shared.mkdir()
        cfg = self.repo / config.CONFIG_PATH
        cfg.write_text(cfg.read_text() + f'\n[sandbox]\nsecrets = ["{shared}"]\n')
        patch = mock.patch.object(adapters, "SHARED_TMP", shared)
        patch.start()
        self.addCleanup(patch.stop)
        return shared

    def assert_stopped(self, code, out, err, tid, reason):
        self.assertEqual(code, 3, out + err)
        self.assertIn(f"■ 샌드박스 중단 이유: {reason}", out)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn(f"gs-ticket: demo/{tid}", self.integration("log", "--format=%B", "gs/demo/integration"))
        st = state.load(self.rundir, "demo")
        ts = st.tickets[tid]
        self.assertEqual((ts.status, ts.failures, ts.reason), ("pending", 0, "중단(샌드박스)"), out)
        self.assertEqual(ts.review, {})  # 리뷰 실패로도, 지적 0건 리뷰로도 적지 않았다
        self.assertEqual(st.network["kind"], "sandbox")
        self.assertEqual(st.finish, {})
        return ts

    def test_codex_worker_jail_failed_stops_without_counting(self):
        os.environ.pop("GS_WORKER_CMD")
        shared = self.overlap()
        self.ticket("11", codex_ticket("11"))
        code, out, err = self.go("--only", "11")
        ts = self.assert_stopped(code, out, err, "11", f"[11] worker(codex)의 명령이 샌드박스에서 돌지 못했다: "
                                                       f"{jail.JAIL_FAILED}쓰기 경로 {shared}가 거부 경로 {shared}와 같다")
        self.assertEqual(ts.attempts, 1)  # 실패로 세지 않고 다시 띄우지 않았다
        self.assertFalse((self.bin / "codex.calls").exists())
        wt = self.rundir / "wt" / "11"
        self.assertTrue(wt.is_dir())
        self.assertFalse((wt / ".goldstack" / "local.env").exists())  # 모드는 주 레포에서 읽었다
        (script,) = self.rundir.glob("11/*/run.sh")
        text = script.read_text()
        self.assertIn(f"{q(sys.executable)} -m gs.cli jail --write {q(str(wt))} ", text)
        self.assertIn(f"--deny {q(str(self.repo / '.goldstack' / 'local.env'))} ", text)
        self.assertIn(" -- codex exec --json -s danger-full-access ", text)
        self.assertIn("\nunset CLAUDECODE CLAUDE_CODE_ENTRYPOINT GS_NOEQUALS " + " ".join(DROPPED) + "\n", text)

    def test_codex_review_tree_under_write_path_stops_without_review(self):
        os.environ.pop("GS_REVIEWER_CMD")
        with mock.patch.object(adapters, "SHARED_TMP", self.root):  # 레포가 쓰기 경로 아래다(예: /tmp 아래 레포)
            code, out, err = self.go("--only", "01")
        tree = self.rundir / "wt" / "01"
        self.assert_stopped(code, out, err, "01",
                            f"리뷰 트리 {tree}가 landlock 쓰기 경로 {self.root} 아래라 읽기 전용으로 가둘 수 없다")
        self.assertFalse((self.bin / "codex.calls").exists())  # 리뷰어를 띄우지 않았다

    def test_agy_review_jail_failed_stops_without_review(self):
        os.environ.pop("GS_REVIEWER_CMD")
        (self.bin / "agy").write_text(FAKE_AGY)  # PATH 앞(gs check는 PATH만 본다)
        (self.bin / "agy").chmod(0o755)
        shared = self.overlap()
        self.ticket("01", support.ticket("01").replace("reviewer: codex", "reviewer: agy"))
        code, out, err = self.go("--only", "01")
        ts = self.assert_stopped(code, out, err, "01", f"agy 리뷰어를 landlock으로 가두지 못했다: {jail.JAIL_FAILED}"
                                                       f"쓰기 경로 ")
        self.assertIn(f"{shared}가 거부 경로 {shared}와 같다", out)
        self.assertTrue(ts.network_resume["done"])  # 다음 gs go가 리뷰부터 잇는다
        self.assertFalse((self.bin / "agy.calls").exists())

    def test_every_review_round_gets_the_run_value(self):
        """첫 리뷰·재리뷰·수리 재리뷰 모두 실행 시작 때 계산한 값을 받는다(seam 리뷰어라 실제로 가두지는 않는다)."""
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            if grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"; then git rm -q BROKEN; git commit -qm repair; exit $?; fi
            if grep -q "^## 리뷰 지적(고칠 것)" "$GS_BRIEF"; then echo fixed > fix_file; git add -A; git commit -qm fix; exit 0; fi
            touch BROKEN; echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            prompt="$(cat)"
            if grep -q '"verdicts"' <<< "$prompt"; then
              echo '{"verdicts": [{"id": 1, "status": "resolved", "evidence": "확인"}], "findings": []}'
            elif [ ! -f "$here/reviewed" ]; then
              touch "$here/reviewed"
              echo '{"findings": [{"severity": "high", "location": "f", "claim": "FIX 값", "evidence": "재현"}]}'
            else echo '{"findings": []}'; fi
        '''))
        real, seen = review._ask_reviewer, []

        def spy(*args, **kwargs):
            seen.append((args[0], kwargs.get("sandbox")))
            return real(*args, **kwargs)

        with self.review_with([]), mock.patch.object(review, "_ask_reviewer", side_effect=spy):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual([p["phase"] for p in ts.phases],
                         ["worker", "review", "fix", "rereview", "verify", "repair", "rereview", "verify", "finish"])
        self.assertEqual(len(seen), 3, seen)  # 첫 리뷰, 재리뷰, 수리 재리뷰
        for reviewer, box in seen:
            self.assertEqual(reviewer, "codex")
            self.assertEqual(box.mode, "landlock")
            self.assertIn(self.repo / ".goldstack" / "local.env", box.denies["codex"])

    def test_report_head_line_in_landlock_mode(self):
        code, out, err = self.go("--only", "01")  # seam(GS_WORKER_CMD, GS_REVIEWER_CMD)은 가두지 않는다
        self.assertEqual(code, 0, out + err)
        self.assertTrue(self.final_report().startswith(f"# demo 결과\n\n{LANDLOCK_LINE}\n\n## Summary\n\n"),
                        self.final_report()[:300])

    def test_report_has_no_head_line_in_os_mode(self):
        (self.repo / ".goldstack" / "local.env").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        text = self.final_report()
        self.assertTrue(text.startswith("# demo 결과\n\n## Summary\n\n"), text[:300])
        self.assertNotIn("샌드박스:", text)


def outside_writes() -> Path | None:
    """쓰기 목록(/tmp, $TMPDIR) 밖에 시험 디렉터리를 둘 곳. 없으면 None."""
    blocked = [Path(os.path.realpath(p)) for p in ("/tmp", os.environ.get("TMPDIR") or "/tmp")]
    for base in ("/var/tmp", str(Path.home())):
        real = Path(os.path.realpath(base))
        if real.is_dir() and os.access(real, os.W_OK) and not any(real.is_relative_to(b) for b in blocked):
            return real
    return None


# 실제 jail 안의 가짜 codex·agy: 거부 경로를 읽어 보고, 리뷰 모양이면 리뷰 트리에 써 보고, worker 모양이면 커밋한다.
PROBE = """\
#!/bin/bash
cat > /dev/null
out=""
for arg in "$@"; do if [ "$prev" = --output-last-message ]; then out="$arg"; fi; prev="$arg"; done
if cat "$GS_SECRET" > /dev/null 2>&1; then echo SECRET_READ; else echo SECRET_DENIED; fi
if cat "$GS_LOCAL_ENV" > /dev/null 2>&1; then echo LOCAL_ENV_READ; else echo LOCAL_ENV_DENIED; fi
if [ "$GS_SHAPE" = review ]; then
  if (echo x > jail-write.txt) 2> /dev/null; then echo TREE_WRITTEN; else echo TREE_DENIED; fi
  if (echo y > a) 2> /dev/null; then echo TRACKED_WRITTEN; else echo TRACKED_DENIED; fi
  if (echo t > "$TMPDIR/probe") 2> /dev/null; then echo TMP_WRITTEN; else echo TMP_DENIED; fi
  if [ -n "$out" ]; then printf '%s\\n' '{"findings": []}' > "$out"; else echo '{"findings": []}'; fi
  exit 0
fi
echo x > jailed.txt && git add jailed.txt && git commit -qm jailed && echo COMMITTED
"""


@unittest.skipUnless(jail.abi() >= 1, "Landlock을 쓸 수 없는 머신(리눅스가 아니거나 커널이 지원하지 않음)")
class RealLandlockTest(unittest.TestCase):
    """실제 Landlock(리눅스 CI). ABI 1은 경로 `truncate(2)`·`chmod`를 막지 못하므로 쓰기는 `open` 기준으로만 본다."""

    def setUp(self):
        base = outside_writes()
        if base is None:
            self.skipTest("쓰기 목록(/tmp, $TMPDIR) 밖에 시험 디렉터리를 둘 곳이 없다")
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        home, bin_ = self.root / "home", self.root / "bin"
        home.mkdir()
        bin_.mkdir()
        for name in ("codex", "agy"):
            (bin_ / name).write_text(PROBE)
            (bin_ / name).chmod(0o755)
        self.repo = self.root / "repo"
        self.local_env = self.repo / ".goldstack" / "local.env"
        self.secret = self.root / "secret.txt"
        os.environ.update(GIT_ENV, HOME=str(home), PATH=f"{bin_}{os.pathsep}{os.environ['PATH']}",
                          GS_SECRET=str(self.secret), GS_LOCAL_ENV=str(self.local_env), GS_AGY=str(bin_ / "agy"))
        for name in ("GS_REVIEWER_CMD", "GS_WORKER_CMD", "CODEX_HOME"):
            os.environ.pop(name, None)
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / "a").write_text("a\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        self.local_env.parent.mkdir()
        self.local_env.write_text("GS_SANDBOX=landlock\n")
        self.secret.write_text("s3cret\n")
        self.wt = self.root / "wt"
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "gs/demo/01", str(self.wt))
        self.box = go._sandbox(self.repo, SimpleNamespace(sandbox=SimpleNamespace(secrets=[str(self.secret)])))
        self.assertEqual(self.box.mode, "landlock")

    def test_codex_worker_commits_and_cannot_read_denied_paths(self):
        brief = self.root / "brief.md"
        brief.write_text("brief\n")
        inp = WorkerInput(brief=brief, worktree=self.wt, log=self.root / "worker.log")
        command = adapters.Codex(MODELS, sandbox=self.box).command(inp)
        cp = subprocess.run(["bash", "-c", command], cwd=self.wt, env={**os.environ, "GS_SHAPE": "worker"},
                            capture_output=True, text=True, timeout=120)
        self.assertNotIn(jail.JAIL_FAILED, cp.stderr)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(cp.stdout.split(), ["SECRET_DENIED", "LOCAL_ENV_DENIED", "COMMITTED"], cp.stderr)
        self.assertEqual(sh(self.wt, "git", "log", "-1", "--format=%s", "gs/demo/01"), "jailed")

    def test_reviewers_cannot_write_the_review_tree(self):
        os.environ["GS_SHAPE"] = "review"
        cfg = SimpleNamespace(models=MODELS, timeouts=config.TimeoutsConfig(30, 10, 60))
        for reviewer in ("codex", "agy"):
            with self.subTest(reviewer):
                rdir = self.root / f"rdir-{reviewer}"
                rdir.mkdir()
                text = review._ask_reviewer(reviewer, self.wt, "prompt", rdir, 120, cfg, None, config.ModelEffort(""),
                                            sandbox=self.box)
                stdout = next(rdir.glob("reviewer*.stdout")).read_text()
                self.assertNotIn(jail.JAIL_FAILED, (rdir / "reviewer.log").read_text())
                self.assertEqual(stdout.split()[:5], ["SECRET_DENIED", "LOCAL_ENV_DENIED", "TREE_DENIED", "TRACKED_DENIED",
                                                      "TMP_WRITTEN"], stdout)
                self.assertIn(ANSWER, text)
                self.assertIn(ANSWER, (rdir / "review.txt").read_text())
                self.assertFalse((self.wt / "jail-write.txt").exists())
                self.assertEqual((self.wt / "a").read_text(), "a\n")


if __name__ == "__main__":
    unittest.main()
