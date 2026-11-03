"""설정 스키마, 비밀 파일, 초기화와 CLI 사전 검사."""
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config
from support import isolate_git_env


CONFIG = '''[git]
remote = "upstream"
base = "release/stable"
[models]
judge = "judge-model"
claude_review = "review-model"
agy = "agy-model"
codex = "codex-model"
[timeouts]
review_minutes = 17
judge_minutes = 8
summary_seconds = 45
[notify]
telegram = true
'''


class ConfigTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / ".goldstack").mkdir()
        self.path = self.repo / config.CONFIG_PATH
        self.path.write_text(CONFIG, encoding="utf-8")

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), *args])
        return code, out.getvalue(), err.getvalue()

    def test_all_values(self):
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.assertEqual(cfg, config.Config(
            config.GitConfig("upstream", "release/stable"),
            config.ModelsConfig("judge-model", "review-model", "agy-model", "codex-model"),
            config.TimeoutsConfig(17, 8, 45), config.NotifyConfig(True)))

    def test_every_key_is_required(self):
        section = ""
        for line in CONFIG.splitlines():
            if line.startswith("["):
                section = line[1:-1]
            elif "=" in line:
                key = line.split("=", 1)[0].strip()
                with self.subTest(key=f"{section}.{key}"):
                    self.path.write_text(CONFIG.replace(line + "\n", ""))
                    cfg, problems = config.load(self.repo)
                    self.assertIsNone(cfg)
                    self.assertEqual(len(problems), 1)
                    self.assertEqual(problems[0].level, "오류")
                    self.assertIn(f"`{section}.{key}`", problems[0].message)

    def test_wrong_types_and_boolean_is_not_integer(self):
        cases = [(line, '"17"' if line.startswith(("review_minutes", "judge_minutes", "summary_seconds"))
                  else "17") for line in CONFIG.splitlines() if "=" in line]
        cases.extend(("review_minutes = 17", bad) for bad in ("true", "17.0", "[17]"))
        for line, bad in cases:
            key = line.split("=", 1)[0].strip()
            with self.subTest(key=key, bad=bad):
                self.path.write_text(CONFIG.replace(line, f"{key} = {bad}"))
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertTrue(any(p.level == "오류" and key in p.message for p in problems))

    def test_unknown_keys_are_warnings_and_errors_accumulate(self):
        self.path.write_text('extra = 3\n' + CONFIG.replace('[git]', '[git]\nowner = "me"')
                             + '\n[future]\nmode = "new"\n')
        cfg, problems = config.load(self.repo)
        self.assertIsNotNone(cfg)
        self.assertEqual([p.level for p in problems], ["경고"] * 3)
        for key in ("extra", "future", "git.owner"):
            self.assertTrue(any(f"`{key}`" in p.message for p in problems))
        self.path.write_text(self.path.read_text().replace('base = "release/stable"', '')
                             .replace("judge_minutes = 8", 'judge_minutes = "bad"'))
        cfg, problems = config.load(self.repo)
        self.assertIsNone(cfg)
        self.assertEqual(sum(p.level == "오류" for p in problems), 2)
        self.assertEqual(sum(p.level == "경고" for p in problems), 3)

    def test_missing_or_invalid_section_and_bad_toml(self):
        for text in ('', 'git = "wrong"\n', '[git]\nbase = ', '[git]\nbase = "a"\nbase = "b"\n'):
            with self.subTest(text=text):
                self.path.write_text(text)
                cfg, problems = config.load(self.repo)
                self.assertIsNone(cfg)
                self.assertTrue(problems)
                self.assertTrue(all(p.level == "오류" for p in problems))

    def test_local_env_only_reads_file_and_keeps_value_contents(self):
        with mock.patch.dict(os.environ, {"TG_TOKEN": "environment-secret", "OTHER": "ignored"}):
            self.assertEqual(config.read_local_env(self.repo), {})
            (self.repo / ".goldstack/local.env").write_text(
                "\n# comment\n  # indented comment\nTG_TOKEN=file-secret\n"
                "TG_CHAT_ID=\nOTHER = a=b # literal\nUNICODE=한글\n", encoding="utf-8")
            self.assertEqual(config.read_local_env(self.repo), {
                "TG_TOKEN": "file-secret", "TG_CHAT_ID": "", "OTHER": "a=b # literal", "UNICODE": "한글"})

    def test_config_command_outputs_one_line(self):
        for key, value in (("git.base", "release/stable"), ("git.remote", "upstream"),
                           ("timeouts.summary_seconds", "45"), ("notify.telegram", "true"),
                           ("models.codex", "codex-model")):
            with self.subTest(key=key):
                self.assertEqual(self.cli("config", key), (0, value + "\n", ""))
        self.path.write_text(CONFIG.replace('codex = "codex-model"', 'codex = ""')
                             .replace("telegram = true", "telegram = false"))
        self.assertEqual(self.cli("config", "models.codex"), (0, "\n", ""))
        self.assertEqual(self.cli("config", "notify.telegram"), (0, "false\n", ""))

    def test_config_command_rejects_unknown_keys_and_invalid_config(self):
        for key in ("nope.key", "git.nope", "git", "git.base.extra", "__dict__.git"):
            with self.subTest(key=key):
                code, out, err = self.cli("config", key)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("없는 설정 키", err)
        self.path.write_text(CONFIG.replace("review_minutes = 17", 'review_minutes = "bad"'))
        code, out, err = self.cli("config", "git.base")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("timeouts.review_minutes", err)

    def test_missing_config_stops_check_and_go_before_any_work(self):
        self.path.unlink()
        expected = "오류: .goldstack/config.toml이 없다. gs init을 먼저 실행하라"
        with mock.patch("gs.git.run") as git_run:
            for cmd in ("check", "go"):
                with self.subTest(cmd=cmd):
                    code, out, err = self.cli(cmd, "absent-feature")
                    self.assertEqual(code, 1)
                    self.assertIn(expected + "\n", err)
                    self.assertNotIn("feature 디렉터리", err)
            git_run.assert_not_called()
        self.assertFalse((self.repo / ".goldstack/work").exists())
        self.assertEqual(self.cli("config", "git.base"), (1, "", expected + "\n"))

    @mock.patch("gs.check.shutil.which", return_value="/test/cli")
    def test_check_and_go_reject_invalid_config_and_check_reports_warnings(self, _which):
        root = self.repo / ".goldstack/work/demo"
        (root / "tickets").mkdir(parents=True)
        (root / "spec.md").write_text('---\nfeature: demo\nverify: "true"\n---\n')
        (root / "tickets/01-a.md").write_text(
            '---\nid: "01"\ntitle: a\nblocked_by: []\nmodel: claude\nreviewer: codex\n---\n')
        self.path.write_text(CONFIG + "extra = 1\n")
        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=1:abc\nTG_CHAT_ID=42\n")  # telegram = true의 비밀 경고(06) 제외
        code, out, err = self.cli("check", "demo")
        self.assertEqual(code, 0)
        self.assertIn("경고 1", out)
        self.assertIn("알 수 없는 키 `notify.extra`", err)
        self.path.write_text(CONFIG.replace("telegram = true", 'telegram = "yes"'))
        for cmd in ("check", "go"):
            code, out, err = self.cli(cmd, "demo")
            self.assertEqual(code, 1)
            self.assertIn("notify.telegram", err)
        self.assertFalse((root / "run").exists())


class InitTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)

    def init(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["--repo", str(self.repo), "init"]), 0)
        return out.getvalue()

    def test_fallback_defaults_idempotence_and_no_commit(self):
        out = self.init()
        self.assertIn("origin/HEAD", out)
        self.assertIn("main", out)
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.assertEqual(cfg, config.Config(
            config.GitConfig("origin", "main"), config.ModelsConfig("opus", "opus", "gemini-4-argon-high", ""),
            config.TimeoutsConfig(30, 10, 60), config.NotifyConfig(False)))
        example = (self.repo / ".goldstack/local.env.example").read_text()
        self.assertIn("TG_TOKEN=\nTG_CHAT_ID=\n", example)
        self.assertIn("복사", example)
        self.assertFalse((self.repo / ".goldstack/local.env").exists())
        paths = [self.repo / config.CONFIG_PATH, self.repo / ".goldstack/local.env.example",
                 self.repo / ".gitignore"]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        second = self.init()
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths])
        self.assertEqual(second.count("그대로 둠:"), 3)
        self.assertNotIn("origin/HEAD", second)
        self.assertNotEqual(subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=self.repo,
                                          capture_output=True).returncode, 0)

    def test_remote_head_branch_is_detected(self):
        for base in ("release/stable", "배포/🚀"):
            with self.subTest(base=base):
                subprocess.run(["git", "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{base}"],
                               cwd=self.repo, check=True)
                out = self.init()
                self.assertNotIn("찾지 못해", out)
                self.assertEqual(config.load(self.repo)[0].git.base, base)
                (self.repo / config.CONFIG_PATH).unlink()

    def test_preserves_existing_files_and_appends_only_missing_ignore_lines(self):
        (self.repo / ".goldstack").mkdir()
        existing = {config.CONFIG_PATH: CONFIG, ".goldstack/local.env.example": "# custom example\n",
                    ".goldstack/local.env": "TG_TOKEN=secret\n"}
        for name, text in existing.items():
            (self.repo / name).write_text(text)
        (self.repo / ".gitignore").write_text("custom/\n.goldstack/local.env")
        out = self.init()
        self.assertNotIn("secret", out)
        self.assertIn(f"그대로 둠: {config.CONFIG_PATH}", out)
        self.assertIn("그대로 둠: .goldstack/local.env.example", out)
        for name, text in existing.items():
            self.assertEqual((self.repo / name).read_text(), text)
        self.assertEqual((self.repo / ".gitignore").read_text(),
                         "custom/\n.goldstack/local.env\n.goldstack/work/*/run/\n")
        self.init()
        self.assertEqual((self.repo / ".gitignore").read_text().count(".goldstack/local.env"), 1)


if __name__ == "__main__":
    unittest.main()
