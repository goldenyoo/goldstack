"""설치 기록 유형별 시작 경고. 네트워크는 호출하지 않는다."""
import io
import unittest
from pathlib import Path
from unittest import mock

from gs import version


class LocalInstallWarningTest(unittest.TestCase):
    def warn_for(self, raw):
        dist = mock.Mock()
        dist.read_text.return_value = raw
        out = io.StringIO()
        with mock.patch.object(version.metadata, "version", return_value="0.1.0"), \
                mock.patch.object(version.metadata, "distribution", return_value=dist), \
                mock.patch("gs.adapters.claude_plugins", return_value=[]), \
                mock.patch.object(version.subprocess, "run") as run:
            version.warn(Path("."), out)
        return out.getvalue(), run

    def test_local_directory_install_warns_without_blocking(self):
        out, run = self.warn_for('{"dir_info": {"editable": false}}')
        self.assertEqual(out, "경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다\n")
        run.assert_not_called()

    def test_git_install_keeps_remote_comparison(self):
        out, run = self.warn_for(
            '{"url":"https://example.invalid/repo.git",'
            '"vcs_info":{"vcs":"git","commit_id":"abc"}}')
        run.assert_called_once()
        self.assertNotIn("설치 commit 모름", out)

    def test_missing_install_record_stays_silent(self):
        out, run = self.warn_for(None)
        self.assertEqual(out, "")
        run.assert_not_called()

