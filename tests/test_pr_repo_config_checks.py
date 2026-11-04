"""PR 저장소 지정과 실행 전에 잡아야 하는 설정·CLI 오류(티켓 01)."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_check
import support
from gs import cli, config, finish, git


class ConfigChecksTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def command(self, name):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), name, "demo"])
        return code, out.getvalue(), err.getvalue()

    def assert_stops(self, message):
        for command in ("check", "go"):
            with self.subTest(command=command):
                code, out, err = self.command(command)
                self.assertEqual(code, 1, out + err)
                self.assertIn(message, err)
                if command == "go":
                    self.assertIn("아무것도 띄우지 않았다", err)
        self.assertFalse((self.tickets.parent / "run").exists())

    def test_each_timeout_must_be_positive(self):
        self.write("01-a.md", test_check.ticket("01"))
        path = self.repo / config.CONFIG_PATH
        original = path.read_text()
        for key, default in (("review_minutes", 30), ("judge_minutes", 10), ("summary_seconds", 60)):
            for value in (0, -1):
                with self.subTest(key=key, value=value):
                    path.write_text(original.replace(f"{key} = {default}", f"{key} = {value}"))
                    self.assert_stops(f"`timeouts.{key}`는 0보다 커야 한다")
            path.write_text(original.replace(f"{key} = {default}", f"{key} = 1"))
            self.assertEqual(self.run_check()[::2], (0, ""))

    def test_non_codex_models_must_not_be_empty(self):
        self.write("01-a.md", test_check.ticket("01"))
        path = self.repo / config.CONFIG_PATH
        original = path.read_text()
        for key, default in (("judge", "opus"), ("claude_review", "opus"), ("agy", "gemini-4-argon-high")):
            for value in ("", " \t "):
                with self.subTest(key=key, value=value):
                    path.write_text(original.replace(f'{key} = "{default}"', f"{key} = {json.dumps(value)}"))
                    self.assert_stops(f"`models.{key}`는 비어 있으면 안 된다")
        path.write_text(original)  # models.codex = ""는 CLI 기본 모델을 뜻한다.
        self.assertEqual(config.load(self.repo)[0].models.codex, "")
        self.assertEqual(self.run_check()[::2], (0, ""))

    def test_claude_is_required_even_without_claude_tickets(self):
        self.write("01-a.md", test_check.ticket("01", model="codex", reviewer="agy"))
        self.assertEqual(self.run_check()[::2], (0, ""))
        (self.bin / "claude").unlink()  # PATH는 이 시험의 bin만 포함한다.
        self.assert_stops("CLI `claude`가 PATH에 없다")

    def test_non_github_remote_stops_go_before_launching(self):
        self.write("01-a.md", test_check.ticket("01"))
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('remote = "origin"', 'remote = "upstream"'))
        git.run(self.repo, "remote", "add", "upstream", "https://gitlab.com/owner/repo.git")
        for url in ("https://gitlab.com/owner/repo.git", "git@gitlab.com:owner/repo.git",
                    "/tmp/github.com/repo.git", "https://github.com.example.org/owner/repo.git",
                    "https://github.com/owner", "https://github.com/owner/repo/extra",
                    "https://github.com/owner/repo?query=bad", "ftp://github.com/owner/repo.git"):
            with self.subTest(url=url):
                git.run(self.repo, "remote", "set-url", "upstream", url)
                with mock.patch("gs.go.worker.make_runner") as start, mock.patch("gs.go.herdr.tab_create") as herdr:
                    self.assert_stops(f"원격 `upstream`의 URL `{url}`은 GitHub 저장소 형식이 아니다")
                start.assert_not_called()
                herdr.assert_not_called()


class PrRepoTest(unittest.TestCase):
    def test_all_url_forms_and_pr_commands_use_configured_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git.run(repo, "init", "-q")
            git.run(repo, "remote", "add", "origin", "https://github.com/other/origin.git")
            git.run(repo, "remote", "add", "upstream", "https://github.com/owner/repo.git")
            fake = repo / "gh"
            fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            run = SimpleNamespace(repo=repo, remote="upstream")
            with mock.patch.dict(os.environ, {"GS_GH": str(fake)}):
                for prefix in ("https://github.com/", "git@github.com:", "ssh://git@github.com/"):
                    for suffix in ("", ".git", ".GIT", ".GiT"):
                        url = prefix + "owner/repo" + suffix
                        git.run(repo, "remote", "set-url", "upstream", url)
                        for command in ("view", "list", "create", "edit", "merge"):
                            with self.subTest(url=url, command=command):
                                args = finish._gh(run, command).splitlines()
                                self.assertEqual(args, ["pr", command, "--repo", "owner/repo"])


class UpstreamGoTest(unittest.TestCase):
    BASE, REMOTE = "main", "upstream"
    setUp, tearDown, go = support.GoTest.setUp, support.GoTest.tearDown, support.GoTest.go
    rundir = support.GoTest.rundir

    def test_full_finish_uses_upstream_with_two_remotes_and_local_mirror(self):
        git.run(self.repo, "remote", "add", "origin", "https://github.com/other/origin.git")
        self.assertEqual(git.out(self.repo, "remote", "get-url", "upstream"), str(self.remote))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        calls = (self.bin / "gh.log").read_text().splitlines()
        commands = set()
        for call in calls:
            args = call.split()
            commands.add(args[1])
            self.assertEqual(args[-2:], ["--repo", "test/upstream"], call)
        self.assertEqual(commands, {"view", "list", "create", "edit", "merge"})
