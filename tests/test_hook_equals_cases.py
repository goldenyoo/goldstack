"""goldstack-v28 02: `GS_NOEQUALS=1` worker는 같은 셸의 `=` 단어 판정만 건너뛰고 새 zsh 본문은 계속 본다.

VerdictTest는 `hook.decide`의 판정만 본다(zsh가 없어도 돈다).
ZshTest는 같은 명령에 `; echo after`를 붙여 실제 /bin/zsh로 돌려 판정의 근거를 확인한다. HOME에는 시작 파일이 없다
(사용자 설정에 `noequals`가 없는 기계).
- 통과 쪽: 01의 전달 폴더(`shellenv.prepare`)를 `ZDOTDIR`로 둔 셸에서 `after`가 나오고 `=` 확장 오류(`not found`)가 없다
- 막는 쪽: 같은 전달 폴더 셸에서도 새 zsh가 `== not found`로 끊긴다(전달 `.zshenv`가 `ZDOTDIR`을 되돌려 자식 zsh는 noequals가 아니다)
- `GS_NOEQUALS`가 없는 쪽: 전달 폴더 없는 셸에서 끊겨 `after`가 나오지 않는다
경우는 spec §6의 `hook.decide` ↔ `/bin/zsh -f -c` 대조(main 6c9b25c)와 grill 실측에서 왔다.
"""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from gs import config, hook, shellenv

ZSH = "/bin/zsh"

# GS_NOEQUALS=1에서 통과한다. 맨 바깥 셸과 그 셸이 읽는 eval 본문·치환·( ) 속이다
SAME_SHELL = [
    r'eval "[[ \$(echo ===) == a ]]"',  # 놓침이었다(지금 환경에서는 `(eval):1: == not found`)
    '""! [[ a == a ]]',  # 놓침이었다. noequals 셸에서도 `bad pattern`을 내지만 끊기지 않는다
    '> ""/dev/null [[ a == a ]]',  # 오차단이었다
    "echo ';' eval '==='",  # 오차단이었다
    "echo ===",
    "eval 'echo ==='", "echo $(echo ===)", "echo `echo ===`", "(echo ===)", "x=$(eval 'echo ===')",
]
# GS_NOEQUALS=1에서도 막는다. 새 zsh 프로세스의 본문이다(어디서 띄웠든)
NEW_ZSH = [
    "zsh -f -c 'echo ==='", "zsh -c 'echo ==='", "zsh -o equals -c 'echo ==='", "/bin/zsh -c 'echo ==='",
    "eval \"zsh -f -c 'echo ==='\"", "echo $(zsh -c 'echo ===')", "(zsh -c 'echo ===')",
    "bash -c 'zsh -f -c \"echo ===\"'",
]


class VerdictTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(os.path.realpath(tmp.name))
        self.wt = base / "repo" / ".goldstack" / "work" / "f" / "run" / "wt" / "02"
        self.wt.mkdir(parents=True)
        self.home = base / "home"
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": str(self.wt), "HOME": str(self.home),
                    "TMPDIR": str(base / "tmp")}
        self.noeq = {**self.env, shellenv.NOEQUALS_ENV: "1"}

    def verdict(self, command, env):
        return hook.decide({"cwd": str(self.wt), "tool_name": "Bash", "tool_input": {"command": command}}, env)

    def assertEqualsBlocked(self, command, env):
        reason = self.verdict(command, env)
        self.assertIsNotNone(reason, command)
        self.assertIn("zsh의 `=` 확장", reason, command)

    def test_noequals_skips_same_shell(self):
        for command in SAME_SHELL:
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command, self.noeq))

    def test_noequals_keeps_new_zsh_body(self):
        for command in NEW_ZSH:
            with self.subTest(command=command):
                self.assertEqualsBlocked(command, self.noeq)

    def test_without_noequals_unchanged(self):
        """표식이 없거나 `1`이 아니면 지금처럼 막는다."""
        for env in [self.env, {**self.env, shellenv.NOEQUALS_ENV: ""}, {**self.env, shellenv.NOEQUALS_ENV: "0"}]:
            for command in ["echo ===", '> ""/dev/null [[ a == a ]]', "echo ';' eval '==='", "eval 'echo ==='",
                            "echo $(echo ===)", "(echo ===)", *NEW_ZSH]:
                with self.subTest(env=env.get(shellenv.NOEQUALS_ENV), command=command):
                    self.assertEqualsBlocked(command, env)

    def test_noequals_keeps_other_checks(self):
        """`=` 밖의 판정은 표식과 상관없이 같은 이유로 막고 같은 명령을 통과시킨다."""
        rules = config.WorkerTestsConfig(deny=(r"unittest discover -s tests\s*$",)).env_value()
        blocked = ["git push origin HEAD", "eval 'git push'", "echo $(git push)", "(git push)", "zsh -f -c 'git push'",
                   "git push --force-with-lease", "git config user.name x", "gh pr merge 3", "rm -rf /etc/x",
                   "echo x > ../out", f"cat {self.home}/.ssh/id_rsa", "cat .env", "pkill -f worker", "killall python",
                   ".venv/bin/python -m unittest discover -s tests"]
        allowed = ["git commit -m x", "ls -la", "echo x > out.txt", "kill 123", "gh pr view 3",
                   ".venv/bin/python -m unittest discover -s tests -p test_x.py"]
        env, noeq = {**self.env, config.WORKER_TESTS_ENV: rules}, {**self.noeq, config.WORKER_TESTS_ENV: rules}
        for command in blocked:
            with self.subTest(command=command):
                reason = self.verdict(command, env)
                self.assertIsNotNone(reason, command)
                self.assertEqual(self.verdict(command, noeq), reason)
        for command in allowed:
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command, env), command)
                self.assertIsNone(self.verdict(command, noeq), command)

    def test_noequals_still_checks_rest_of_same_shell(self):
        """`=` 단어를 건너뛰어도 같은 글의 다른 명령은 본다."""
        for command in ["echo ===; git push", "eval 'echo ===; git push'", "echo $(echo ===; git push)"]:
            with self.subTest(command=command):
                reason = self.verdict(command, self.noeq)
                self.assertIsNotNone(reason, command)
                self.assertIn("git push", reason, command)

    def test_main_entry(self):
        def run(env):
            err = io.StringIO()
            stdin = io.StringIO(json.dumps({"cwd": str(self.wt), "tool_name": "Bash",
                                            "tool_input": {"command": "echo ==="}}))
            with contextlib.redirect_stderr(err):
                return hook.main(["pretooluse"], stdin=stdin, env=env), err.getvalue()

        self.assertEqual(run(self.noeq), (0, ""))
        code, err = run(self.env)
        self.assertEqual(code, 2)
        self.assertIn("따옴표", err)


@unittest.skipUnless(os.access(ZSH, os.X_OK), "/bin/zsh가 없다")
class ZshTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.home = self.root / "home"
        self.home.mkdir()
        (self.root / "run").mkdir()
        self.folder = shellenv.prepare(self.root / "run", None)
        self.assertIsNotNone(self.folder)

    def zsh(self, command, forwarded):
        env = {"HOME": str(self.home), "PATH": "/usr/bin:/bin", "TERM": "dumb", "LC_ALL": "C"}
        if forwarded:
            env[shellenv.ZDOTDIR_ENV] = str(self.folder)
        return subprocess.run([ZSH, "-c", f"{command}; echo after"], env=env, cwd=self.root, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=60)

    def test_same_shell_does_not_break_with_forwarding_folder(self):
        for command in SAME_SHELL:
            with self.subTest(command=command):
                cp = self.zsh(command, forwarded=True)
                self.assertEqual(cp.stdout.splitlines()[-1:], ["after"], cp.stderr)
                self.assertNotIn("not found", cp.stderr)

    def test_new_zsh_breaks_even_with_forwarding_folder(self):
        for command in NEW_ZSH:
            with self.subTest(command=command):
                cp = self.zsh(command, forwarded=True)
                self.assertIn("== not found", cp.stderr)
                self.assertNotIn("===", cp.stdout.splitlines())

    def test_without_forwarding_folder_breaks(self):
        cp = self.zsh("echo ===", forwarded=False)
        self.assertIn("== not found", cp.stderr)
        self.assertNotIn("after", cp.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
