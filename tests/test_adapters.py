"""모델 어댑터(05): 어댑터별 명령 조립, 종료 판정, agy 차단 장치 확인과 거부, agy hook 번역.

실제 codex·agy 호출은 하지 않는다. agy는 가짜 실행 파일(GS_AGY)로 바꿔 끼운다.
"""
import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, cli, config, hook_agy, streamfmt, worker
from gs.adapters import AdapterError, WorkerInput
from gs.feature import Ticket

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import FAKE_GH, SPEC, sh  # noqa: E402
from support import isolate_git_env

MODELS = config.ModelsConfig("judge-test", "review-test", "agy-test", "")

GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

# `agy -p /hooks`에 gs hook 줄을 내는 가짜 agy. 그 밖의 호출은 worker처럼 커밋하고 stream-json을 낸다.
# FAKE_AGY_MODE: ok | nohook | error | nocommit
FAKE_AGY = r"""#!/bin/bash
mode="${FAKE_AGY_MODE:-ok}"
if [ "$1 $2" = "-p /hooks" ]; then
  if [ "$mode" != nohook ] && grep -q goldstack-worker-guard .agents/hooks.json 2>/dev/null; then
    printf 'herdr\tenabled\tPreInvocation\t-\tcommand\tbash x.sh\n'
    printf 'goldstack-worker-guard\tenabled\tPreToolUse\t*\tcommand\t%s\n' "$(sed -n 's/.*"command": "\(.*\)".*/\1/p' .agents/hooks.json)"
  fi
  exit 0
fi
echo "$@" > "$(dirname "$0")/agy.args"
echo '{"event":"init","init":{"model":"gemini-4-argon-high","permission_mode":"always-proceed"}}'
if [ "$mode" != nocommit ]; then echo "$GS_TICKET $GS_ROLE" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"; fi
if [ "$mode" = error ]; then echo '{"event":"result","result":{"status":"ERROR","finished_reason":"error"}}'; exit 0; fi
echo '{"event":"result","result":{"status":"SUCCESS","response":"done","num_turns":3}}'
"""


def git_repo_with_worktree(root: Path, branch="gs/demo/01"):
    repo = root / "repo"
    repo.mkdir()
    sh(repo, "git", "init", "-q", "-b", "main")
    (repo / "a").write_text("a\n")
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-qm", "init")
    wt = root / "wt"
    sh(repo, "git", "worktree", "add", "-q", "-b", branch, str(wt))
    return repo, Path(os.path.realpath(wt))


class Base(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        patch = mock.patch.dict(os.environ, GIT_ENV)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_WORKER_CMD", None)

    def fake_agy(self, mode="ok"):
        path = self.root / "bin" / "agy"
        path.parent.mkdir(exist_ok=True)
        path.write_text(FAKE_AGY)
        path.chmod(0o755)
        os.environ["GS_AGY"] = str(path)
        os.environ["FAKE_AGY_MODE"] = mode
        self.addCleanup(os.environ.pop, "GS_AGY", None)
        self.addCleanup(os.environ.pop, "FAKE_AGY_MODE", None)
        return path


class CommandTest(Base):
    """어댑터별 명령 조립. 같은 입력(brief, worktree, 로그)에서 명령을 만든다."""

    def setUp(self):
        super().setUp()
        self.repo, self.wt = git_repo_with_worktree(self.root)
        self.inp = WorkerInput(brief=self.root / "run dir" / "brief.md", worktree=self.wt,
                               log=self.root / "run dir" / "worker.log")

    def argv(self, cmd):
        return shlex.split(cmd.replace("< ", "<"))

    def test_claude(self):
        cmd = adapters.Claude(MODELS).command(self.inp)
        self.assertTrue(cmd.startswith("claude -p --output-format stream-json"))
        self.assertIn("--permission-mode bypassPermissions", cmd)
        self.assertIn('--disallowedTools "Bash(git push *)" "Bash(gh *)"', cmd)
        self.assertTrue(cmd.endswith(f"< {shlex.quote(str(self.inp.brief))}"), cmd)  # 공백 경로도 인용

    def test_codex(self):
        cmd = adapters.Codex(MODELS).command(self.inp)
        self.assertTrue(cmd.startswith("codex exec --json -s workspace-write "), cmd)
        self.assertIn("-c sandbox_workspace_write.network_access=false", cmd)  # push가 나갈 길을 막는다
        self.assertNotIn("danger", cmd)
        argv = self.argv(cmd)
        self.assertEqual(argv[argv.index("-C") + 1], str(self.wt))
        adds = [argv[i + 1] for i, a in enumerate(argv) if a == "--add-dir"]
        common = os.path.realpath(self.repo / ".git")
        self.assertEqual(adds, [f"{common}/worktrees/wt", f"{common}/objects", f"{common}/refs/heads/gs/demo",
                                f"{common}/logs/refs/heads/gs/demo"])
        self.assertTrue(all(Path(d).is_dir() for d in adds))
        self.assertNotIn(common, [os.path.realpath(d) for d in adds])  # .git 전체는 열지 않는다
        self.assertIn(adapters.Codex.NOTE, argv)  # sandbox에서 못 돈 검증은 gs가 다시 돈다
        self.assertEqual(argv[-1], "<" + str(self.inp.brief))

    def test_codex_prepare_needs_git_worktree(self):
        with self.assertRaises(AdapterError):
            adapters.Codex(MODELS).prepare(WorkerInput(self.root / "b", self.root / "nogit", self.root / "l"))

    def test_agy_follows_research_recommendation(self):
        cmd = adapters.Agy(MODELS).command(self.inp)
        argv = shlex.split(cmd)
        self.assertEqual(argv[:2], ["agy", "-p"])
        self.assertEqual(argv[2], f"$(cat {shlex.quote(str(self.inp.brief))})")  # brief 전문을 프롬프트로(셸이 펼친다)
        self.assertIn('"$(cat ', cmd)
        for flag in ("--output-format", "--dangerously-skip-permissions", "--settings", "--model"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertEqual(argv[argv.index("--model") + 1], MODELS.agy)
        for bad in ("--mode", "--sandbox", "--print-timeout", "--effort"):  # 11 §6: 넣지 않는다
            self.assertNotIn(bad, argv)
        deny = json.loads(argv[argv.index("--settings") + 1])["permissions"]["deny"]
        for rule in ("command(git push)", "command(gh pr create)", "command(gh pr merge)", "command(gh api)"):
            self.assertIn(rule, deny)

    def test_every_adapter_sets_worker_role(self):
        for cls in (adapters.Claude, adapters.Codex, adapters.Agy):
            env = cls(MODELS).env(self.inp)
            self.assertEqual(env["GS_ROLE"], "worker", cls)
            self.assertEqual(env["GS_WORKTREE"], str(self.wt))

    def test_script_exports_role_and_runs_adapter_command(self):
        rundir = self.root / "run"
        rundir.mkdir()
        t = Ticket(id="01", title="t", blocked_by=[], model="codex", reviewer="claude", path=Path("01-t.md"))
        job = worker.Job(ticket=t, worktree=self.wt, rundir=rundir)
        for cls in (adapters.Claude, adapters.Codex, adapters.Agy):
            a = cls(MODELS)
            worker.write_script(job, a)
            text = job.script.read_text()
            self.assertIn("export GS_ROLE=worker", text, cls)
            self.assertIn(f"export GS_WORKTREE={shlex.quote(str(self.wt))}", text)
            self.assertIn(f"( {a.command(job.input)} )", text)

    def test_for_model(self):
        self.assertIsInstance(adapters.for_model("codex", MODELS), adapters.Codex)
        self.assertIsInstance(adapters.for_model("agy", MODELS), adapters.Agy)
        self.assertIsInstance(adapters.for_model("claude", MODELS), adapters.Claude)
        with self.assertRaises(AdapterError):
            adapters.for_model("gpt", MODELS)
        with mock.patch.dict(os.environ, {"GS_WORKER_CMD": "bash w.sh"}):
            a = adapters.for_model("agy", MODELS)
            self.assertEqual((a.name, a.command(self.inp)), ("custom", "bash w.sh"))


class AgyOutcomeTest(Base):
    """agy 끝 판정: 종료 0 + 마지막 result의 status SUCCESS + finished_reason 없음."""

    def outcome(self, code, *lines):
        log = self.root / "worker.log"
        log.write_text("".join((json.dumps(x) if isinstance(x, dict) else x) + "\n" for x in lines))
        return adapters.Agy(MODELS).outcome(code, WorkerInput(self.root / "b", self.root, log))

    def test_success(self):
        self.assertEqual(self.outcome(0, {"event": "init"}, {"event": "result", "result": {"status": "SUCCESS"}}),
                         (0, ""))

    def test_exit_zero_is_not_enough(self):
        code, note = self.outcome(0, {"event": "init"})
        self.assertEqual((code, note), (1, "agy: result 이벤트가 없다"))
        code, note = self.outcome(0, {"event": "result", "result": {"status": "ERROR"}})
        self.assertEqual(code, 1)
        self.assertIn("status ERROR", note)
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS",
                                                                     "finished_reason": "print_timeout"}})
        self.assertEqual(code, 1)
        self.assertIn("print_timeout", note)

    def test_silent_downgrade_and_denials_are_noted(self):
        code, note = self.outcome(
            0, "warning: --mode auto is not available for this account; continuing in the default mode.",
            {"event": "step_update", "step_update": {"state": "ERROR", "step_type": "tool"}},
            {"event": "result", "result": {"status": "SUCCESS", "denied_actions": [{"action": "command"}]}})
        self.assertEqual(code, 0)  # 커밋 유무는 gs가 따로 본다
        self.assertIn("--mode auto is not available", note)
        self.assertIn("ERROR 단계 1개", note)
        self.assertIn("자동 거부: command", note)

    def test_nonzero_exit_kept(self):
        self.assertEqual(self.outcome(1, {"event": "result", "result": {"status": "ERROR",
                                                                         "finished_reason": "interrupted"}})[0], 1)

    def test_last_result_wins_and_garbage_is_ignored(self):
        code, _ = self.outcome(0, "not json", "[1]", {"event": "result", "result": {"status": "ERROR"}},
                               {"event": "result", "result": {"status": "SUCCESS"}})
        self.assertEqual(code, 0)

    def test_malformed_last_result_does_not_reuse_earlier_success(self):  # 리뷰 05 #3
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS"}},
                                  {"event": "result", "result": []})
        self.assertEqual(code, 1)
        self.assertIn("result", note)

    def test_error_step_after_success_fails(self):  # 리뷰 05 #3
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS"}},
                                  {"event": "step_update", "step_update": {"state": "ERROR", "step_type": "tool"}})
        self.assertEqual(code, 1)
        self.assertIn("마지막 이벤트", note)

    def test_truncated_last_event_fails(self):
        code, _ = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS"}}, '{"event":"res')
        self.assertEqual(code, 1)

    def test_trailing_stderr_text_after_result_is_ignored(self):
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS"}},
                                  "terminating 1 background task(s) on exit")
        self.assertEqual((code, note), (0, ""))

    def test_malformed_denied_actions_is_failure_not_exception(self):  # 리뷰 05 #4
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS", "denied_actions": 1}})
        self.assertEqual(code, 1)
        self.assertIn("denied_actions", note)
        code, note = self.outcome(0, {"event": "result", "result": {"status": "SUCCESS", "denied_actions": [1]}})
        self.assertEqual(code, 1)
        self.assertIn("denied_actions", note)


class AgyGuardTest(Base):
    """차단 장치: worktree에 gs hook을 걸고, agy가 실제로 거는지 확인한다. 안 걸리면 거부한다."""

    def setUp(self):
        super().setUp()
        self.repo, self.wt = git_repo_with_worktree(self.root)
        self.inp = WorkerInput(self.root / "brief.md", self.wt, self.root / "worker.log")

    def test_prepare_installs_hook_outside_git(self):
        self.fake_agy("ok")
        adapters.Agy(MODELS).prepare(self.inp)
        spec = json.loads((self.wt / ".agents" / "hooks.json").read_text())
        h = spec["goldstack-worker-guard"]["PreToolUse"][0]
        self.assertEqual(h["matcher"], "*")
        self.assertTrue(h["hooks"][0]["command"].endswith("-m gs.cli hook agy-pretooluse"))
        self.assertEqual(sh(self.wt, "git", "status", "--porcelain"), "")  # 커밋에 섞이지 않는다
        adapters.Agy(MODELS).prepare(self.inp)  # 다시 해도 exclude 줄은 하나
        exclude = Path(sh(self.wt, "git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
        self.assertEqual(exclude.read_text().splitlines().count("/.agents/hooks.json"), 1)

    def test_refused_when_agy_does_not_load_hook(self):
        self.fake_agy("nohook")
        with self.assertRaisesRegex(AdapterError, "agy 차단 장치가 없다.*구현 worker로 띄우지 않는다"):
            adapters.Agy(MODELS).prepare(self.inp)

    def test_refused_when_agy_missing(self):
        os.environ["GS_AGY"] = str(self.root / "no-agy")
        self.addCleanup(os.environ.pop, "GS_AGY", None)
        with self.assertRaisesRegex(AdapterError, "없다"):
            adapters.Agy(MODELS).prepare(self.inp)

    def test_refused_when_hook_command_does_not_block(self):
        self.fake_agy("ok")
        with mock.patch.object(adapters, "agy_hook_command", return_value="echo hook agy-pretooluse"):
            with self.assertRaisesRegex(AdapterError, "막지 않았다"):
                adapters.Agy(MODELS).prepare(self.inp)

    def test_refused_when_repo_tracks_hook_file(self):
        self.fake_agy("ok")
        (self.wt / ".agents").mkdir()
        (self.wt / ".agents" / "hooks.json").write_text("{}")
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "commit", "-qm", "own hooks")
        with self.assertRaisesRegex(AdapterError, "추적"):
            adapters.Agy(MODELS).prepare(self.inp)

    def test_refused_when_agents_is_tracked_symlink(self):  # 리뷰 05 #1: 링크를 따라 밖의 파일을 덮어쓰지 않는다
        self.fake_agy("ok")
        shared = self.root / "shared" / "agents"
        shared.mkdir(parents=True)
        (shared / "hooks.json").write_text("original\n")
        (self.wt / ".agents").symlink_to(shared)
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "commit", "-qm", "agents link")
        with self.assertRaisesRegex(AdapterError, "심볼릭 링크"):
            adapters.Agy(MODELS).prepare(self.inp)
        self.assertEqual((shared / "hooks.json").read_text(), "original\n")

    def test_refused_when_hooks_file_is_symlink(self):
        self.fake_agy("ok")
        outside = self.root / "outside.json"
        outside.write_text("original\n")
        (self.wt / ".agents").mkdir()
        (self.wt / ".agents" / "hooks.json").symlink_to(outside)
        with self.assertRaisesRegex(AdapterError, "심볼릭 링크"):
            adapters.Agy(MODELS).prepare(self.inp)
        self.assertEqual(outside.read_text(), "original\n")

    def test_refused_when_agents_is_a_file(self):
        self.fake_agy("ok")
        (self.wt / ".agents").write_text("x\n")
        sh(self.wt, "git", "add", "-A")
        sh(self.wt, "git", "commit", "-qm", "agents file")
        with self.assertRaisesRegex(AdapterError, "디렉터리가 아니다"):
            adapters.Agy(MODELS).prepare(self.inp)
        self.assertEqual((self.wt / ".agents").read_text(), "x\n")


class AgyHookTest(unittest.TestCase):
    """`gs hook agy-pretooluse`: agy 입력 → 09 decide() → agy 출력 JSON."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = Path(os.path.realpath(self.tmp.name)) / "wt"
        self.wt.mkdir()
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": "/home/u"}

    def payload(self, name, prompt="", **args):
        return {"conversationId": "c", "workspacePaths": [str(self.wt)], "lastUserInput": prompt,
                "toolCall": {"name": name, "args": args}}

    def run_hook(self, payload, env):
        out = io.StringIO()
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        code = hook_agy.main(stdin=stdin, stdout=out, env=env)
        return code, json.loads(out.getvalue())

    def verdict(self, payload, env=None):
        code, out = self.run_hook(payload, self.env if env is None else env)
        self.assertEqual(code, 0)  # agy는 종료 코드가 아니라 stdout JSON으로 판정한다
        return out["decision"]

    def test_shell_commands(self):
        for cmd in ["git push origin HEAD:v1", "git -C . push", "sh -c 'git push'", "gh pr merge 3",
                    "cd . && git push", "echo y > /etc/outside.txt"]:
            self.assertEqual(self.verdict(self.payload("run_command", CommandLine=cmd)), "deny", cmd)
        for cmd in ["git add -A && git commit -qm t", "uv run python -m unittest discover -s tests", "ls -la"]:
            self.assertEqual(self.verdict(self.payload("run_command", CommandLine=cmd)), "allow", cmd)

    def test_deny_has_reason(self):
        _, out = self.run_hook(self.payload("run_command", CommandLine="git push"), self.env)
        self.assertIn("git push", out["reason"])
        self.assertIn("gs가 막음", out["reason"])

    def test_prompt_is_not_inspected(self):  # 11 E3b: brief의 금지 문구로 정상 명령을 막지 않는다
        p = self.payload("run_command", prompt="push, PR은 하지 않는다: git push 금지", CommandLine="git status")
        self.assertEqual(self.verdict(p), "allow")

    def test_file_tools(self):
        self.assertEqual(self.verdict(self.payload("write_file", Path="/etc/hosts", Content="x")), "deny")
        self.assertEqual(self.verdict(self.payload("edit_file", Path="/home/u/.zshrc")), "deny")
        self.assertEqual(self.verdict(self.payload("write_to_file", TargetFile="/etc/x")), "deny")
        self.assertEqual(self.verdict(self.payload("write_file", Path=str(self.wt / "a.py"), Content="")), "allow")
        self.assertEqual(self.verdict(self.payload("edit_file", Path=str(self.wt / "README.md"))), "allow")
        self.assertEqual(self.verdict(self.payload("read_file", Path="/home/u/.ssh/id_rsa")), "deny")
        self.assertEqual(self.verdict(self.payload("read_file", Path=".goldstack/local.env")), "deny")
        self.assertEqual(self.verdict(self.payload("read_file", Path="/etc/hosts")), "allow")
        self.assertEqual(self.verdict(self.payload("search_web", Query="git push")), "allow")

    def test_hook_config_is_protected(self):
        for p in [self.payload("write_file", Path=str(self.wt / ".agents" / "hooks.json"), Content="{}"),
                  self.payload("edit_file", Path=".agents/hooks.json"),
                  self.payload("run_command", CommandLine="echo {} > .agents/hooks.json"),
                  self.payload("run_command", CommandLine="rm -rf .agents")]:
            self.assertEqual(self.verdict(p), "deny", p)
        self.assertEqual(self.verdict(self.payload("run_command", CommandLine="ls agents_notes")), "allow")

    def test_worktree_from_workspace_when_env_missing(self):
        env = {"GS_ROLE": "worker", "HOME": "/home/u"}
        self.assertEqual(self.verdict(self.payload("write_file", Path=str(self.wt / "a"), Content=""), env), "allow")
        self.assertEqual(self.verdict(self.payload("write_file", Path="/etc/x", Content=""), env), "deny")

    def test_no_role_allows_without_reading(self):
        for env in [{}, {"GS_ROLE": "reviewer"}]:
            self.assertEqual(self.verdict("not json", env), "allow")
            self.assertEqual(self.verdict(self.payload("run_command", CommandLine="git push"), env), "allow")

    def test_bad_input_is_denied_for_worker(self):
        self.assertEqual(self.verdict("not json"), "deny")
        self.assertEqual(self.verdict("[1]"), "deny")

    def test_cli_entrypoint(self):
        env = {**os.environ, **self.env}
        cp = subprocess.run([sys.executable, "-m", "gs.cli", "hook", "agy-pretooluse"], env=env, text=True,
                            input=json.dumps(self.payload("run_command", CommandLine="git push")),
                            capture_output=True)
        self.assertEqual((cp.returncode, json.loads(cp.stdout)["decision"]), (0, "deny"), cp.stderr)


AGY_TICKET = '---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: []\nmodel: {model}\nreviewer: claude\n---\n## 목표\n{tid}\n'


class AgyGoAndCheckTest(Base):
    """`gs go`가 agy 티켓을 어댑터로 띄우고 판정한다. 차단 장치가 없으면 거부하고, `gs check`는 경고한다."""

    def setUp(self):
        super().setUp()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("claude", "codex"):
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 1\n")
            path.chmod(0o755)
        (self.bin / "gh").write_text("#!/bin/bash\n" + FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                                            "GS_RUNNER": "subprocess", "GS_GH": str(self.bin / "gh"),
                                            "GS_JUDGE": "/usr/bin/true",
                                            "GS_REVIEWER_CMD": "echo '{\"findings\": []}'"})
        patch.start()
        self.addCleanup(patch.stop)
        remote = self.root / "remote.git"
        sh(self.root, "git", "init", "-q", "--bare", "-b", "main", str(remote))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n")
        tickets = self.repo / ".goldstack/work" / "demo" / "tickets"
        tickets.mkdir(parents=True)
        (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text(SPEC)
        (tickets / "01-t.md").write_text(AGY_TICKET.format(tid="01", model="agy"))
        (tickets / "02-t.md").write_text(AGY_TICKET.format(tid="02", model="codex"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        url = "https://github.com/test/origin.git"
        sh(self.repo, "git", "remote", "add", "origin", url)
        sh(self.repo, "git", "config", f"url.{remote}.insteadOf", url)
        sh(self.repo, "git", "push", "-q", "-u", "origin", "main")

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), *args])
        return code, out.getvalue(), err.getvalue()

    def state(self):
        return json.loads((self.repo / ".goldstack/work" / "demo" / "run" / "state.json").read_text())["tickets"]

    def test_go_runs_agy_through_adapter(self):
        self.fake_agy("ok")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("(agy, ", out)
        args = (self.bin / "agy.args").read_text()
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertIn("# 티켓 01", args)  # brief 전문이 프롬프트로 들어갔다
        log = sh(self.repo, "git", "show", "origin/main:file_01")
        self.assertEqual(log, "01 worker")  # worker 환경에 GS_ROLE=worker
        self.assertNotIn(".agents/hooks.json", sh(self.repo, "git", "ls-tree", "-r", "--name-only", "origin/main"))

    def test_go_fails_agy_on_error_result_despite_exit_zero(self):
        self.fake_agy("error")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn("agy: result status ERROR", self.state()["01"]["reason"])

    def test_go_refuses_agy_without_guard(self):
        self.fake_agy("nohook")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 1, out + err)
        reason = self.state()["01"]["reason"]
        self.assertIn("agy 차단 장치가 없다", reason)
        self.assertFalse((self.bin / "agy.args").exists())  # worker를 띄우지 않았다

    def test_check_warns_without_guard(self):
        self.fake_agy("nohook")
        code, out, err = self.cli("check", "demo")
        self.assertEqual(code, 0, out + err)  # 경고다(오류 아님)
        self.assertIn("경고: agy: 차단 장치가 없다", err)
        self.assertIn("agy 티켓(01)", err)

    def test_check_quiet_with_guard_or_without_agy_tickets(self):
        self.fake_agy("ok")
        code, out, err = self.cli("check", "demo")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("차단 장치가 없다", err)
        self.fake_agy("nohook")
        code, out, err = self.cli("check", "demo", "--only", "02")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("차단 장치가 없다", err)  # 범위에 agy 티켓이 없다


class StreamfmtTest(unittest.TestCase):
    """pane에 보이는 출력: codex·agy 이벤트도 읽을 수 있게(실제 로그에서 뽑은 모양)."""

    def r(self, ev):
        return streamfmt.render(json.dumps(ev))

    def test_codex(self):
        self.assertEqual(self.r({"type": "item.completed", "item": {"type": "agent_message", "text": "완료\n"}}),
                         "완료")
        self.assertEqual(self.r({"type": "item.completed", "item": {
            "type": "command_execution", "command": "/bin/zsh -lc 'python3 -m unittest'", "exit_code": 0}}),
            "→ /bin/zsh -lc 'python3 -m unittest' (종료 0)")
        self.assertIsNone(self.r({"type": "item.started", "item": {"type": "command_execution"}}))
        self.assertEqual(self.r({"type": "turn.completed", "usage": {}}), "■ 결과: turn.completed")

    def test_agy(self):
        self.assertIn("model=gemini-4-argon-high", self.r({"event": "init", "init": {"model": "gemini-4-argon-high"}}))
        tool = {"event": "step_update", "step_update": {"state": "DONE", "step_type": "tool", "tool_name": "run_command",
                                                        "tool_info": {"parameters": {"CommandLine": "git status"}}}}
        self.assertEqual(self.r(tool), "→ run_command git status")
        tool["step_update"].update(state="ERROR", tool_info={"parameters": {"CommandLine": "git push"},
                                                             "error": {"message": "denied by pre-tool hook"}})
        self.assertEqual(self.r(tool), "! run_command git push — denied by pre-tool hook")
        tool["step_update"]["state"] = "ACTIVE"
        self.assertIsNone(self.r(tool))
        self.assertEqual(self.r({"event": "result", "result": {"status": "SUCCESS", "response": "끝"}}),
                         "■ 결과: SUCCESS\n끝")

    def test_claude_unchanged(self):
        self.assertEqual(self.r({"type": "system", "subtype": "init", "model": "m", "cwd": "/w"}),
                         "■ 시작: model=m cwd=/w")


if __name__ == "__main__":
    unittest.main()
