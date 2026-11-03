"""adopt 설정과 가짜 GS_GH를 통한 doctor 조회·부분 수정."""
import contextlib
import io
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config, doctor, git
import test_check
import test_config
from support import isolate_git_env


class AdoptConfigTest(unittest.TestCase):
    setUp = test_config.ConfigTest.setUp
    cli = test_config.ConfigTest.cli

    def test_defaults_in_legacy_config_and_init_example(self):
        expected = {"git.merge_method": "merge", "git.direct_push": "true", "git.wait_checks": "false",
                    "timeouts.checks_minutes": "60", "timeouts.setup_minutes": "15", "worktree.setup": ""}
        for text in (test_config.CONFIG, config.DEFAULT_CONFIG.format(base='"main"')):
            self.path.write_text(text)
            for key, value in expected.items():
                with self.subTest(key=key, text=text):
                    self.assertEqual(self.cli("config", key), (0, value + "\n", ""))
            if text != test_config.CONFIG:
                for key in expected:
                    section, name = key.split(".")
                    self.assertIn(name, tomllib.loads(text)[section])

    def test_explicit_values(self):
        text = config.DEFAULT_CONFIG.format(base='"main"')
        for old, new in [('merge_method = "merge"', 'merge_method = "squash"'),
                         ('direct_push = true', 'direct_push = false'),
                         ('wait_checks = false', 'wait_checks = true'),
                         ('checks_minutes = 60', 'checks_minutes = 2'),
                         ('setup_minutes = 15', 'setup_minutes = 3'),
                         ('setup = ""', 'setup = "uv sync"')]:
            text = text.replace(old, new)
        self.path.write_text(text)
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.assertEqual(cfg.git, config.GitConfig("origin", "main", "squash", False, True))
        self.assertEqual(cfg.timeouts.checks_minutes, 2)
        self.assertEqual(cfg.timeouts.setup_minutes, 3)
        self.assertEqual(cfg.worktree.setup, "uv sync")


class AdoptCheckTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def test_invalid_new_values_are_check_errors(self):
        self.write("01-a.md", test_check.ticket("01"))
        path = self.repo / config.CONFIG_PATH
        original = path.read_text()
        cases = [('merge_method = "merge"', bad) for bad in ('"rebase"', '""', 'true', '3')]
        cases += [('checks_minutes = 60', bad) for bad in ('0', '-1', 'true', '"60"')]
        cases += [('setup_minutes = 15', bad) for bad in ('0', '-2', 'false', '1.5')]
        cases += [('direct_push = true', '"true"'), ('wait_checks = false', '0'), ('setup = ""', 'false')]
        for line, bad in cases:
            key = line.split(" = ")[0]
            with self.subTest(key=key, bad=bad):
                path.write_text(original.replace(line, f"{key} = {bad}"))
                code, out, err = self.run_check()
                self.assertEqual(code, 1, out + err)
                self.assertIn(key, err)


class DoctorTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        git.run(self.repo, "init", "-q")
        git.run(self.repo, "remote", "add", "origin", "https://github.com/wrong/repo.git")
        git.run(self.repo, "remote", "add", "upstream", "git@github.com:owner/project.git")
        (self.repo / ".goldstack").mkdir()
        self.path = self.repo / config.CONFIG_PATH
        self.original = config.DEFAULT_CONFIG.format(base='"release/stable"').replace('remote = "origin"',
                                                                                   'remote = "upstream"')
        self.path.write_text(self.original)
        self.root = "repos/owner/project"
        self.protection = self.root + "/branches/release%2Fstable/protection"
        self.rules = self.root + "/rules/branches/release%2Fstable"
        self.responses = {
            self.root: {"allow_merge_commit": False, "allow_squash_merge": True, "allow_rebase_merge": True},
            self.protection: {"required_pull_request_reviews": None, "required_status_checks": None},
        }
        fake = self.repo / "gh"
        fake.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
p = Path(__file__).parent
with (p / "calls").open("a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if len(sys.argv) != 3 or sys.argv[1] != "api":
    sys.exit(2)
response = json.loads((p / "responses.json").read_text()).get(sys.argv[2], {{"error": "HTTP 404"}})
if isinstance(response, dict) and "error" in response:
    print(response["error"], file=sys.stderr)
    sys.exit(1)
if isinstance(response, dict) and "raw" in response:
    print(response["raw"])
else:
    print(json.dumps(response))
''')
        fake.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"GS_GH": str(fake)})
        patch.start()
        self.addCleanup(patch.stop)

    def command(self, *args):
        (self.repo / "responses.json").write_text(json.dumps(self.responses))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), *args])
        self.assertEqual(err.getvalue(), "")
        return code, out.getvalue()

    def protect(self):
        self.responses[self.protection] = {
            "required_pull_request_reviews": {"required_approving_review_count": 2},
            "required_status_checks": {"contexts": ["build"], "checks": [{"context": "test"}, {"context": "build"}]},
        }

    def test_squash_configured_remote_and_encoded_base_read_only(self):
        before = self.path.stat().st_mtime_ns
        code, out = self.command("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("gs doctor: owner/project (원격 upstream", out)
        self.assertIn('→ git.merge_method = "squash"', out)
        self.assertIn("직접 push 제한 없음", out)
        self.assertIn("필수 승인  0명", out)
        self.assertIn("필수 검사  없음", out)
        self.assertEqual(self.path.read_text(), self.original)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        calls = [json.loads(x) for x in (self.repo / "calls").read_text().splitlines()]
        self.assertEqual(calls, [["api", self.root], ["api", self.protection]])

    def test_merge_preferred_and_unsupported_methods_warn(self):
        self.responses[self.root]["allow_merge_commit"] = True
        self.assertIn('→ git.merge_method = "merge"', self.command("doctor")[1])
        self.responses[self.root].update(allow_merge_commit=False, allow_squash_merge=False)
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertIn("gs가 지원하지 않는 병합 방식", out)
        self.assertNotIn("→ git.merge_method", out)
        self.assertEqual(self.path.read_text(), self.original)

    def test_protection_approvals_and_required_check_names(self):
        self.protect()
        code, out = self.command("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("release/stable 직접 push 금지 → git.direct_push = false", out)
        self.assertIn("2명 → gs는 PR을 열고 승인을 기다린다", out)
        self.assertIn("build, test → git.wait_checks = true", out)

    def test_rulesets_fallback_combines_required_approvals_and_checks(self):
        self.responses[self.protection] = {"error": "HTTP 403: Resource not accessible"}
        self.responses[self.rules] = [
            {"type": "pull_request", "parameters": {"required_approving_review_count": 1}},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 3}},
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "CI"}]}},
        ]
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertIn("3명", out)
        self.assertIn("CI → git.wait_checks = true", out)
        cfg, _ = config.load(self.repo)
        self.assertFalse(cfg.git.direct_push)
        self.assertTrue(cfg.git.wait_checks)

    def test_classic_checks_or_signatures_alone_disable_direct_push(self):
        cases = [
            {"required_status_checks": {"contexts": ["CI"]}},
            {"required_status_checks": {"checks": [{"context": "CI"}]}},
            {"required_signatures": {"enabled": True}},
        ]
        for protection in cases:
            with self.subTest(protection=protection):
                self.path.write_text(self.original)
                self.responses[self.protection] = protection
                code, out = self.command("doctor", "--write")
                self.assertEqual(code, 0, out)
                self.assertIn("직접 push 금지 → git.direct_push = false", out)
                cfg, _ = config.load(self.repo)
                self.assertFalse(cfg.git.direct_push)
                self.assertEqual(cfg.git.wait_checks, "required_status_checks" in protection)

    def test_ruleset_checks_or_signatures_alone_disable_direct_push(self):
        self.responses[self.protection] = {"error": "HTTP 403"}
        for rule in (
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "CI"}]}},
            {"type": "required_signatures"},
        ):
            with self.subTest(rule=rule):
                self.path.write_text(self.original)
                self.responses[self.rules] = [rule]
                code, out = self.command("doctor", "--write")
                self.assertEqual(code, 0, out)
                self.assertIn("직접 push 금지 → git.direct_push = false", out)
                cfg, _ = config.load(self.repo)
                self.assertFalse(cfg.git.direct_push)
                self.assertEqual(cfg.git.wait_checks, rule["type"] == "required_status_checks")

    def test_disabled_signatures_and_empty_checks_do_not_disable_direct_push(self):
        self.responses[self.protection] = {
            "required_status_checks": {"contexts": [], "checks": []},
            "required_signatures": {"enabled": False},
        }
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertIn("직접 push 제한 없음", out)
        self.assertTrue(config.load(self.repo)[0].git.direct_push)

    def test_permission_failures_unknown_values_never_written(self):
        for endpoint in (self.root, self.protection, self.rules):
            self.responses[endpoint] = {"error": "HTTP 403: no permission"}
        before = self.path.stat().st_mtime_ns
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        for label in ("병합 방식", "base 보호", "필수 승인", "필수 검사"):
            self.assertIn(label + "  모름(", out)
        self.assertIn("HTTP 403", out)
        self.assertNotIn("→ git.", out)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(self.path.read_text(), self.original)

    def test_empty_rulesets_do_not_claim_unknown_classic_protection_absent(self):
        self.responses[self.protection] = {"error": "HTTP 403"}
        self.responses[self.rules] = []
        code, out = self.command("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("base 보호  모름(", out)
        self.assertIn("필수 검사  모름(", out)

    def test_non_github_remote_makes_no_gh_calls_or_writes(self):
        git.run(self.repo, "remote", "set-url", "upstream", "https://gitlab.com/owner/project.git")
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertIn("GitHub 원격 아님", out)
        self.assertIn("모름(", out)
        self.assertFalse((self.repo / "calls").exists())
        self.assertEqual(self.path.read_text(), self.original)

    def test_write_overwrites_only_proposals_preserving_comments_order_and_crlf(self):
        self.protect()
        before = (self.original.replace('[git]', '# header\n[git] # git settings')
                  .replace('merge_method = "merge"', "  merge_method = 'merge'  # choose method")
                  .replace('direct_push = true', 'direct_push = true # push comment')
                  .replace('setup = ""', 'setup = "echo \\\"# literal\\\"" # setup comment')
                  .replace('\n', '\r\n'))
        self.path.write_bytes(before.encode())
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        expected = (before.replace("merge_method = 'merge'", 'merge_method = "squash"')
                    .replace('direct_push = true', 'direct_push = false')
                    .replace('wait_checks = false', 'wait_checks = true'))
        self.assertEqual(self.path.read_bytes(), expected.encode())
        self.assertIn('git.merge_method: "merge" → "squash" (', out)
        self.assertIn('git.direct_push: true → false (', out)
        self.assertIn('git.wait_checks: false → true (', out)
        before_mtime = self.path.stat().st_mtime_ns
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertNotIn('git.merge_method:', out)
        self.assertEqual(self.path.stat().st_mtime_ns, before_mtime)

    def test_write_missing_legacy_keys_and_does_not_reset_nonproposals(self):
        self.protect()
        self.path.write_text(test_config.CONFIG)
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.assertEqual(cfg.git, config.GitConfig("upstream", "release/stable", "squash", False, True))
        self.assertEqual(cfg.models.judge, "judge-model")
        self.responses[self.protection] = {}
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        cfg, _ = config.load(self.repo)
        self.assertFalse(cfg.git.direct_push)
        self.assertTrue(cfg.git.wait_checks)

    def test_write_quoted_dotted_and_inline_git_preserves_other_values(self):
        self.protect()
        git_section, rest = self.original.split('[worktree]', 1)
        for header in ('["git"] # settings', '  [ "git" ] # settings', None, "inline"):
            with self.subTest(header=header):
                if header == "inline":
                    git_text = 'git = {remote = "upstream", base = "release/stable", merge_method = "merge"} # inline\n\n'
                elif header is None:
                    git_text = '\n'.join('git.' + line if '=' in line else line
                                         for line in git_section.splitlines()[1:]) + '\n'
                else:
                    git_text = (git_section.replace('[git]', header).replace('merge_method', '"merge_method"')
                                .replace('direct_push = true\n', '').replace('wait_checks = false\n', ''))
                self.path.write_text(git_text + '[worktree]' + rest)
                code, out = self.command("doctor", "--write")
                self.assertEqual(code, 0, out)
                cfg, problems = config.load(self.repo)
                self.assertEqual(problems, [])
                self.assertEqual(cfg.git, config.GitConfig("upstream", "release/stable", "squash", False, True))
                self.assertTrue(self.path.read_text().endswith('[worktree]' + rest))

    def test_write_ignores_assignment_lookalikes_in_multiline_setup_string(self):
        self.protect()
        text = self.original.replace('setup = ""', '''setup = """
[git]
merge_method = "merge"
direct_push = true
wait_checks = false
"""''')
        self.path.write_text(text)
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        self.assertEqual(config.load(self.repo)[0].worktree.setup,
                         '[git]\nmerge_method = "merge"\ndirect_push = true\nwait_checks = false\n')

    def test_verify_noop_warnings_and_real_command(self):
        spec = self.repo / ".goldstack/work/demo/spec.md"
        spec.parent.mkdir(parents=True)
        for verify in ('true', ':', None, 'python -m unittest'):
            with self.subTest(verify=verify):
                line = f'verify: {json.dumps(verify)}\n' if verify else ''
                spec.write_text(f'---\nfeature: demo\n{line}---\n')
                code, out = self.command("doctor")
                self.assertEqual(code, 0, out)
                self.assertEqual("검증 없음, 리뷰만으로 병합" in out, verify != 'python -m unittest')

    def test_init_runs_doctor_once_without_writing_and_survives_gh_failure(self):
        self.protect()
        code, out = self.command("init")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("gs doctor:"), 1)
        self.assertEqual(self.path.read_text(), self.original)
        for value in ({"error": "HTTP 500"}, {"raw": "not json"}, []):
            self.responses[self.root] = self.responses[self.protection] = self.responses[self.rules] = value
            code, out = self.command("init")
            self.assertEqual(code, 0, out)
            self.assertIn("모름(", out)
        with mock.patch.dict(os.environ, {"GS_GH": str(self.repo / "absent-gh")}):
            code, out = self.command("init")
        self.assertEqual(code, 0, out)
        self.assertIn("모름(", out)

    def test_timeout_is_unknown_and_init_succeeds(self):
        with mock.patch("gs.doctor._api", side_effect=doctor.ReadError("gh 시간 초과")):
            code, out = self.command("init")
        self.assertEqual(code, 0, out)
        self.assertIn("모름(gh 시간 초과)", out)


if __name__ == "__main__":
    unittest.main()
