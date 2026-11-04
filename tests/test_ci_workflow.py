"""GitHub Actions가 main/PR에서 Ubuntu 시험을 실행하는지 확인한다."""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/tests.yml"


class CiWorkflowTest(unittest.TestCase):
    def test_runs_tests_on_main_push_and_pull_request(self):
        content = WORKFLOW.read_text()
        self.assertIn("  push:\n    branches: [main]", content)
        self.assertIn("  pull_request:", content)
        self.assertIn("runs-on: ubuntu-latest", content)
        self.assertIn("timeout-minutes:", content)
        self.assertIn("run: uv run python -m unittest discover -s tests", content)

    def test_actions_are_pinned_and_permissions_are_read_only(self):
        content = WORKFLOW.read_text()
        self.assertIn("actions/checkout@v4.2.2", content)
        self.assertIn("astral-sh/setup-uv@v5.4.1", content)
        self.assertIn("permissions:\n  contents: read", content)
        self.assertNotIn("claude plugin validate", content)

    def test_configures_git_identity_for_tests(self):
        content = WORKFLOW.read_text()
        self.assertIn('git config --global user.name "GitHub Actions"', content)
        self.assertIn('git config --global user.email "github-actions[bot]@users.noreply.github.com"', content)
