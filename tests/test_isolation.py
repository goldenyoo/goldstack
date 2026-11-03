"""claude worker 플러그인 격리(08): 명령 문자열에 격리 옵션이 들어가는가.

실제 claude는 부르지 않는다. `claude plugin list --json`은 가짜 실행 파일(GS_CLAUDE)로 바꿔 끼운다.
격리 옵션이 실제로 goldstack hook을 남기고 다른 플러그인 skill을 빼는지는
docs/research/worker-plugin-isolation.md에 실제 실행으로 적었다.
"""
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, config
from gs.adapters import AdapterError, WorkerInput

MODELS = config.ModelsConfig("judge-test", "review-test", "agy-test", "")

PLUGINS = [
    {"id": "goldstack@goldstack", "scope": "user", "enabled": True},
    {"id": "oh-my-claudecode@omc", "scope": "user", "enabled": True},
    {"id": "ha-rtl@ha-rtl", "scope": "user", "enabled": False},
    {"id": "pdf-viewer@synced", "scope": "synced", "enabled": True},
    {"id": "proj-thing@market", "scope": "project", "enabled": False, "projectEnabled": True},
]


class IsolationCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wt = self.root / "wt dir"
        self.wt.mkdir()
        self.inp = WorkerInput(brief=self.root / "run dir" / "brief.md", worktree=self.wt,
                               log=self.root / "run dir" / "worker.log")
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)

    def fake_claude(self, body: str) -> Path:
        """`$0 plugin list --json` 호출을 받는 가짜 claude. 받은 인자와 cwd를 calls 파일에 남긴다."""
        exe = self.root / "fake-claude"
        calls = self.root / "calls"
        exe.write_text(f'#!/bin/bash\necho "$PWD|$*" >> {shlex.quote(str(calls))}\n{body}\n', encoding="utf-8")
        exe.chmod(0o755)
        os.environ["GS_CLAUDE"] = str(exe)
        return calls

    def listing(self, plugins) -> Path:
        out = self.root / "plugins.json"
        out.write_text(json.dumps(plugins), encoding="utf-8")
        return self.fake_claude(f"cat {shlex.quote(str(out))}")

    def argv(self, cmd: str) -> list[str]:
        return shlex.split(cmd.replace("< ", "<"))

    def test_command_disables_other_plugins_keeps_goldstack(self):
        calls = self.listing(PLUGINS)
        a = adapters.Claude(MODELS)
        cmd = a.command(self.inp)
        argv = self.argv(cmd)
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertEqual(settings, {"enabledPlugins": {"ha-rtl@ha-rtl": False, "oh-my-claudecode@omc": False,
                                                       "pdf-viewer@synced": False, "proj-thing@market": False}})
        self.assertNotIn("goldstack", argv[argv.index("--settings") + 1])  # goldstack hook은 남는다
        self.assertEqual(a.outcome(0, self.inp), (0, ""))
        cwd, args = calls.read_text(encoding="utf-8").strip().split("|")
        self.assertEqual(args, "plugin list --json")
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(self.wt))  # project scope 플러그인도 보이게

    def test_command_has_mcp_and_skill_isolation(self):
        self.listing(PLUGINS)
        cmd = adapters.Claude(MODELS).command(self.inp)
        argv = self.argv(cmd)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(json.loads(argv[argv.index("--mcp-config") + 1]), {"mcpServers": {}})
        self.assertIn("--disable-slash-commands", argv)
        for flag in ("--bare", "--safe-mode", "--setting-sources", "--restricted"):  # CLAUDE.md·설정·hook·로그인을 지운다
            self.assertNotIn(flag, argv)

    def test_command_keeps_existing_guards_and_shape(self):
        self.listing(PLUGINS)
        cmd = adapters.Claude(MODELS).command(self.inp)
        self.assertTrue(cmd.startswith(adapters.Claude.BASE + " "), cmd)
        self.assertIn('--disallowedTools "Bash(git push *)" "Bash(gh *)"', cmd)
        self.assertTrue(cmd.endswith(f"< {shlex.quote(str(self.inp.brief))}"), cmd)
        argv = self.argv(cmd)
        # 가변 인자 옵션(--disallowedTools, --mcp-config) 뒤에는 `--` 옵션이 와서 값이 섞이지 않는다
        tools = argv.index("--disallowedTools")
        self.assertEqual(argv[tools + 1:tools + 3], ["Bash(git push *)", "Bash(gh *)"])
        self.assertTrue(argv[tools + 3].startswith("--"))
        self.assertTrue(argv[argv.index("--mcp-config") + 2].startswith("--"))

    def test_only_goldstack_installed_omits_settings(self):
        self.listing([{"id": "goldstack@goldstack"}, {"id": "goldstack@other-market"}])
        cmd = adapters.Claude(MODELS).command(self.inp)
        self.assertNotIn("--settings", cmd)
        self.assertIn("--disable-slash-commands", cmd)

    def test_listing_failure_keeps_other_isolation_and_notes(self):
        cases = {"exit": "echo boom >&2; exit 3", "not json": "echo nope", "not list": "echo '{}'"}
        for why, body in cases.items():
            with self.subTest(why):
                self.fake_claude(body)
                a = adapters.Claude(MODELS)
                cmd = a.command(self.inp)
                self.assertNotIn("--settings", cmd)
                self.assertIn("--strict-mcp-config", cmd)
                self.assertIn("--disable-slash-commands", cmd)
                code, note = a.outcome(0, self.inp)
                self.assertEqual(code, 0)
                self.assertIn("플러그인 격리 못 함", note)

    def test_missing_claude_binary(self):
        os.environ["GS_CLAUDE"] = str(self.root / "no-such-claude")
        a = adapters.Claude(MODELS)
        self.assertNotIn("--settings", a.command(self.inp))
        self.assertIn("가 없다", a.outcome(1, self.inp)[1])
        self.assertEqual(a.outcome(1, self.inp)[0], 1)

    def test_plugins_to_disable_ignores_junk(self):
        got = adapters.plugins_to_disable([{"id": "a@m"}, {"id": ""}, {"id": 3}, {}, {"id": "a@m"},
                                           {"id": "goldstack"}, {"id": "goldstackx@m"}])
        self.assertEqual(got, ["a@m", "goldstackx@m"])

    def test_claude_plugins_raises_adapter_error(self):
        self.fake_claude("exit 1")
        with self.assertRaises(AdapterError):
            adapters.claude_plugins(self.wt)


if __name__ == "__main__":
    unittest.main()
