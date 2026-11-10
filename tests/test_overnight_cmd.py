"""`gs overnight arm|disarm`과 `gs hook permissionrequest`: 켠 세션에서만 창이 거부로 바뀐다. `gs overnight add`: 밤샘 파일의 대기열.
`gs overnight next`: 사이 단계 묶기(`OvernightNextTest`).

세션 판정은 진짜 `ps`로 시험한다. `FakeClaude`는 argv[0]이 `claude`인 진짜 프로세스고, 그 자식으로 진짜 `gs`를 돌린다.
"""
import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config, hook, overnight
from support import isolate_git_env

REPO = Path(__file__).resolve().parents[1]
GS = [sys.executable, "-m", "gs.cli"]
# 줄마다 셸 명령 하나를 돌린다. 돌리는 자식은 fork 뒤 바로 exec되어 이 이름을 물려받지 않는다
LOOP = 'while IFS= read -r line; do eval "$line"; done'
NIGHT = """# overnight 2026-11-06
## 받은 허락
- 순서: a
- 사소한 수정: A
- 텔레그램: 끔
## 쓴 허락
## 아침에 물을 것
## 결과
| feature | 상태 | 다시 띄움 | PR | 이유·재개 명령 |
|---|---|---|---|---|
| a | 실행 중 | 0 | – | – |
"""
ROW_C = "| c | 대기 | 0 | – | – |"
REPORT = "## 아침 보고\n# 밤샘 보고 2026-11-06\n| feature | 결과 | PR |\n|---|---|---|\n| a | verified | – |\n"
# 두 프로세스가 같은 글을 읽은 자리에서 서로를 기다린 뒤 쓴다. 잠금이 없으면 뒤에 쓴 쪽이 앞 줄을 지운다.
# 잠금이 있으면 상대는 안으로 들어오지 못해 먼저 든 쪽이 잠깐 기다리고 혼자 쓴다. 통과는 시간에 기대지 않는다
MEET = """
import sys, time
from pathlib import Path
from gs import overnight

repo, name, other, meet = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
real = overnight._result_table

def wait_for(path, seconds):
    deadline = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.005)

def meeting(lines):
    (meet / f"{name}.inside").touch()
    wait_for(meet / f"{other}.ready", 60)
    wait_for(meet / f"{other}.inside", 0.5)
    return real(lines)

overnight._result_table = meeting
(meet / f"{name}.ready").touch()
sys.exit(overnight.add(repo, name, sys.stdout, sys.stderr))
"""

SPEC = '---\nfeature: demo\nverify: "true"\n---\n# demo\n'
TICKET = '---\nid: "01"\ntitle: t\nblocked_by: []\nmodel: claude\nreviewer: codex\ntouches: ["a.py"]\n---\n## 목표\n'
# 부른 순서를 $NEXT_CALLS에 남기는 가짜 외부 명령들
FAKE_GS = f'''#!/bin/sh
echo "gs $*" >> "$NEXT_CALLS"
exec {shlex.quote(sys.executable)} -m gs.cli "$@"
'''
FAKE_UV = '''#!/bin/sh
echo "uv $*" >> "$NEXT_CALLS"
[ -z "$HEAD_AT_UV" ] || git rev-parse HEAD > "$HEAD_AT_UV"
[ -z "$FAIL_UV" ] || { echo 'uv가 실패했다' >&2; exit 1; }
[ -z "$NEW_CODE" ] || cat "$NEW_CODE" >> "$PYTHONPATH/gs/check.py"
'''
FAKE_CLAUDE = '''#!/bin/sh
echo "claude $*" >> "$NEXT_CALLS"
[ "$*" != "plugin list --json" ] || echo '[]'
'''
FAKE_PS = '#!/bin/sh\n[ -z "$PS_ROW" ] || echo "$PS_ROW"\n'
NEW_CODE_MARK = "새 코드로 돌았다"
# 가짜 재설치가 설치본 check.py 끝에 붙이는 코드. 이미 읽은 프로세스는 이 코드를 돌리지 못한다
NEW_CHECK = f'''

_installed_check = check


def check(repo, name, only=None):
    print("{NEW_CODE_MARK}")
    return _installed_check(repo, name, only)
'''
INSTALL_URL = "https://example.test/goldstack.git"


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

    # ---- 낡은 프로세스 목록
    def stale_setup(self, *sessions):
        """주어진 (pid, started)의 표시를 쓰고 `_live_markers`가 지울 수 있는 경로 {pid: Path}를 돌려준다."""
        for pid, started in sessions:
            overnight._write_marker(self.repo, overnight.Session(pid, started))
        return {pid: overnight._marker(self.repo, pid) for pid, _ in sessions}

    @staticmethod
    def ps_rows(*sessions):
        return {pid: overnight.Process(1, started, "claude") for pid, started in sessions}

    def live_pids(self, table, fresh=None, error=None):
        """`ps` 다시 읽기를 가짜로 바꿔 `_live_markers`를 부른다. (살아 있는 pid들, 다시 읽은 횟수)."""
        read = mock.Mock(side_effect=error) if error else mock.Mock(return_value=fresh)
        with mock.patch("gs.overnight.processes", read):
            live = overnight._live_markers(self.repo, table)
        return [m.pid for m in live], read.call_count

    def test_marker_missing_from_the_first_list_but_in_the_fresh_one_stays(self):
        paths = self.stale_setup((501, 1000), (502, 2000))
        pids, reads = self.live_pids(self.ps_rows((501, 1000)), fresh=self.ps_rows((501, 1000), (502, 2000)))
        self.assertEqual((pids, reads), ([501, 502], 1))
        self.assertTrue(paths[501].exists() and paths[502].exists())

    def test_marker_gone_from_both_lists_is_removed(self):
        paths = self.stale_setup((501, 1000), (502, 2000))
        pids, reads = self.live_pids(self.ps_rows((501, 1000)), fresh=self.ps_rows((501, 1000)))
        self.assertEqual((pids, reads), ([501], 1))
        self.assertTrue(paths[501].exists())
        self.assertFalse(paths[502].exists())

    def test_marker_with_a_reused_pid_is_removed_after_the_second_read(self):
        paths = self.stale_setup((501, 1000))
        pids, reads = self.live_pids(self.ps_rows((501, 5000)), fresh=self.ps_rows((501, 5000)))
        self.assertEqual((pids, reads), ([], 1))
        self.assertFalse(paths[501].exists())

    def test_unreadable_marker_is_removed_without_reading_ps_again(self):
        paths = self.stale_setup((501, 1000))
        broken = paths[501].with_name("502.json")
        broken.write_text("not json")
        misnamed = paths[501].with_name("503.json")
        misnamed.write_text(json.dumps({"pid": 504, "started": 1000}))
        pids, reads = self.live_pids(self.ps_rows((501, 1000), (503, 1000), (504, 1000)))
        self.assertEqual((pids, reads), ([501], 0))
        self.assertTrue(paths[501].exists())
        self.assertFalse(broken.exists() or misnamed.exists())

    def test_all_live_markers_do_not_read_ps_again(self):
        paths = self.stale_setup((501, 1000), (502, 2000))
        pids, reads = self.live_pids(self.ps_rows((501, 1000), (502, 2001)))
        self.assertEqual((pids, reads), ([501, 502], 0))
        self.assertTrue(all(path.exists() for path in paths.values()))

    def test_no_markers_do_not_read_ps_again(self):
        self.assertEqual(self.live_pids(self.ps_rows((501, 1000))), ([], 0))

    def test_failed_second_read_keeps_the_marker_but_the_result_leaves_it_out(self):
        for error in (OSError("ps 안 됨"), subprocess.TimeoutExpired("ps", 1)):
            with self.subTest(error=type(error).__name__):
                paths = self.stale_setup((501, 1000), (502, 2000))
                pids, reads = self.live_pids(self.ps_rows((501, 1000)), error=error)
                self.assertEqual((pids, reads), ([501], 1))
                self.assertTrue(paths[501].exists() and paths[502].exists())
                paths[502].unlink()

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

    def denied_call(self, command):
        """켠 세션의 거부 경로를 프로세스 안에서 돌려 기록된 이름을 돌려준다. 세션 판정은 위 시험들이 진짜 `ps`로 본다."""
        (self.repo / overnight.OVERNIGHT_DIR).mkdir(parents=True, exist_ok=True)
        before = self.log()
        out = io.StringIO()
        with mock.patch("gs.overnight.armed_root", return_value=self.repo), contextlib.redirect_stdout(out):
            code = hook.main(["permissionrequest"], stdin=io.StringIO(self.payload(command=command)), env={})
        self.assertEqual(code, 0)
        name = self.log()[len(before):].rstrip("\n").split(" ", 1)[1]
        self.assertEqual(self.denial(out.getvalue()), hook.denial(name))
        return name

    def assertCallNames(self, commands):
        """기대한 이름과 같아야 한다. 거부 이유도 그 이름만 담으므로 인자는 어디에도 남지 않는다."""
        for command, name in commands.items():
            with self.subTest(command=command):
                self.assertEqual(self.denied_call(command), name)

    def test_quoted_separators_do_not_split_commands(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f"curl --data ';' {s}": "Bash(curl)",
                              f'grep "|" {s}': "Bash(grep)",
                              f"find . -exec rm {{}} \\; {s}": "Bash(find)",
                              f"echo $'a\\'b;' {s}": "Bash(echo)",
                              f'echo "a\n{s}"': "Bash(echo)",
                              f"echo a\\\n{s}": "Bash(echo)",
                              f"curl y # {s}": "Bash(curl)",
                              f"# {s}\nls": "Bash(ls)"})

    def test_substitutions_do_not_expose_following_arguments(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f"curl -H Authorization:$(cat token) https://x/{s}": "Bash(curl, cat)",
                              f"curl `cat token` https://x/{s}": "Bash(curl, cat)",
                              f"curl \"$(printf ')')\" {s}": "Bash(curl, printf)",
                              f"echo ${{X:-;}} {s}": "Bash(echo)",
                              f'echo "${{X:-$(cat y)}}" {s}': "Bash(echo, cat)",
                              f"echo $((1+2)) {s}": "Bash(echo)",
                              f"diff <(cat a) {s}": "Bash(diff, cat)",
                              f"curl y >(tee /tmp/z) {s}": "Bash(curl, tee)",
                              f"<(cat a) {s}": "Bash(cat)",  # 명령 자리의 `<(`도 단어다. 뒤는 그 인자다
                              f"$(cat token) {s}": "Bash(cat)"})

    def test_heredoc_bodies_of_every_shape_are_skipped(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f"cat <<\\EOF\n{s}\nEOF": "Bash(cat)",
                              f"cat <<'E O F'\n{s}\nE O F": "Bash(cat)",
                              f'cat <<"EOF"\n{s}\nEOF': "Bash(cat)",
                              f'cat <<E"O"F\n{s}\nEOF': "Bash(cat)",
                              f"cat <<EOF\n  EOF\n{s}\nEOF\nls": "Bash(cat, ls)",  # 끝말은 줄 전체가 같아야 한다
                              f"cat <<-EOF\n\t{s}\n\tEOF\nls": "Bash(cat, ls)",
                              f"cat <<EOF\n{s}": "Bash(cat)",
                              f"curl -d @- <<< {s}": "Bash(curl)",
                              f"curl y 2>&1 {s}": "Bash(curl)",
                              f"curl y &> {s}": "Bash(curl)",
                              f"curl y >| {s}": "Bash(curl)",
                              f"2>/tmp/e curl {s}": "Bash(curl)"})

    def test_compound_commands_name_only_what_runs(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f"[[ a == b && {s} == c ]] && curl y": "Bash(curl)",
                              f"(( {s} > 1 )) && curl y": "Bash(curl)",
                              f"(curl {s})": "Bash(curl)",
                              f"{{ curl {s}; }} > /tmp/x": "Bash(curl)",
                              f"if curl {s}; then ls {s}; fi": "Bash(curl, ls)",
                              f"while read l; do curl {s}; done < /tmp/x": "Bash(read, curl)",
                              f"for x\nin a {s}\ndo curl y; done": "Bash(curl)",
                              f"case $x in a) curl y;; {s}) ls;; esac": "Bash",  # 패턴을 명령과 가르지 않고 이름을 내지 않는다
                              f"y=$(case $x in a) ls;; {s}) ls;; esac)": "Bash",
                              f"A=({s} b); curl y": "Bash",
                              f"f() {{ curl {s}; }}": "Bash",
                              f"ls @(a|{s}) y": "Bash"})

    def test_only_a_plain_word_in_command_position_is_a_name(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f"sudo -u {s} curl y": "Bash(sudo)",  # 옵션 값은 명령과 구별할 수 없다
                              f"command -v {s}": "Bash(command)",
                              f"env -u {s} curl y": "Bash(env)",
                              f"timeout -s {s} 5 curl y": "Bash(timeout)",
                              f"timeout 5 curl {s}": "Bash(curl)",
                              f"sudo FOO={s} curl y": "Bash(curl)",
                              f"/usr/bin/curl {s}": "Bash(curl)",
                              f"'if' {s}": "Bash",  # 따옴표를 씌운 말은 셸 예약어가 아니다
                              f"\\time {s}": "Bash",
                              f"$CMD {s}": "Bash",
                              f"https://x/{s} y": "Bash",
                              f"-x {s}": "Bash"})

    def test_unfinished_command_gives_no_names(self):
        s = "hunter2-SECRET"
        self.assertCallNames({f'curl "$(cat {s}': "Bash",
                              f"curl $(cat {s}": "Bash",
                              f"curl `cat {s}": "Bash",
                              f"curl ${{X {s}": "Bash",
                              f"curl $'{s}": "Bash",
                              f"echo ) {s}": "Bash",
                              f"curl $(cat <<EOF) {s}\nx\nEOF": "Bash",
                              f"{'$(' * 5000}{s}": "Bash"})  # 재귀 한도를 넘어도 거부는 낸다

    def test_many_commands_are_cut(self):
        names = self.denied_call("; ".join(f"c{i} x" for i in range(20)))
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

    # ---- 대기열
    def night(self, text=NIGHT, name="2026-11-06.md"):
        path = self.repo / overnight.OVERNIGHT_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def feature(self, *names):
        for name in names:
            (self.repo / ".goldstack" / "work" / name).mkdir(parents=True)

    def add(self, name="c", **kw):
        return self.run_cmd("overnight", "add", name, **kw)

    def rows(self, path):
        table = path.read_text(encoding="utf-8").partition("## 결과\n")[2]
        return [line.split("|")[1].strip() for line in table.splitlines()[2:] if line.startswith("|")]

    def test_add_puts_a_waiting_row_after_the_last_row(self):
        path, _ = self.night(), self.feature("c")
        code, out, err = self.add()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(path.read_text(encoding="utf-8"), NIGHT + ROW_C + "\n")
        self.assertIn(f"더함: {overnight.OVERNIGHT_DIR}/2026-11-06.md", out)

    def test_add_leaves_the_rest_of_the_file_alone(self):
        self.feature("c")
        head = NIGHT.partition("| a |")[0]
        cases = {"뒤에 다른 절": (NIGHT + "## 메모\n| x | y |\n", NIGHT + ROW_C + "\n## 메모\n| x | y |\n"),
                 "끝 줄바꿈 없음": (NIGHT.rstrip("\n"), NIGHT + ROW_C),
                 "줄이 아직 없는 표": (head, head + ROW_C + "\n"),
                 "표 앞의 빈 줄": (NIGHT.replace("## 결과\n", "## 결과\n\n"),
                                NIGHT.replace("## 결과\n", "## 결과\n\n") + ROW_C + "\n")}
        for label, (before, after) in cases.items():
            with self.subTest(label):
                path = self.night(before)
                self.assertEqual(self.add()[0], 0)
                self.assertEqual(path.read_text(encoding="utf-8"), after)

    def test_add_twice_is_one_row(self):
        path, _ = self.night(), self.feature("a", "c")
        self.assertEqual(self.add()[0], 0)
        before = path.read_text(encoding="utf-8")
        code, out, _ = self.add()
        self.assertEqual(code, 0)
        self.assertIn("이미 있다", out)
        self.assertIn("c(대기)", out)
        code, out, _ = self.add("a")  # 끝나지 않은 다른 상태의 줄도 그대로 둔다
        self.assertEqual(code, 0)
        self.assertIn("a(실행 중)", out)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertEqual(self.rows(path), ["a", "c"])

    def test_add_sees_a_row_the_model_wrote_differently(self):
        path = self.night(NIGHT + "|`c`|대기|0|–|–|\n")
        self.feature("c")
        before = path.read_text(encoding="utf-8")
        code, out, _ = self.add()
        self.assertEqual(code, 0)
        self.assertIn("이미 있다", out)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_add_from_two_processes_at_once_keeps_both_rows(self):
        path, _ = self.night(), self.feature("b", "c")
        meet = self.base / "meet"
        meet.mkdir()
        procs = [subprocess.Popen([sys.executable, "-c", MEET, str(self.repo), me, other, str(meet)], env=self.session_env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for me, other in (("b", "c"), ("c", "b"))]
        for proc in procs:
            _, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(sorted(self.rows(path)), ["a", "b", "c"])

    def test_add_from_many_commands_at_once_keeps_every_row(self):
        names = [f"f{i}" for i in range(8)]
        path, _ = self.night(), self.feature(*names)
        procs = [subprocess.Popen([*GS, "overnight", "add", name], cwd=self.repo, env=self.session_env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for name in names]
        for proc in procs:
            _, err = proc.communicate(timeout=120)
            self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(sorted(self.rows(path)), sorted(["a", *names]))

    def test_add_without_a_night_file_says_to_make_one_and_writes_nothing(self):
        self.feature("c")
        code, out, err = self.add()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("밤샘 파일이 없다", err)
        self.assertIn("/overnight add <feature>", err)
        self.assertIn("/overnight <feature>", err)
        self.assertFalse((self.repo / overnight.OVERNIGHT_DIR).exists())

    def test_add_does_not_reopen_a_finished_night(self):
        """이 밤을 잇는 세션이 없고, 끝난 밤의 허락이 새 feature에 쓰이면 안 된다."""
        text = NIGHT + REPORT
        path, _ = self.night(text), self.feature("c")
        code, _, err = self.add()
        self.assertEqual(code, 1)
        self.assertIn("끝난 밤", err)
        self.assertIn("/overnight add <feature>", err)
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_add_joins_a_resumed_night_that_keeps_its_report(self):
        """`/overnight resume`은 멈춘 밤의 보고를 남긴 채 같은 파일을 잇는다. 거부하면 새 파일이 생겨 코디네이터가 읽지 않는 표에 줄이 간다."""
        path, _ = self.night(NIGHT + REPORT), self.feature("c")
        typist, coordinator = FakeClaude(self), FakeClaude(self)
        self.arm(coordinator)
        code, out, err = typist.run([*GS, "overnight", "add", "c"], self.repo)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(path.read_text(encoding="utf-8"), NIGHT + ROW_C + "\n" + REPORT)
        self.assertIn(f"코디네이터: 세션 pid {coordinator.pid}", out)
        self.assertEqual(overnight.latest_night(self.repo), path)

    def test_add_refuses_a_reported_night_once_its_coordinator_is_gone(self):
        text = NIGHT + REPORT
        path, _ = self.night(text), self.feature("c")
        typist, coordinator = FakeClaude(self), FakeClaude(self)
        self.arm(coordinator)
        coordinator.run([*GS, "overnight", "disarm"], self.repo)
        code, _, err = typist.run([*GS, "overnight", "add", "c"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("끝난 밤", err)
        self.arm(coordinator)
        coordinator.close()
        code, _, err = typist.run([*GS, "overnight", "add", "c"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("끝난 밤", err)
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_add_to_a_reported_night_without_ps_does_not_call_it_finished(self):
        """끝났다고 하면 skill이 새 파일을 만든다. 모를 때는 아무것도 바꾸지 않고 다시 치게 한다."""
        text = NIGHT + REPORT
        path, _ = self.night(text), self.feature("c")
        for error in (OSError("ps 안 됨"), subprocess.TimeoutExpired("ps", 1)):
            with self.subTest(error=error):
                out, err = io.StringIO(), io.StringIO()
                with mock.patch("gs.overnight.processes", side_effect=error):
                    self.assertEqual(overnight.add(self.repo, "c", out, err), 1)
                self.assertIn("모른다", err.getvalue())
                self.assertNotIn("끝난 밤", err.getvalue())
                self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_report_written_before_disarm_keeps_the_added_row_alive(self):
        """7단계의 마지막 확인과 보고 뒤, 끄기 전에 들어온 줄. 끄기가 거부해 코디네이터가 잇고, 끈 뒤에는 거부되어 줄이 방치되지 않는다."""
        path, _ = self.night(NIGHT + REPORT), self.feature("c", "d")
        typist, coordinator = FakeClaude(self), FakeClaude(self)
        self.arm(coordinator)
        code, out, err = typist.run([*GS, "overnight", "add", "c"], self.repo)
        self.assertEqual((code, err), (0, ""))
        self.assertIn(f"코디네이터: 세션 pid {coordinator.pid}", out)

        code, out, err = coordinator.run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual((code, out), (1, ""))
        self.assertIn(overnight.ROWS_LEFT, err)
        self.assertIn(": c.", err)
        self.denial(self.hook(coordinator))  # 켜진 채로 다음 feature를 잇는다

        path.write_text(path.read_text(encoding="utf-8").replace(ROW_C, "| c | verified | 0 | – | – |"), encoding="utf-8")
        code, out, err = coordinator.run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("끔", out)
        self.assertWindow(coordinator)

        before = path.read_text(encoding="utf-8")
        code, _, err = typist.run([*GS, "overnight", "add", "d"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("끝난 밤", err)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def disarm_in_lock(self, inside):
        """`gs overnight disarm`을 켜진 가짜 세션으로 돌린다. 잠금을 얻은 자리에서 `inside()`를 부르고, 그 직후와 놓기 직전의 표시 유무를 함께 돌려준다."""
        session = overnight.Session(4242, 1000)
        overnight._ensure_ignored(self.repo)
        overnight._write_marker(self.repo, session)
        marker = overnight._marker(self.repo, session.pid)
        real = overnight._queue_lock
        seen = []

        @contextlib.contextmanager
        def watched(root):
            with real(root):
                inside()
                seen.append(marker.exists())
                yield
                seen.append(marker.exists())

        table = {session.pid: overnight.Process(1, session.started, "claude")}
        with mock.patch("gs.overnight._queue_lock", watched), mock.patch("gs.overnight.current_session", return_value=session):
            return (*self.run_cmd("overnight", "disarm", table=table), seen)

    def test_disarm_reads_the_table_after_it_gets_the_lock(self):
        """표시를 본 `add`가 잠금 안에서 더하는 동안 끄는 쪽이 기다렸다가 그 줄을 본다. 잠금 전에 읽으면 줄이 방치된다."""
        path, _ = self.night(NIGHT + REPORT), self.feature("c")
        code, _, err, seen = self.disarm_in_lock(lambda: path.write_text(NIGHT + ROW_C + "\n" + REPORT, encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertIn(overnight.ROWS_LEFT, err)
        self.assertEqual(seen, [True, True])

    def test_disarm_removes_the_mark_inside_the_lock(self):
        """잠금을 놓기 전에 꺼져 있어야 그 뒤의 `add`가 표시 없는 끝난 밤을 본다."""
        self.night(NIGHT + REPORT)
        code, out, _, seen = self.disarm_in_lock(lambda: None)
        self.assertEqual(code, 0)
        self.assertIn("끔", out)
        self.assertEqual(seen, [True, False])

    def test_disarm_is_refused_only_for_a_waiting_row_on_a_reported_night(self):
        cases = {"보고 전의 대기 줄(사전 점검, 밤 중의 수동 끄기)": NIGHT + ROW_C + "\n",
                 "보고 뒤 다른 상태의 줄": NIGHT + REPORT,
                 "보고가 있고 표가 깨졌다": "## 결과\n글\n" + REPORT}
        for label, text in cases.items():
            with self.subTest(label):
                self.night(text)
                code, out, err, _ = self.disarm_in_lock(lambda: None)
                self.assertEqual((code, err), (0, ""))
                self.assertIn("끔", out)
        with self.subTest("읽지 못하는 파일"):
            self.night().write_bytes(b"\xff\xfe")
            self.assertEqual(self.disarm_in_lock(lambda: None)[0], 0)
        with self.subTest("모델이 다르게 쓴 줄"):
            self.night(NIGHT + "|`c`|`대기`|0|–|–|\n" + REPORT)
            self.assertEqual(self.disarm_in_lock(lambda: None)[0], 1)

    def test_disarm_of_an_unarmed_session_ignores_waiting_rows(self):
        """켜져 있지 않으면 닫을 대기열이 없다. 사전 점검의 `gs overnight disarm`이 멈추지 않는다."""
        self.night(NIGHT + ROW_C + "\n" + REPORT)
        code, out, _ = FakeClaude(self).run([*GS, "overnight", "disarm"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("이미 꺼져", out)
        self.assertFalse((self.repo / overnight.QUEUE_LOCK).exists())

    def test_add_picks_the_newest_night_by_name(self):
        self.feature("c")
        older = [self.night(name=name) for name in ("2026-11-05-9.md", "2026-11-06.md", "2026-11-06-2.md")]
        newest = self.night(name="2026-11-06-10.md")
        self.night("메모\n", name="notes.md")
        (newest.parent / "2026-11-07-telegram.txt").write_text("보고")
        os.utime(newest, (1000, 1000))  # 옛 밤을 고쳐도 고른 파일이 바뀌지 않는다
        self.assertEqual(overnight.latest_night(self.repo), newest)
        self.assertEqual(self.add()[0], 0)
        self.assertEqual(self.rows(newest), ["a", "c"])
        for path in older:
            self.assertEqual(self.rows(path), ["a"])

    def test_add_needs_the_result_table_and_changes_nothing_without_it(self):
        self.feature("c")
        cases = {"제목 없음": "# overnight\n## 받은 허락\n",
                 "표 없음": "## 결과\n글\n",
                 "다른 절의 표": "## 결과\n## 메모\n| feature | 상태 |\n|---|---|\n",
                 "구분 줄 없음": "## 결과\n| feature | 상태 |\n| a | 대기 |\n",
                 "다른 표": "## 결과\n| 이름 | 상태 |\n|---|---|\n"}
        for label, text in cases.items():
            with self.subTest(label):
                path = self.night(text)
                code, _, err = self.add()
                self.assertEqual(code, 1)
                self.assertIn("표를 찾지 못했다", err)
                self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_add_refuses_names_that_are_not_a_feature(self):
        path, _ = self.night(), self.feature("a|b", "a b")
        for name in ("a|b", "a b", "../c", "..", ".goldstack"):  # 표의 칸을 깨거나 레포 밖을 가리킨다. `a|b`는 디렉터리가 있어도 안 된다
            with self.subTest(name):
                code, _, err = self.add(name)
                self.assertEqual(code, 1)
                self.assertIn("이름으로 쓸 수 없다", err)
                self.assertEqual(path.read_text(encoding="utf-8"), NIGHT)
        code, _, err = self.add("없는것")
        self.assertEqual(code, 1)
        self.assertIn(".goldstack/work/없는것가 없다", err)
        self.assertEqual(path.read_text(encoding="utf-8"), NIGHT)

    def test_add_reports_an_unreadable_file(self):
        path = self.night()
        path.write_bytes(b"\xff\xfe")
        self.feature("c")
        code, _, err = self.add()
        self.assertEqual(code, 1)
        self.assertIn("오류: .goldstack/overnight/2026-11-06.md", err)
        self.assertEqual(path.read_bytes(), b"\xff\xfe")

    def test_add_keeps_the_mode_and_leaves_no_temporary_file(self):
        path, _ = self.night(), self.feature("c")
        path.chmod(0o640)
        self.assertEqual(self.add()[0], 0)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_add_stays_out_of_git_status(self):
        self.night()
        self.feature("c")
        self.assertEqual(self.add()[0], 0)
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", overnight.OVERNIGHT_DIR],
                                cwd=self.repo, capture_output=True, text=True, check=True).stdout
        self.assertEqual(status, "")

    def test_add_from_a_linked_worktree_uses_the_main_checkout(self):
        self.git("commit", "-q", "--allow-empty", "-m", "x")
        worktree = self.base / "wt"
        self.git("worktree", "add", "-q", "-b", "gs/f/01", str(worktree))
        path, _ = self.night(), self.feature("c")
        code, _, err = self.run_cmd("overnight", "add", "c", cwd=worktree)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.rows(path), ["a", "c"])
        self.assertFalse((worktree / overnight.OVERNIGHT_DIR).exists())

    def test_add_names_the_coordinator(self):
        """살아 있는 켜짐 표시가 코디네이터다. 줄을 이을 세션이 없을 때만 `없음`이다."""
        self.night()
        self.feature("c", "d", "e", "g")
        typist, coordinator = FakeClaude(self), FakeClaude(self)

        def add_from(session, name):
            code, out, err = session.run([*GS, "overnight", "add", name], self.repo)
            self.assertEqual(code, 0, err)
            return out

        self.assertIn(overnight.NO_COORDINATOR, add_from(typist, "c"))
        self.arm(coordinator)
        out = add_from(typist, "d")
        self.assertIn(f"코디네이터: 세션 pid {coordinator.pid}", out)
        self.assertNotIn(overnight.NO_COORDINATOR, out)
        self.assertIn(f"코디네이터: 이 세션(pid {coordinator.pid})", add_from(coordinator, "e"))
        self.assertIn(f"코디네이터: 세션 pid {coordinator.pid}", add_from(typist, "c"))  # 이미 있는 줄이어도 알린다
        coordinator.run([*GS, "overnight", "disarm"], self.repo)
        self.assertIn(overnight.NO_COORDINATOR, add_from(typist, "c"))
        self.arm(coordinator)
        coordinator.close()  # 세션이 죽으면 표시가 있어도 이을 세션이 없다
        self.assertIn(overnight.NO_COORDINATOR, add_from(typist, "g"))
        self.assertEqual(list((self.repo / overnight.ARMED_DIR).glob("*.json")), [])

    def test_add_without_ps_still_adds_and_does_not_say_none(self):
        path, _ = self.night(), self.feature("c")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("gs.overnight.processes", side_effect=OSError("ps 안 됨")):
            self.assertEqual(overnight.add(self.repo, "c", out, err), 0)
        self.assertEqual(self.rows(path), ["a", "c"])
        self.assertIn("코디네이터: 모름", out.getvalue())
        self.assertIn("ps 안 됨", out.getvalue())
        self.assertNotIn(overnight.NO_COORDINATOR, out.getvalue())


class OvernightNextTest(unittest.TestCase):
    """임시 레포와 bare 원격으로 진짜 git을 돌린다. uv·claude·ps만 가짜다. 이 시험을 도는 머신의 진짜 `gs go`를 ps가 찾으면 안 된다."""

    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        self.code = REPO / "src"
        self.calls_file = self.base / "calls"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name, text in (("gs", FAKE_GS), ("uv", FAKE_UV), ("claude", FAKE_CLAUDE), ("ps", FAKE_PS),
                           ("gh", "#!/bin/sh\n"), ("codex", "#!/bin/sh\n"), ("agy", "#!/bin/sh\n")):
            path = self.bin / name
            path.write_text(text)
            path.chmod(0o755)
        self.origin = self.base / "origin.git"
        self.repo = self.base / "repo"
        self.upstream = self.base / "upstream"
        self.git(self.base, "init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git(self.base, "clone", "-q", str(self.origin), str(self.repo))
        github = "https://github.com/test/demo.git"  # `gs check`가 원격을 GitHub 주소로 본다. 전송은 bare 원격으로 간다
        self.git(self.repo, "remote", "set-url", "origin", github)
        self.git(self.repo, "config", f"url.{self.origin}.insteadOf", github)
        self.git(self.repo, "checkout", "-q", "-B", "main")
        self.commit(self.repo, "처음", {
            config.CONFIG_PATH: config.DEFAULT_CONFIG.format(base='"main"'),
            ".goldstack/work/demo/spec.md": SPEC, ".goldstack/work/demo/tickets/01-a.md": TICKET,
            ".goldstack/ideas/x.md": "처음\n", ".goldstack/profile.md": "처음\n", "src/a.py": "처음\n",
        })
        self.git(self.repo, "push", "-q", "origin", "main")
        self.git(self.base, "clone", "-q", str(self.origin), str(self.upstream))

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k != "GS_ROLE"}
        env.update({"PATH": f"{self.bin}{os.pathsep}{env['PATH']}", "PYTHONPATH": str(self.code),
                    "GS_UV": str(self.bin / "uv"), "GS_CLAUDE": str(self.bin / "claude"),
                    "NEXT_CALLS": str(self.calls_file), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        env.update(extra)
        return env

    def git(self, cwd, *args):
        cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=self.env())
        self.assertEqual(cp.returncode, 0, f"git {args}: {cp.stderr}")
        return cp.stdout.strip()

    def write(self, where, files):
        for name, text in files.items():
            path = where / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit(self, where, message, files):
        self.write(where, files)
        self.git(where, "add", "-A")
        self.git(where, "commit", "-q", "-m", message)
        return self.git(where, "rev-parse", "HEAD")

    def merged(self, files=None, message="병합된 feature"):
        """다른 곳에서 base에 올라간 커밋. 원격 꼭대기를 돌려준다."""
        tip = self.commit(self.upstream, message, files or {"src/merged.py": "병합\n"})
        self.git(self.upstream, "push", "-q", "origin", "main")
        return tip

    def head(self):
        return self.git(self.repo, "rev-parse", "HEAD")

    def origin_tip(self):
        return self.git(self.origin, "rev-parse", "main")

    def status(self):
        return self.git(self.repo, "status", "--porcelain")

    def calls(self):
        return self.calls_file.read_text(encoding="utf-8").splitlines() if self.calls_file.exists() else []

    def next(self, name="demo", gs=None, **env):
        cp = subprocess.run([*(gs or GS), "overnight", "next", name], cwd=self.repo, capture_output=True, text=True,
                            env=self.env(**env))
        return cp.returncode, cp.stdout, cp.stderr

    def assertFailedAt(self, step, result):
        code, out, err = result
        self.assertEqual(code, 1, out + err)
        self.assertIn(f"{overnight.STEP_FAILED}: {step}", err)
        return err

    def assertPassed(self, result):
        code, out, err = result
        self.assertEqual(code, 0, out + err)
        self.assertNotIn(overnight.STEP_FAILED, err)
        return out

    def assertStopped(self, before):
        """base 단계에서 멈췄다. 로컬은 그대로고 다음 단계는 돌지 않았고 원격에는 아무것도 가지 않았다."""
        self.assertEqual(self.head(), before)
        self.assertEqual(self.git(self.repo, "symbolic-ref", "--short", "HEAD"), "main")
        self.assertEqual(self.calls(), [])

    # ---- base 위로 올리기
    def test_up_to_date_changes_nothing_and_runs_the_check(self):
        before = self.head()
        out = self.assertPassed(self.next())
        self.assertEqual(self.head(), before)
        self.assertIn(f"■ {overnight.STEP_BASE}: 이미 origin/main 위다", out)
        self.assertIn("demo: 티켓 1장, 오류 0", out)
        self.assertEqual(self.calls(), ["gs check -- demo"])  # goldstack 레포가 아니므로 재설치하지 않는다
        self.assertIn(f"■ {overnight.STEP_UPDATE}: 건너뜀", out)

    def test_behind_only_fast_forwards(self):
        before, tip = self.head(), self.merged()
        out = self.assertPassed(self.next())
        self.assertEqual(self.head(), tip)
        self.assertEqual(self.git(self.repo, "merge-base", "HEAD", before), before)
        self.assertIn("1커밋 fast-forward", out)

    def test_grill_commits_on_top_of_base_stay_and_are_not_pushed(self):
        """base가 앞서지 않았으면 올릴 것이 없다. push는 `/go` 2단계가 한다."""
        tip = self.origin_tip()
        mine = self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        out = self.assertPassed(self.next())
        self.assertEqual((self.head(), self.origin_tip()), (mine, tip))
        self.assertIn("push 안 된 grill 커밋 1개", out)

    def test_diverged_grill_commits_are_rebased_onto_base_and_not_pushed(self):
        first = self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        self.commit(self.repo, "grill: r", {".goldstack/ideas/new.md": "새 생각\n"})
        tip = self.merged()
        out = self.assertPassed(self.next())
        self.assertEqual(self.origin_tip(), tip)  # force push도 그냥 push도 없다
        self.assertEqual(self.git(self.repo, "log", "--format=%s", "-3").splitlines(), ["grill: r", "grill: q", "병합된 feature"])
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD~2"), tip)
        self.assertEqual(self.git(self.repo, "rev-list", "--merges", "HEAD"), "")
        self.assertNotEqual(self.git(self.repo, "rev-parse", "HEAD~1"), first)
        self.assertEqual(self.status(), "")
        for name in ("src/merged.py", ".goldstack/work/q/spec.md", ".goldstack/ideas/new.md"):
            self.assertTrue((self.repo / name).exists(), name)
        self.assertIn("grill 커밋 2개를 origin/main 위로 rebase", out)

    def test_every_grill_path_may_be_rebased(self):
        self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC, ".goldstack/out-of-scope/z.md": "z\n",
                                            ".goldstack/ideas/x.md": "고침\n", ".goldstack/profile.md": "고침\n"})
        tip = self.merged()
        self.assertPassed(self.next())
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD~1"), tip)

    def test_a_queued_feature_that_only_arrives_by_rebase_or_pull_passes_the_check(self):
        """`gs check`는 올린 다음의 트리를 본다."""
        self.merged({".goldstack/work/there/spec.md": SPEC.replace("demo", "there"),
                     ".goldstack/work/there/tickets/01-a.md": TICKET})
        self.assertIn("there: 티켓 1장", self.assertPassed(self.next("there")))

    def other_paths(self):
        """(이름, 로컬에 커밋을 만드는 함수, 거부 메시지에 나올 경로)."""
        repo = self.repo

        def renamed():
            self.git(repo, "mv", "src/a.py", ".goldstack/ideas/a.py")
            self.git(repo, "commit", "-q", "-m", "grill처럼 보이는 이동")

        def merge_commit():
            start = self.head()
            self.git(repo, "checkout", "-q", "-b", "side")
            self.commit(repo, "옆 코드", {"src/side.py": "옆\n"})
            self.git(repo, "checkout", "-q", "main")
            self.commit(repo, "grill: q", {".goldstack/ideas/q.md": "q\n"})
            self.git(repo, "merge", "-q", "--no-edit", "side")
            self.git(repo, "branch", "-q", "-D", "side")
            self.assertNotEqual(self.head(), start)

        def merge_commit_edits_code():
            """옆 브랜치는 grill뿐이고 병합 커밋이 직접 코드를 고쳤다. 병합 커밋은 기본으로 경로를 내지 않는다."""
            self.git(repo, "checkout", "-q", "-b", "side")
            self.commit(repo, "grill: s", {".goldstack/ideas/s.md": "s\n"})
            self.git(repo, "checkout", "-q", "main")
            self.commit(repo, "grill: q", {".goldstack/ideas/q.md": "q\n"})
            self.git(repo, "merge", "-q", "--no-commit", "--no-ff", "side")
            self.commit(repo, "병합", {"src/evil.py": "x\n"})
            self.git(repo, "branch", "-q", "-D", "side")

        def reverted():
            self.commit(repo, "코드", {"src/a.py": "고침\n"})
            self.commit(repo, "되돌림", {"src/a.py": "처음\n"})

        return [
            ("한 커밋에 섞임", lambda: self.commit(repo, "grill: q", {".goldstack/ideas/q.md": "q\n", "src/b.py": "b\n"}), "src/b.py"),
            ("둘째 커밋", lambda: (self.commit(repo, "grill: q", {".goldstack/ideas/q.md": "q\n"}),
                                 self.commit(repo, "코드", {"src/b.py": "b\n"})), "src/b.py"),
            ("옮긴 커밋의 옛 경로", renamed, "src/a.py"),
            ("병합 커밋이 가져온 경로", merge_commit, "src/side.py"),
            ("병합 커밋이 직접 고친 경로", merge_commit_edits_code, "src/evil.py"),
            ("고쳤다 되돌림", reverted, "src/a.py"),
            ("config", lambda: self.commit(repo, "설정", {config.CONFIG_PATH: config.DEFAULT_CONFIG.format(base='"main"') + "\n"}),
             config.CONFIG_PATH),
            ("비슷한 이름의 디렉터리", lambda: self.commit(repo, "x", {".goldstack/ideas-old/q.md": "q\n"}), ".goldstack/ideas-old/q.md"),
            ("비슷한 이름의 파일", lambda: self.commit(repo, "x", {".goldstack/profile.md.bak": "q\n"}), ".goldstack/profile.md.bak"),
            ("work 자체와 이름이 겹침", lambda: self.commit(repo, "x", {".goldstack/workshop/q.md": "q\n"}), ".goldstack/workshop/q.md"),
            ("한글 경로", lambda: self.commit(repo, "x", {"문서/메모 하나.md": "q\n"}), "문서/메모 하나.md"),
        ]

    def test_other_paths_refuse_when_base_is_ahead(self):
        self.merged()
        start = self.head()
        for name, make, path in self.other_paths():
            with self.subTest(name):
                self.git(self.repo, "reset", "-q", "--hard", start)
                make()
                before, tip = self.head(), self.origin_tip()
                err = self.assertFailedAt(overnight.STEP_BASE, self.next())
                self.assertIn(path, err)
                self.assertIn("grill 경로 밖", err)
                self.assertStopped(before)
                self.assertEqual(self.origin_tip(), tip)

    def test_other_paths_refuse_even_when_base_is_not_ahead(self):
        """올릴 것은 없지만 다음 `/go` 2단계의 push가 검증 없이 base에 넣는다."""
        before = self.commit(self.repo, "코드", {"src/b.py": "b\n"})
        self.assertIn("src/b.py", self.assertFailedAt(overnight.STEP_BASE, self.next()))
        self.assertStopped(before)

    def grill_merge(self):
        """두 grill 브랜치를 합치며 병합 커밋에서만 파일을 더 고쳤다. 경로는 모두 grill이다."""
        repo = self.repo
        self.git(repo, "checkout", "-q", "-b", "side")
        self.commit(repo, "grill: s", {".goldstack/ideas/s.md": "s\n"})
        self.git(repo, "checkout", "-q", "main")
        self.commit(repo, "grill: q", {".goldstack/ideas/q.md": "q\n"})
        self.git(repo, "merge", "-q", "--no-commit", "--no-ff", "side")
        head = self.commit(repo, "병합", {".goldstack/ideas/x.md": "병합 때만 고친 결정\n"})
        self.git(repo, "branch", "-q", "-D", "side")
        return head

    def test_grill_only_merge_commit_refuses_the_rebase(self):
        """rebase는 병합 커밋을 버린다. 그 커밋에서만 고친 내용이 종료 코드 0으로 사라지면 안 된다."""
        before, tip = self.grill_merge(), self.merged()
        result = self.next()
        self.assertEqual((self.repo / ".goldstack/ideas/x.md").read_text(encoding="utf-8"), "병합 때만 고친 결정\n")
        err = self.assertFailedAt(overnight.STEP_BASE, result)
        self.assertIn("병합 커밋", err)
        self.assertIn(before, err)
        self.assertStopped(before)
        self.assertEqual(self.origin_tip(), tip)

    def test_grill_only_merge_commit_stays_when_base_is_not_ahead(self):
        """rebase가 없으면 잃을 것도 없다."""
        before = self.grill_merge()
        self.assertIn("push 안 된 grill 커밋 3개", self.assertPassed(self.next()))
        self.assertEqual(self.head(), before)

    def test_merge_commits_already_on_base_do_not_refuse_the_rebase(self):
        """티켓을 merge 방식으로 병합하는 레포의 base에는 병합 커밋이 있다. push 안 된 커밋이 아니다."""
        upstream = self.upstream
        self.git(upstream, "checkout", "-q", "-b", "feature")
        self.commit(upstream, "티켓", {"src/feature.py": "f\n"})
        self.git(upstream, "checkout", "-q", "main")
        self.commit(upstream, "다른 티켓", {"src/other.py": "o\n"})
        self.git(upstream, "merge", "-q", "--no-edit", "feature")
        self.git(upstream, "push", "-q", "origin", "main")
        self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        self.assertIn("grill 커밋 1개를 origin/main 위로 rebase", self.assertPassed(self.next()))
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD~1"), self.origin_tip())

    def test_conflict_aborts_back_to_the_original_state(self):
        """둘째 커밋에서 충돌해도 첫 커밋까지 옮겨진 자리가 아니라 시작 전으로 돌아간다."""
        self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        before = self.commit(self.repo, "grill: r", {".goldstack/ideas/x.md": "로컬\n"})
        tip = self.merged({".goldstack/ideas/x.md": "병합\n"})
        err = self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.assertIn(overnight.REBASE_CONFLICT, err)
        self.assertIn(".goldstack/ideas/x.md", err)
        self.assertStopped(before)
        self.assertEqual(self.status(), "")
        self.assertEqual((self.repo / ".goldstack/ideas/x.md").read_text(encoding="utf-8"), "로컬\n")
        self.assertEqual(self.origin_tip(), tip)
        for name in ("rebase-merge", "rebase-apply"):
            self.assertFalse((self.repo / ".git" / name).exists(), name)

    def test_conflict_can_be_typed_again_after_a_person_resolves_it(self):
        self.commit(self.repo, "grill: r", {".goldstack/ideas/x.md": "로컬\n"})
        self.merged({".goldstack/ideas/x.md": "병합\n"})
        self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.git(self.repo, "reset", "-q", "--hard", "HEAD~1")
        self.assertPassed(self.next())

    def test_failed_abort_says_a_person_has_to_look(self):
        """되돌렸다고 거짓말하지 않는다."""
        self.commit(self.repo, "grill: r", {".goldstack/ideas/x.md": "로컬\n"})
        self.merged({".goldstack/ideas/x.md": "병합\n"})
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env()), mock.patch("gs.overnight._rebasing", return_value=True):
            self.assertEqual(overnight.advance(self.repo, "demo", out, err), 1)
        self.assertIn("되돌리지 못했다", err.getvalue())
        self.assertIn("사람이", err.getvalue())

    def test_uncommitted_change_refuses_the_rebase_even_with_autostash_set(self):
        """git이 시작을 거부한다. 설정이 있어도 변경을 치우지 않는다."""
        self.git(self.repo, "config", "rebase.autoStash", "true")
        before = self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        self.merged()
        self.write(self.repo, {".goldstack/ideas/x.md": "쓰는 중\n"})
        err = self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.assertIn("git pull --rebase가 시작하지 못했다", err)
        self.assertStopped(before)
        self.assertEqual(self.status(), "M .goldstack/ideas/x.md")
        self.assertEqual((self.repo / ".goldstack/ideas/x.md").read_text(encoding="utf-8"), "쓰는 중\n")
        self.assertEqual(self.git(self.repo, "stash", "list"), "")

    def test_untracked_file_in_the_way_leaves_the_original_state(self):
        before = self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        self.merged({".goldstack/ideas/new.md": "병합\n"})
        self.write(self.repo, {".goldstack/ideas/new.md": "쓰는 중\n"})
        self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.assertStopped(before)
        self.assertEqual((self.repo / ".goldstack/ideas/new.md").read_text(encoding="utf-8"), "쓰는 중\n")
        self.assertEqual(self.status(), "?? .goldstack/ideas/new.md")
        for name in ("rebase-merge", "rebase-apply"):
            self.assertFalse((self.repo / ".git" / name).exists(), name)

    def test_fast_forward_keeps_an_uncommitted_change_it_does_not_touch(self):
        tip = self.merged()
        self.write(self.repo, {".goldstack/ideas/x.md": "쓰는 중\n"})
        self.assertPassed(self.next())
        self.assertEqual(self.head(), tip)
        self.assertEqual(self.status(), "M .goldstack/ideas/x.md")

    def test_fast_forward_refuses_over_an_uncommitted_change_it_would_overwrite(self):
        before = self.head()
        self.merged({".goldstack/ideas/x.md": "병합\n"})
        self.write(self.repo, {".goldstack/ideas/x.md": "쓰는 중\n"})
        self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.assertStopped(before)
        self.assertEqual((self.repo / ".goldstack/ideas/x.md").read_text(encoding="utf-8"), "쓰는 중\n")

    def test_refuses_on_another_branch_and_detached_head(self):
        self.merged()
        self.git(self.repo, "checkout", "-q", "-b", "work")
        before = self.head()
        self.assertIn("work", self.assertFailedAt(overnight.STEP_BASE, self.next()))
        self.assertEqual(self.head(), before)
        self.git(self.repo, "checkout", "-q", "--detach")
        self.assertIn("detached HEAD", self.assertFailedAt(overnight.STEP_BASE, self.next()))
        self.assertEqual(self.head(), before)
        self.assertEqual(self.calls(), [])

    def test_unreachable_remote_fails_at_the_base_step(self):
        before = self.head()
        self.git(self.repo, "remote", "set-url", "origin", str(self.base / "없음.git"))
        self.assertFailedAt(overnight.STEP_BASE, self.next())
        self.assertStopped(before)

    def test_remote_and_base_come_from_the_config(self):
        self.git(self.repo, "remote", "rename", "origin", "upstream")
        self.git(self.repo, "checkout", "-q", "-b", "develop")
        text = config.DEFAULT_CONFIG.format(base='"develop"').replace('remote = "origin"', 'remote = "upstream"')
        self.assertIn('remote = "upstream"', text)
        self.commit(self.repo, "설정", {config.CONFIG_PATH: text})
        self.git(self.repo, "push", "-q", "upstream", "develop")
        self.git(self.upstream, "fetch", "-q", "origin")
        self.git(self.upstream, "checkout", "-q", "-b", "develop", "origin/develop")
        tip = self.commit(self.upstream, "병합", {"src/merged.py": "병합\n"})
        self.git(self.upstream, "push", "-q", "origin", "develop")
        self.commit(self.repo, "grill: q", {".goldstack/work/q/spec.md": SPEC})
        self.assertPassed(self.next())
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD~1"), tip)
        self.assertEqual(self.git(self.repo, "symbolic-ref", "--short", "HEAD"), "develop")

    def test_without_a_config_fails_at_the_base_step(self):
        (self.repo / config.CONFIG_PATH).unlink()
        self.assertIn("gs init", self.assertFailedAt(overnight.STEP_BASE, self.next()))
        self.assertEqual(self.calls(), [])

    def test_bad_name_moves_nothing(self):
        before = self.head()
        self.merged()
        for name in ("a|b", "a/b", ".hidden", "a b"):
            with self.subTest(name):
                code, _, err = self.next(name)
                self.assertEqual(code, 1)
                self.assertIn("feature 이름으로 쓸 수 없다", err)
                self.assertStopped(before)

    def test_never_pushes(self):
        """force push는 없다. `/go` 2단계가 fast-forward로만 올린다."""
        source = Path(overnight.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"push"', source)
        self.assertNotIn("--force", source)

    # ---- 재설치
    def install(self, url=INSTALL_URL):
        """이 레포를 goldstack으로 만들고 옛 gs 설치본을 놓는다. 시험은 `bin/gs`로 그 설치본을 돌린다."""
        self.code = self.base / "install"
        shutil.copytree(REPO / "src" / "gs", self.code / "gs", ignore=shutil.ignore_patterns("__pycache__"))
        info = self.code / "goldstack-1.0.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text("Metadata-Version: 2.1\nName: goldstack\nVersion: 1.0.0\n")
        if url:
            (info / "direct_url.json").write_text(json.dumps({"url": url, "vcs_info": {"vcs": "git", "commit_id": "abc"}}))
        self.commit(self.repo, "pyproject", {"pyproject.toml": '[project]\nname = "goldstack"\n'})
        self.git(self.repo, "push", "-q", "origin", "main")
        self.git(self.upstream, "pull", "-q", "origin", "main")
        return [str(self.bin / "gs")]

    def test_check_after_the_reinstall_runs_the_new_code(self):
        """옛 코드는 cli.py에서 check를 이미 읽었다. 새 프로세스로 불러야 재설치한 코드가 돈다."""
        gs = self.install()
        new_code = self.base / "new_check.py"
        new_code.write_text(NEW_CHECK, encoding="utf-8")
        before = subprocess.run([*gs, "check", "demo"], cwd=self.repo, capture_output=True, text=True, env=self.env())
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertNotIn(NEW_CODE_MARK, before.stdout)
        self.calls_file.unlink()
        out = self.assertPassed(self.next(gs=gs, NEW_CODE=str(new_code)))
        self.assertIn(NEW_CODE_MARK, out)
        self.assertEqual([call for call in self.calls() if call != "claude plugin list --json"], [
            "gs overnight next demo",
            f"uv tool install --reinstall git+{INSTALL_URL}@main",
            "claude plugin marketplace update goldstack",
            "claude plugin update goldstack@goldstack",
            "gs check -- demo",
        ])

    def test_reinstall_runs_after_base_moved(self):
        gs = self.install()
        tip = self.merged()
        at_uv = self.base / "head_at_uv"
        self.assertPassed(self.next(gs=gs, HEAD_AT_UV=str(at_uv)))
        self.assertEqual(at_uv.read_text().strip(), tip)

    def test_running_go_refusal_is_passed_on_and_typing_again_continues(self):
        gs = self.install()
        tip = self.merged()
        row = "4242 /venv/bin/python /venv/bin/gs go other"
        err = self.assertFailedAt(overnight.STEP_UPDATE, self.next(gs=gs, PS_ROW=row))
        self.assertIn("거부: 이 머신에서 gs go 실행 중(PID 4242)", err)
        self.assertEqual(self.calls(), ["gs overnight next demo"])  # 설치도 check도 돌지 않는다
        self.assertEqual(self.head(), tip)
        self.assertPassed(self.next(gs=gs))
        self.assertEqual(self.calls()[-1], "gs check -- demo")

    def test_local_install_passes_on_the_from_refusal(self):
        gs = self.install(url=None)
        err = self.assertFailedAt(overnight.STEP_UPDATE, self.next(gs=gs))
        self.assertIn("gs self-update --from", err)
        self.assertNotIn("gs check -- demo", self.calls())

    def test_failed_reinstall_stops_before_the_check(self):
        gs = self.install()
        err = self.assertFailedAt(overnight.STEP_UPDATE, self.next(gs=gs, FAIL_UV="1"))
        self.assertIn("uv가 실패했다", err)
        self.assertNotIn("gs check -- demo", self.calls())

    def test_only_a_repo_named_goldstack_reinstalls(self):
        path = self.repo / "pyproject.toml"
        for text, expected in (('[project]\nname = "goldstack"\n', True), ('[project]\nname = "other"\n', False),
                               ('name = "goldstack"\n', False), ('project = "goldstack"\n', False), ("이건 toml이 아니다", False)):
            with self.subTest(text):
                path.write_text(text, encoding="utf-8")
                self.assertEqual(overnight._is_goldstack(self.repo), expected)
        path.unlink()
        self.assertFalse(overnight._is_goldstack(self.repo))

    # ---- gs check
    def test_check_failure_names_the_step_and_shows_its_output(self):
        tip = self.merged()
        err = self.assertFailedAt(overnight.STEP_CHECK, self.next("없음"))
        self.assertIn("없음", err)
        self.assertIn("종료 코드 1", err)
        self.assertEqual(self.head(), tip)  # 다시 쳐도 되는 자리다

    def test_check_warning_passes_and_stays_visible(self):
        """경고를 허락 안에서 없앨지는 모델의 판단이다."""
        self.commit(self.repo, "grill", {".goldstack/ideas/x.md": "고침\n"})
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"') + "\n[unknown_key]\n", encoding="utf-8")
        code, out, err = self.next()
        self.assertEqual(code, 0, err)
        self.assertIn("경고 1", out)
        self.assertIn("unknown_key", err)
        self.assertIn("모델이 본다", out)

    def test_missing_gs_names_the_check_step(self):
        only_git = self.base / "only_git"
        only_git.mkdir()
        (only_git / "git").symlink_to(shutil.which("git"))
        err = self.assertFailedAt(overnight.STEP_CHECK, self.next(PATH=str(only_git)))
        self.assertIn("돌리지 못했다", err)

    def test_name_starting_with_a_dash_is_not_an_option_of_the_check(self):
        cp = subprocess.run([*GS, "overnight", "next", "--", "--help"], cwd=self.repo, capture_output=True, text=True, env=self.env())
        self.assertEqual(cp.returncode, 1, cp.stdout)
        self.assertIn(f"{overnight.STEP_FAILED}: {overnight.STEP_CHECK}", cp.stderr)
        self.assertEqual(self.calls(), ["gs check -- --help"])


if __name__ == "__main__":
    unittest.main()
