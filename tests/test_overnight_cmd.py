"""`gs overnight arm|disarm`과 `gs hook permissionrequest`: 켠 세션에서만 창이 거부로 바뀐다. `gs overnight add`: 밤샘 파일의 대기열.

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


if __name__ == "__main__":
    unittest.main()
