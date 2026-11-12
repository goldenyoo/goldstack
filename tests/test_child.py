"""측정용 자식 명령의 환경과 exec 전달을 확인한다."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import support  # noqa: F401


GS = Path(sys.executable).parent / "gs"
SESSION_VARIABLES = (
    "CLAUDECODE",
    "CLAUDE_EFFORT",
    "CLAUDE_PID",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
)


class ChildTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cwd = directory.name

    def run_child(self, *args, env=None):
        return subprocess.run(
            [str(GS), "child", *args], cwd=self.cwd, env=env,
            capture_output=True, text=True, timeout=10,
        )

    def test_claude_session_variables_removed_and_other_variables_preserved(self):
        preserved = {
            "GS_ROLE": "worker",
            "GS_WORKTREE": self.cwd,
            "GS_CUSTOM": "custom",
            "CLAUDE_CODE_OAUTH_TOKEN": "test-oauth",
            "CLAUDE_CODE_FUTURE_SETTING": "keep",
            "CLAUDE_EFFORT_EXTRA": "keep-too",
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_BASE_URL": "https://example.invalid",
            "ARBITRARY_CHILD_VALUE": "한글 value",
        }
        env = {**os.environ, **dict.fromkeys(SESSION_VARIABLES, "session"), **preserved}
        result = self.run_child(
            "--", sys.executable, "-c", "import json, os; print(json.dumps(dict(os.environ)))",
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        for name in SESSION_VARIABLES:
            with self.subTest(removed=name):
                self.assertNotIn(name, actual.keys())
        for name, value in env.items():
            if name not in SESSION_VARIABLES:
                with self.subTest(preserved=name):
                    self.assertEqual(actual.get(name), value)
        self.assertEqual(result.stderr, "")

    def test_exec_preserves_pid_exit_code_streams_and_arguments(self):
        script = (
            "import json, os, sys; "
            "print(json.dumps([os.getpid(), sys.argv[1:], sys.stdin.read()])); "
            "print('child stderr', file=sys.stderr); sys.exit(37)"
        )
        arguments = ["--help", "--", "--model", "a b", "", "한글"]
        with subprocess.Popen(
            [str(GS), "child", "--", sys.executable, "-c", script, *arguments],
            cwd=self.cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        ) as proc:
            try:
                out, err = proc.communicate("child stdin\n", timeout=10)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            self.assertEqual(proc.returncode, 37, err)
            self.assertEqual(json.loads(out), [proc.pid, arguments, "child stdin\n"])
            self.assertEqual(err, "child stderr\n")

    def test_unset_session_variables_and_path_lookup(self):
        env = {name: value for name, value in os.environ.items() if name not in SESSION_VARIABLES}
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        for separator in (("--",), ()):
            with self.subTest(separator=separator):
                result = self.run_child(*separator, Path(sys.executable).name, "-c", "print('found')", env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "found\n")

    def test_missing_command_shows_usage_on_stderr(self):
        for args in (("--",), ()):
            with self.subTest(args=args):
                result = self.run_child(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage: gs child --", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_help_explains_purpose_and_lists_removed_variables(self):
        result = self.run_child("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("측정용 중첩 세션을 사람이 띄운 것과 같은 조건으로", result.stdout)
        for name in SESSION_VARIABLES:
            with self.subTest(name=name):
                self.assertIn(name, result.stdout.split())
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
