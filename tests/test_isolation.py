"""claude worker·리뷰·판단 플러그인 격리: 명령 인자에 격리 옵션이 들어가는가.

실제 claude는 부르지 않는다. `claude plugin list --json`은 가짜 실행 파일(GS_CLAUDE)로 바꿔 끼운다.
격리 옵션이 실제로 goldstack hook을 남기고 다른 플러그인 skill을 빼는지는
docs/research/worker-plugin-isolation.md에 실제 실행으로 적었다.
"""
import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import adapters, config, report, review, state
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
        cases = {"exit": "echo boom >&2; exit 3", "not json": "echo nope", "not list": "echo '{}'", "decode": r"printf '\377'"}
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
                self.assertTrue(note.startswith("플러그인 격리 못 함: "), note)

    def test_missing_claude_binary(self):
        os.environ["GS_CLAUDE"] = str(self.root / "no-such-claude")
        a = adapters.Claude(MODELS)
        self.assertNotIn("--settings", a.command(self.inp))
        self.assertIn("가 없다", a.outcome(1, self.inp)[1])
        self.assertEqual(a.outcome(1, self.inp)[0], 1)

    def review_and_judge_argv(self, on_wait=None):
        argv, prompt, to_file = review.reviewer_argv(
            "claude", self.wt, "review prompt", self.root / "review.txt", MODELS, on_wait=on_wait)
        self.assertEqual((prompt, to_file), ("review prompt", False))
        return [(argv, "Read,Grep,Glob"),
                (review.judge_argv(SimpleNamespace(models=MODELS), cwd=self.wt, on_wait=on_wait), "Read")]

    def assert_readonly_isolation(self, argv, tools):
        self.assertEqual(argv[argv.index("--tools") + 1], tools)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(json.loads(argv[argv.index("--mcp-config") + 1]), {"mcpServers": {}})
        self.assertIn("--disable-slash-commands", argv)

    def test_review_and_judge_share_worker_isolation_in_their_worktree(self):
        os.environ.pop("GS_REVIEWER_CMD", None)
        calls = self.listing(PLUGINS)
        worker_argv = self.argv(adapters.Claude(MODELS).command(self.inp))
        expected = json.loads(worker_argv[worker_argv.index("--settings") + 1])
        for argv, tools in self.review_and_judge_argv():
            self.assert_readonly_isolation(argv, tools)
            self.assertEqual(json.loads(argv[argv.index("--settings") + 1]), expected)
        lines = calls.read_text().splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            cwd, args = line.split("|")
            self.assertEqual(os.path.realpath(cwd), os.path.realpath(self.wt))
            self.assertEqual(args, "plugin list --json")

    def test_review_and_judge_listing_failure_warns_and_keeps_other_isolation(self):
        os.environ.pop("GS_REVIEWER_CMD", None)
        for body in ("exit 3", "echo nope", "echo '{}'", r"printf '\377'", None):
            with self.subTest(body=body):
                if body is None:
                    os.environ["GS_CLAUDE"] = str(self.root / "missing")
                else:
                    self.fake_claude(body)
                with mock.patch("sys.stderr") as stderr:
                    commands = self.review_and_judge_argv()
                self.assertEqual("".join(c.args[0] for c in stderr.write.call_args_list)
                                 .count("플러그인 격리 못 함:"), 2)
                for argv, tools in commands:
                    self.assert_readonly_isolation(argv, tools)
                    self.assertNotIn("--settings", argv)

    def test_review_and_judge_warnings_are_queued_and_saved_in_report(self):
        os.environ.pop("GS_REVIEWER_CMD", None)
        self.fake_claude("exit 3")
        for caller in ("review", "judge", "summary"):
            with self.subTest(caller=caller):
                st = state.State("demo")
                pending = []
                save = mock.Mock()
                wait = review.CallWait(st, save, "01" if caller != "summary" else "", post=pending.append)
                with mock.patch("sys.stderr"):
                    if caller == "review":
                        review.reviewer_argv("claude", self.wt, "prompt", self.root / "out", MODELS, on_wait=wait)
                    else:
                        review.judge_argv(SimpleNamespace(models=MODELS), cwd=self.wt, on_wait=wait)
                self.assertEqual(st.tickets, {})  # 스레드는 상태를 직접 고치지 않는다.
                save.assert_not_called()
                self.assertEqual(len(pending), 1)
                pending[0]()
                save.assert_called_once()
                warnings = (st.tickets["01"].isolation_warnings if caller != "summary"
                            else st.finish["isolation_warnings"])
                self.assertEqual(len(warnings), 1)
                state.save(self.root, st)
                restored = state.load(self.root, "demo")
                risks = report.isolation_risks(SimpleNamespace(st=restored))
                self.assertIn("### 남은 위험", risks)
                self.assertIn(warnings[0], risks)

    def test_review_and_judge_seams_are_preserved(self):
        os.environ["GS_REVIEWER_CMD"] = "custom reviewer --flag"
        os.environ["GS_JUDGE"] = str(self.root / "custom judge")
        with mock.patch.object(adapters, "claude_plugins", return_value=[]) as listing:
            self.assertEqual(review.reviewer_argv("claude", self.wt, "prompt", self.root / "out", MODELS),
                             (["bash", "-c", "custom reviewer --flag"], "prompt", False))
            listing.assert_not_called()
            argv = review.judge_argv(SimpleNamespace(models=MODELS), model="summary-model", cwd=self.wt)
        self.assertEqual(argv[0], os.environ["GS_JUDGE"])
        self.assertEqual(argv[argv.index("--model") + 1], "summary-model")
        self.assert_readonly_isolation(argv, "Read")

    def test_plugins_to_disable_ignores_junk(self):
        got = adapters.plugins_to_disable([{"id": "a@m"}, {"id": ""}, {"id": 3}, {}, {"id": "a@m"},
                                           {"id": "goldstack"}, {"id": "goldstackx@m"}])
        self.assertEqual(got, ["a@m", "goldstackx@m"])

    def test_claude_plugins_raises_adapter_error(self):
        self.fake_claude("exit 1")
        with self.assertRaises(AdapterError):
            adapters.claude_plugins(self.wt)


class IsolationReportTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    tearDown, go, rundir, integration, final_report = G.tearDown, G.go, G.rundir, G.integration, G.final_report

    def setUp(self):
        self.G.setUp(self)
        os.environ.pop("GS_WORKER_CMD")  # 명령을 바꾸는 seam 대신 실제 Claude 어댑터 경로를 탄다
        os.environ["GS_CLAUDE"] = str(self.bin / "claude")
        (self.bin / "claude").write_text('''#!/bin/bash
here="$(dirname "$0")"
if [ "$1" = plugin ]; then
  if [ -f "$here/list-fails" ]; then echo 'listing denied' >&2; exit 3; fi
  echo '[]'; exit 0
fi
bash "$here/worker.sh"
''')

    def assert_report_warning(self):
        expected = "플러그인 격리 못 함: `claude plugin list --json` 종료 3: listing denied"
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.isolation_warnings, [expected])
        text = self.final_report()
        rows = [line for line in text.splitlines() if line.startswith("| 01 |")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].count(expected), 1)
        risks = text.split("### 남은 위험\n\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn(f"- 01: {expected}", risks)
        facts = (self.rundir / "finish/report-input.md").read_text()
        self.assertIn(f"### 남은 위험\n\n- 01: {expected}", facts)

    def test_listing_failure_still_runs_worker_and_reports_risk(self):
        (self.bin / "list-fails").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, state.MERGED)
        self.assert_report_warning()
        # 완료한 실행을 이어가도 경고가 사라지지 않는다.
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assert_report_warning()

    def test_codex_worker_claude_reviewer_reports_isolation_failure(self):
        os.environ["GS_WORKER_CMD"] = f"bash {self.bin / 'worker.sh'}"
        os.environ.pop("GS_REVIEWER_CMD")
        ticket = self.repo / ".goldstack/work/demo/tickets/01-t.md"
        ticket.write_text(ticket.read_text().replace("model: claude", "model: codex")
                          .replace("reviewer: codex", "reviewer: claude"))
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", "리뷰어 변경")
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        (self.bin / "claude").write_text("#!/bin/bash\n"
                                        "if [ \"$1\" = plugin ]; then echo 'listing denied' >&2; exit 3; fi\n"
                                        "echo '{\"findings\":[]}'\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual(ts.status, state.MERGED)
        self.assertEqual(ts.review["note"], "")
        self.assert_report_warning()

    def test_failed_worker_keeps_isolation_warning_in_result_and_risks(self):
        (self.bin / "list-fails").touch()
        (self.bin / "worker.sh").write_text("exit 7\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, state.FAILED)
        self.assert_report_warning()

    def test_successful_retry_preserves_first_attempt_warning(self):
        (self.bin / "list-fails").touch()
        (self.bin / "worker.sh").write_text('''here="$(dirname "$0")"
if [ -f "$here/list-fails" ]; then rm "$here/list-fails"; exit 7; fi
''' + support.FAKE_WORKER)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].attempts, 2)
        self.assert_report_warning()

    def test_fix_worker_isolation_failure_is_reported(self):
        # 구현은 격리에 성공하고, 리뷰 뒤 수정 worker만 목록 읽기에 실패한다.
        (self.bin / "worker.sh").write_text(support.FAKE_WORKER + '\ntouch "$here/list-fails"\n')
        (self.bin / "judge").write_text("#!/bin/bash\n" + support.FAKE_REVIEW_JUDGE)
        (self.bin / "findings.json").write_text(json.dumps({"findings": [{
            "severity": "high", "location": "file_01:1", "claim": "FIX value", "evidence": "test",
        }]}))
        with mock.patch.dict(os.environ, {"PY": sys.executable}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.bin / "fix.log").exists())
        self.assert_report_warning()

    def test_successful_isolation_has_no_warning_or_risk_section(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].isolation_warnings, [])
        self.assertNotIn("플러그인 격리 못 함", self.final_report())
        self.assertNotIn("### 남은 위험", self.final_report())


if __name__ == "__main__":
    unittest.main()
