"""GitHub Actions가 main/PR에서 Ubuntu 시험을 병렬로 돌리고, linux-only job이 병합 전 관문인지 확인한다(goldstack-v33 06)."""
from pathlib import Path
import re
import tomllib
import unittest

import support

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/tests.yml"
CONFIG = ROOT / ".goldstack/config.toml"


def job_block(content: str, job_id: str) -> str:
    """`jobs:` 아래 `  <job_id>:` 줄부터 다음 job(들여쓰기 2칸 키)까지."""
    match = re.search(rf"^  {re.escape(job_id)}:\n(?:(?!  \S).*\n?)*", content, re.M)
    assert match, job_id
    return match.group(0)


def job_names(content: str) -> list[str]:
    return re.findall(r"^    name: (\S+)\s*$", content, re.M)


class CiWorkflowTest(unittest.TestCase):
    def test_runs_tests_on_main_push_and_pull_request(self):
        content = WORKFLOW.read_text()
        self.assertIn("  push:\n    branches: [main]", content)
        self.assertIn("  pull_request:", content)
        self.assertEqual(content.count("runs-on: ubuntu-latest"), 2)
        self.assertEqual(content.count("timeout-minutes:"), 2)

    def test_has_two_named_jobs(self):
        content = WORKFLOW.read_text()
        self.assertIn("\n  linux-only:\n    name: linux-only\n", content)
        self.assertIn("\n  tests:\n    name: tests\n", content)
        self.assertEqual(sorted(job_names(content)), ["linux-only", "tests"])

    def test_linux_only_runs_landlock_files_with_required_flag(self):
        block = job_block(WORKFLOW.read_text(), "linux-only")
        self.assertIn('GS_REQUIRE_LANDLOCK: "1"', block)
        self.assertIn("-p test_jail.py", block)
        self.assertIn("-p test_sandbox_launch.py", block)
        self.assertNotIn("xargs", block)

    def test_tests_job_runs_files_in_parallel_without_uv_run(self):
        block = job_block(WORKFLOW.read_text(), "tests")
        self.assertIn("uv sync --locked", block)
        self.assertIn("""ls tests | grep '^test_' | xargs -P "$(nproc)" -n 1 .venv/bin/python -m unittest discover -s tests -p""",
                      block)
        self.assertNotIn("uv run", block)
        self.assertNotIn("GS_REQUIRE_LANDLOCK", block)

    def test_actions_are_pinned_and_permissions_are_read_only(self):
        content = WORKFLOW.read_text()
        self.assertEqual(content.count("actions/checkout@v4.2.2"), 2)
        self.assertEqual(content.count("astral-sh/setup-uv@v5.4.1"), 2)
        self.assertIn("permissions:\n  contents: read", content)
        self.assertNotIn("claude plugin validate", content)

    def test_configures_git_identity_for_tests_in_both_jobs(self):
        content = WORKFLOW.read_text()
        for job in ("linux-only", "tests"):
            block = job_block(content, job)
            self.assertIn('git config --global user.name "GitHub Actions"', block)
            self.assertIn('git config --global user.email "github-actions[bot]@users.noreply.github.com"', block)


class ConfigChecksTest(unittest.TestCase):
    def test_config_waits_for_linux_only(self):
        git = tomllib.loads(CONFIG.read_text())["git"]
        self.assertIs(git["wait_checks"], True)
        self.assertEqual(git["checks"], ["linux-only"])

    def test_every_config_check_is_a_job_name_not_a_job_id(self):
        names = job_names(WORKFLOW.read_text())
        for check in tomllib.loads(CONFIG.read_text())["git"]["checks"]:
            self.assertIn(check, names)


class LandlockGateTest(unittest.TestCase):
    """`GS_REQUIRE_LANDLOCK=1`일 때 Landlock을 못 쓰면 skip 대신 실패한다(맥에서도 돈다)."""

    def test_available_runs(self):
        for env in ({}, {"GS_REQUIRE_LANDLOCK": "1"}):
            self.assertEqual(support.landlock_gate(3, env), ("run", ""))

    def test_unavailable_skips_without_the_variable(self):
        for env in ({}, {"GS_REQUIRE_LANDLOCK": ""}, {"GS_REQUIRE_LANDLOCK": "0"}):
            action, _ = support.landlock_gate(0, env)
            self.assertEqual(action, "skip")

    def test_unavailable_fails_with_the_variable(self):
        action, reason = support.landlock_gate(0, {"GS_REQUIRE_LANDLOCK": "1"})
        self.assertEqual(action, "fail")
        self.assertIn("GS_REQUIRE_LANDLOCK", reason)

    def test_decorator_skips_or_fails_each_test(self):
        def make(env):
            @support.requires_landlock(0, env)
            class Sample(unittest.TestCase):
                def test_a(self):
                    pass

                def test_b(self):
                    pass
            return Sample

        for env, outcome in (({}, "skipped"), ({"GS_REQUIRE_LANDLOCK": "1"}, "failures")):
            result = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(make(env)).run(result)
            self.assertEqual(len(getattr(result, outcome)), 2, outcome)
            if outcome == "failures":
                self.assertIn("GS_REQUIRE_LANDLOCK", result.failures[0][1])

    def test_decorator_keeps_class_when_available(self):
        class Sample(unittest.TestCase):
            def test_a(self):
                pass

        self.assertIs(support.requires_landlock(1, {"GS_REQUIRE_LANDLOCK": "1"})(Sample), Sample)

    def test_skip_or_fail_inside_a_test(self):
        case = unittest.TestCase()
        with self.assertRaises(unittest.SkipTest):
            support.skip_or_fail_landlock(case, "x", {})
        with self.assertRaises(AssertionError) as caught:
            support.skip_or_fail_landlock(case, "x", {"GS_REQUIRE_LANDLOCK": "1"})
        self.assertIn("GS_REQUIRE_LANDLOCK", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
