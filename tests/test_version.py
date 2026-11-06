"""릴리스 버전 일치와 설치된 메타데이터를 쓰는 CLI 시험."""
import io
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from importlib import metadata
from pathlib import Path
from unittest import mock

from gs import cli


class VersionTest(unittest.TestCase):
    def test_release_versions_match_installed_metadata(self):
        root = Path(__file__).resolve().parents[1]
        project = tomllib.loads((root / "pyproject.toml").read_text())
        plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(project["project"]["version"], "0.2.2")
        self.assertEqual(plugin["version"], project["project"]["version"])
        self.assertEqual(metadata.version("goldstack"), project["project"]["version"])

    def test_version_reads_package_metadata_without_finding_repo(self):
        out = io.StringIO()
        with mock.patch("gs.cli.metadata.version", return_value="9.8.7") as version, \
                mock.patch("gs.cli.featmod.find_repo_root") as find_repo, redirect_stdout(out):
            with self.assertRaises(SystemExit) as raised:
                cli.main(["--version"])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(out.getvalue(), "gs 9.8.7\n")
        version.assert_called_once_with("goldstack")
        find_repo.assert_not_called()

    def test_version_succeeds_outside_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-m", "gs.cli", "--version"],
                                    cwd=directory, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "gs 0.2.1\n", ""))
