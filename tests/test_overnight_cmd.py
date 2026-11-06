"""`gs overnight arm|disarm`과 `gs hook permissionrequest`: 켠 세션에서만 창이 거부로 바뀐다.

세션 판정은 진짜 `ps`로 시험한다. `FakeClaude`는 argv[0]이 `claude`인 진짜 프로세스고, 그 자식으로 진짜 `gs`를 돌린다.
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

from gs import cli, hook, overnight
from support import isolate_git_env

REPO = Path(__file__).resolve().parents[1]
GS = [sys.executable, "-m", "gs.cli"]
# 줄마다 셸 명령 하나를 돌린다. 돌리는 자식은 fork 뒤 바로 exec되어 이 이름을 물려받지 않는다
LOOP = 'while IFS= read -r line; do eval "$line"; done'


class FakeClaude:
    """argv[0]이 `claude`인 살아 있는 프로세스 하나 = Claude 세션 하나. `run`은 그 자식으로 명령을 돌린다(Bash 도구·hook과 같은 자리)."""

    def __init__(self, test, env=None):
        self.dir = Path(tempfile.mkdtemp(dir=test.base))
        self.proc = subprocess.Popen(["/bin/bash", "-c", 'exec -a claude /bin/bash -c "$0"', LOOP],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                     env=env or test.session_env)
        self.pid = self.proc.pid
        test.addCleanup(self.close)

    def run(self, argv, cwd, stdin=""):
        """(종료 코드, stdout, stderr)."""
        (self.dir / "in").write_text(stdin)
        line = (f"cd {shlex.quote(str(cwd))}; {shlex.join(str(a) for a in argv)} "
                f"<{self.dir}/in >{self.dir}/out 2>{self.dir}/err; echo $?\n")
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        code = int(self.proc.stdout.readline())
        return code, (self.dir / "out").read_text(), (self.dir / "err").read_text()

    def close(self):
        if not self.proc.stdin.closed:
            self.proc.stdin.close()
        self.proc.wait()
        self.proc.stdout.close()


class OvernightTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        self.repo = self.base / "repo"
        self.git_init(self.repo)
        self.other = self.base / "other"
        self.git_init(self.other)
        self.session_env = {k: v for k, v in os.environ.items() if k != "GS_ROLE"}
        self.session_env["PYTHONPATH"] = os.pathsep.join([str(REPO / "src"), self.session_env.get("PYTHONPATH", "")])

    def git_init(self, path):
        path.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=self.repo, check=True,
                       capture_output=True)

    def payload(self, cwd=None, tool="Bash", **inp):
        return json.dumps({"session_id": "s", "hook_event_name": "PermissionRequest", "cwd": str(cwd or self.repo),
                           "tool_name": tool, "tool_input": inp or {"command": "git status"}})

    def arm(self, session, cwd=None):
        code, out, err = session.run([*GS, "overnight", "arm"], cwd or self.repo)
        self.assertEqual(code, 0, err)
        return out

    def hook(self, session, cwd=None, stdin=None, **inp):
        code, out, err = session.run([*GS, "hook", "permissionrequest"], cwd or self.repo,
                                     self.payload(cwd, **inp) if stdin is None else stdin)
        self.assertEqual((code, err), (0, ""))
        return out

    def assertWindow(self, session, cwd=None, **kw):
        self.assertEqual(self.hook(session, cwd, **kw), "")

    def denial(self, out):
        data = json.loads(out)
        self.assertEqual(set(data), {"hookSpecificOutput"})
        spec = data["hookSpecificOutput"]
        self.assertEqual(set(spec), {"hookEventName", "decision"})
        self.assertEqual(spec["hookEventName"], "PermissionRequest")
        self.assertEqual(set(spec["decision"]), {"behavior", "message"})
        self.assertEqual(spec["decision"]["behavior"], "deny")
        return spec["decision"]["message"]

    def log(self, repo=None):
        path = (repo or self.repo) / overnight.DENIED_LOG
        return path.read_text() if path.exists() else ""

    # ---- 켠 세션만
    def test_armed_session_is_denied_with_call_and_next_step(self):
        session = FakeClaude(self)
        self.assertIn(str(session.pid), self.arm(session))
        message = self.denial(self.hook(session, command="git push origin HEAD"))
        self.assertIn("Bash(git)", message)
        self.assertIn("다음 일로 넘어간다", message)
        self.assertIn(overnight.DENIED_LOG, message)

    def test_other_session_in_same_repo_gets_the_window(self):
        armed, other = FakeClaude(self), FakeClaude(self)
        self.arm(armed)
        self.assertWindow(other)
        self.assertEqual(self.log(), "")
        self.denial(self.hook(armed))  # 옆 세션을 본 뒤에도 켠 세션은 그대로다

    def test_other_repo_gets_the_window(self):
        armed, other = FakeClaude(self), FakeClaude(self)
        self.arm(armed)
        self.assertWindow(other, self.other)
        self.assertWindow(armed, self.other)  # 표시는 켠 레포에만 있다
        self.assertEqual(self.log(self.other), "")
        self.assertFalse((self.other / overnight.OVERNIGHT_DIR).exists())

    def test_session_without_marker_gets_the_window_and_writes_nothing(self):
        session = FakeClaude(self)
        self.assertWindow(session)
        self.assertFalse((self.repo / overnight.OVERNIGHT_DIR).exists())

    def test_nested_claude_does_not_inherit_the_mark(self):
        """켠 코디네이터가 띄운 worker claude. 가장 가까운 조상은 worker 자신이다."""
        table = {100: overnight.Process(50, 1000, "/bin/zsh -c gs hook"),
                 50: overnight.Process(40, 1000, "claude -p --model opus"),
                 40: overnight.Process(30, 900, "bash run.sh"),
                 30: overnight.Process(20, 800, "gs go f"),
                 20: overnight.Process(1, 700, "claude")}
        with mock.patch("os.getppid", return_value=100):
            self.assertEqual(overnight.current_session(table), overnight.Session(50, 1000))
        with mock.patch("os.getppid", return_value=30):
            self.assertEqual(overnight.current_session(table), overnight.Session(20, 700))

    def test_session_walk_survives_missing_rows_and_cycles(self):
        with mock.patch("os.getppid", return_value=5):
            self.assertIsNone(overnight.current_session({}))
            self.assertIsNone(overnight.current_session({5: overnight.Process(6, 1, "a"), 6: overnight.Process(5, 1, "b")}))

    def test_claude_process_forms(self):
        for command in ["claude", "claude -p --model opus", "/Users/x/.local/bin/claude --resume",
                        "/Users/x/.local/share/claude/versions/2.1.319 -p", "node /usr/local/bin/claude",
                        "/opt/node/bin/node /x/@anthropic-ai/claude-code/cli.js -p"]:
            self.assertTrue(overnight.is_claude(command), command)
        for command in ["", "/bin/zsh -c claude -p", "vim claude", "claude-helper", "python claude.py",
                        "/Users/x/claude/run.sh", "node server.js claude", "bash /x/claude/versions/run.sh"]:
            self.assertFalse(overnight.is_claude(command), command)

    def test_hook_command_denies_only_the_armed_session(self):
        """hooks.json의 문장 그대로, 진짜 프로세스 트리로 끝까지 돈다."""
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text())
        command = hooks["hooks"]["PermissionRequest"][0]["hooks"][0]["command"]
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        gs = bin_dir / "gs"
        gs.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m gs.cli "$@"\n')
        gs.chmod(0o755)
        env = {**self.session_env, "PATH": f"{bin_dir}:{self.session_env['PATH']}"}
        armed, other = FakeClaude(self, env), FakeClaude(self, env)
        self.assertEqual(armed.run(["gs", "overnight", "arm"], self.repo)[0], 0)
        code, out, err = armed.run(["/bin/sh", "-c", command], self.repo, self.payload(command="git push"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Bash(git)", self.denial(out))
        self.assertEqual(other.run(["/bin/sh", "-c", command], self.repo, self.payload(command="git push")), (0, "", ""))

    # ---- 사라진 세션
    def test_marker_of_gone_process_is_off_and_arm_removes_it(self):
        armed = FakeClaude(self)
        self.arm(armed)
        gone = self.repo / overnight.ARMED_DIR / f"{armed.pid}.json"
        self.assertTrue(gone.exists())
        armed.close()
        later = FakeClaude(self)
        self.assertWindow(later)
        self.arm(later)
        self.assertFalse(gone.exists())

    def test_reused_pid_is_off(self):
        """표시의 pid가 살아 있어도 시작 시각이 다르면 다른 프로세스다."""
        session = FakeClaude(self)
        self.arm(session)
        path = self.repo / overnight.ARMED_DIR / f"{session.pid}.json"
        data = json.loads(path.read_text())
        path.write_text(json.dumps({**data, "started": data["started"] - 3600}))
        self.assertWindow(session)
        self.assertEqual(self.log(), "")

    def test_start_time_jitter_stays_armed(self):
        """Linux의 lstart는 호출마다 1초쯤 흔들린다. 흔들렸다고 꺼지면 창이 떠서 아침까지 선다."""
        session = overnight.Session(5, 1000)
        self.assertTrue(session.same(overnight.Session(5, 1000 + overnight.START_SLACK)))
        self.assertFalse(session.same(overnight.Session(5, 1000 + overnight.START_SLACK + 1)))
        self.assertFalse(session.same(overnight.Session(6, 1000)))

    def test_broken_marker_is_off(self):
        session = FakeClaude(self)
        self.arm(session)
        path = self.repo / overnight.ARMED_DIR / f"{session.pid}.json"
        for broken in ["", "not json", "[]", '{"pid": 1}', '{"pid": "x", "started": 1}']:
            path.write_text(broken)
            self.assertWindow(session)

    # ---- 끄기
    def test_disarm_turns_only_this_session_off(self):
        first, second = FakeClaude(self), FakeClaude(self)
        self.arm(first)
        self.arm(second)  # 같은 레포의 두 번째 arm이 첫 표시를 덮지 않는다
        code, out, _ = second.run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("끔", out)
        self.assertWindow(second)
        self.denial(self.hook(first))

    def test_disarm_when_off_succeeds(self):
        session = FakeClaude(self)
        code, out, _ = session.run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("이미 꺼져", out)
        self.arm(session)
        session.run([*GS, "overnight", "disarm"], self.repo)
        code, out, _ = session.run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("이미 꺼져", out)

    def test_arm_twice_is_one_mark(self):
        session = FakeClaude(self)
        self.arm(session)
        self.arm(session)
        self.assertEqual(len(list((self.repo / overnight.ARMED_DIR).iterdir())), 1)
        session.run([*GS, "overnight", "disarm"], self.repo)
        self.assertWindow(session)

    def run_cmd(self, *argv, table=None, cwd=None):
        out, err = io.StringIO(), io.StringIO()
        old = os.getcwd()
        os.chdir(cwd or self.repo)
        try:
            with mock.patch("gs.overnight.processes", return_value=table or {}), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = cli.main(list(argv))
        finally:
            os.chdir(old)
        return code, out.getvalue(), err.getvalue()

    def test_outside_claude_arm_fails_and_marks_nothing(self):
        code, _, err = self.run_cmd("overnight", "arm")
        self.assertEqual(code, 1)
        self.assertIn("claude", err)
        self.assertFalse((self.repo / overnight.ARMED_DIR).exists())

    def test_outside_claude_disarm_names_the_armed_sessions_and_keeps_them(self):
        session = FakeClaude(self)
        self.arm(session)
        row = overnight.Process(1, json.loads((self.repo / overnight.ARMED_DIR / f"{session.pid}.json").read_text())["started"],
                                "claude")
        code, _, err = self.run_cmd("overnight", "disarm", table={session.pid: row})
        self.assertEqual(code, 1)
        self.assertIn(str(session.pid), err)
        self.denial(self.hook(session))

    def test_arm_and_disarm_report_ps_failure(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("gs.overnight.processes", side_effect=OSError("ps 안 됨")):
            self.assertEqual(overnight.arm(self.repo, out, err), 1)
            self.assertEqual(overnight.disarm(self.repo, out, err), 1)
        self.assertIn("ps 안 됨", err.getvalue())
        self.assertFalse((self.repo / overnight.ARMED_DIR).exists())

    def test_arm_needs_a_repo(self):
        with mock.patch("gs.feature.find_repo_root", return_value=None):  # 임시 디렉터리의 자리에 기대지 않는다
            code, _, err = self.run_cmd("overnight", "arm")
        self.assertEqual(code, 2)
        self.assertIn("git 레포", err)

    # ---- 호출 이름과 기록
    def test_log_has_time_and_name_without_arguments(self):
        session = FakeClaude(self)
        self.arm(session)
        secret = "hunter2-SECRET"
        commands = {f"TOKEN={secret} curl -H 'Authorization: {secret}' https://x/{secret}": "Bash(curl)",
                    f"cat <<EOF | sudo tee /x\n{secret}\nEOF": "Bash(cat, tee)",
                    f"cd /x && git push https://{secret}@host/r.git; echo {secret}": "Bash(cd, git, echo)",
                    f"export TOKEN={secret}": "Bash(export)",
                    f"TOKEN={secret}": "Bash",
                    f"echo \"$(curl -u a:{secret} https://x)\"": "Bash(echo, curl)",
                    f"for x in a {secret}; do curl $x; done": "Bash(curl)",
                    f"echo '{secret}": "Bash",  # 닫히지 않은 따옴표: 조각이 인자일 수 있다
                    f"'{secret} and more' arg": "Bash"}  # 이름 모양이 아닌 첫 단어
        for command, name in commands.items():
            with self.subTest(command=command):
                before = self.log()
                message = self.denial(self.hook(session, command=command))
                self.assertNotIn(secret, message)
                self.assertIn(f"거부한 호출: {name}.", message)
                line = self.log()[len(before):]
                self.assertNotIn(secret, line)
                stamp, called = line.rstrip("\n").split(" ", 1)
                self.assertRegex(stamp, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
                self.assertEqual(called, name)
                self.assertEqual(line.count("\n"), 1)

    def test_tool_calls_are_named_and_input_is_not_logged(self):
        session = FakeClaude(self)
        self.arm(session)
        for tool, inp, name in [("Edit", {"file_path": "/x/a.py", "old_string": "SECRET"}, "Edit"),
                                ("WebFetch", {"url": "https://x/?token=SECRET"}, "WebFetch"),
                                ("mcp__srv__do_it", {"arg": "SECRET"}, "mcp__srv__do_it"),
                                ("Bad\nname SECRET", {}, hook.UNKNOWN_CALL)]:
            with self.subTest(tool=tool):
                before = self.log()
                message = self.denial(self.hook(session, tool=tool, **inp))
                self.assertIn(f"거부한 호출: {name}.", message)
                self.assertNotIn("SECRET", message)
                self.assertEqual(self.log()[len(before):].rstrip("\n").split(" ", 1)[1], name)

    def test_many_commands_are_cut(self):
        names = hook.call_name({"tool_name": "Bash", "tool_input": {"command": "; ".join(f"c{i} x" for i in range(20))}}, {})
        self.assertIn("c7", names)
        self.assertNotIn("c8", names)
        self.assertTrue(names.endswith(", …)"), names)

    def test_log_appends_across_calls(self):
        session = FakeClaude(self)
        self.arm(session)
        self.hook(session)
        self.hook(session, tool="Edit", file_path="/x")
        self.assertEqual([line.split(" ", 1)[1] for line in self.log().splitlines()], ["Bash(git)", "Edit"])

    def test_log_failure_still_denies(self):
        session = FakeClaude(self)
        self.arm(session)
        (self.repo / overnight.DENIED_LOG).mkdir()  # 쓸 수 없는 자리
        self.denial(self.hook(session))

    # ---- 입력
    def test_unreadable_input_in_armed_session_is_denied(self):
        """켠 세션에서는 입력을 못 읽어도 창을 띄우지 않는다. cwd는 프로세스의 것을 쓴다."""
        session = FakeClaude(self)
        self.arm(session)
        for raw in ["not json", "[]", "", '{"cwd": 3}', '{"tool_name": 3}', '{"tool_name": "Bash", "tool_input": []}']:
            with self.subTest(raw=raw):
                code, out, err = session.run([*GS, "hook", "permissionrequest"], self.repo, raw)
                self.assertEqual((code, err), (0, ""))
                self.denial(out)

    def test_unreadable_input_elsewhere_is_quiet(self):
        session = FakeClaude(self)
        for raw in ["not json", "[]", ""]:
            code, out, err = session.run([*GS, "hook", "permissionrequest"], self.repo, raw)
            self.assertEqual((code, out, err), (0, "", ""))

    def test_failing_ps_returns_to_the_window(self):
        session_marker = self.repo / overnight.ARMED_DIR / "1.json"
        session_marker.parent.mkdir(parents=True)
        session_marker.write_text('{"pid": 1, "started": 1}')
        for error in (OSError("ps 안 됨"), subprocess.TimeoutExpired("ps", 1)):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch("gs.overnight.processes", side_effect=error), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = hook.main(["permissionrequest"], stdin=io.StringIO(self.payload()), env={})
            self.assertEqual((code, out.getvalue(), err.getvalue()), (0, "", ""))

    def test_no_marker_does_not_call_ps(self):
        out = io.StringIO()
        with mock.patch("gs.overnight.processes", side_effect=AssertionError("ps를 불렀다")), \
                contextlib.redirect_stdout(out):
            self.assertEqual(hook.main(["permissionrequest"], stdin=io.StringIO(self.payload()), env={}), 0)
        self.assertEqual(out.getvalue(), "")

    def test_cli_hook_needs_no_repo(self):
        plain = self.base / "plain"
        plain.mkdir()
        old = os.getcwd()
        os.chdir(plain)
        out = io.StringIO()
        try:
            with mock.patch("sys.stdin", io.StringIO(self.payload(plain))), contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["hook", "permissionrequest"]), 0)
        finally:
            os.chdir(old)
        self.assertEqual(out.getvalue(), "")

    # ---- 레포 안 자리
    def test_subdirectory_and_linked_worktree_share_the_mark(self):
        self.git("commit", "-q", "--allow-empty", "-m", "x")
        worktree = self.repo / ".goldstack" / "work" / "f" / "run" / "wt" / "01"
        self.git("worktree", "add", "-q", "-b", "gs/f/01", str(worktree))
        sub = self.repo / "src"
        sub.mkdir()
        session, other = FakeClaude(self), FakeClaude(self)
        self.arm(session, worktree)  # worktree에서 켜도 주 체크아웃에 남는다
        self.assertTrue((self.repo / overnight.ARMED_DIR / f"{session.pid}.json").exists())
        self.assertFalse((worktree / overnight.ARMED_DIR).exists())
        for cwd in (self.repo, sub, worktree):
            with self.subTest(cwd=cwd):
                before = self.log()
                self.denial(self.hook(session, cwd))
                self.assertNotEqual(self.log(), before)
                self.assertWindow(other, cwd)
        self.assertFalse((worktree / overnight.DENIED_LOG).exists())
        code, out, _ = session.run([*GS, "overnight", "disarm"], worktree)
        self.assertEqual(code, 0)
        self.assertIn("끔", out)
        self.assertWindow(session)

    def test_marker_and_log_stay_out_of_git_status(self):
        session = FakeClaude(self)
        self.arm(session)
        self.hook(session)
        self.assertTrue(self.log())
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.repo,
                                capture_output=True, text=True, check=True).stdout
        self.assertEqual(status, "")

    def test_existing_ignore_rule_is_left_alone(self):
        (self.repo / ".gitignore").write_text(".goldstack/overnight/\n")
        session = FakeClaude(self)
        self.arm(session)
        self.assertFalse((self.repo / overnight.OVERNIGHT_DIR / ".gitignore").exists())

    def test_existing_ignore_file_keeps_its_lines(self):
        ignore = self.repo / overnight.OVERNIGHT_DIR / ".gitignore"
        ignore.parent.mkdir(parents=True)
        ignore.write_text("keep-me")
        self.arm(FakeClaude(self))
        self.assertEqual(ignore.read_text(), "keep-me\n*\n")


if __name__ == "__main__":
    unittest.main()
