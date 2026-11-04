"""설치 출처·동기화 경고와 레포 최소 버전 관문."""
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from gs import adapters, cli, config, doctor, version
from gs.check import check


class VersionSyncTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / '.goldstack').mkdir()
        self.config = self.repo / config.CONFIG_PATH
        self.config.write_text(config.DEFAULT_CONFIG.format(base='"main"'))

    def test_installation_reads_distribution_and_goldstack_plugin(self):
        dist = mock.Mock(version='0.1.0')
        dist.read_text.return_value = json.dumps({
            'url': 'ssh://git@example.test/kit',
            'vcs_info': {'vcs': 'git', 'commit_id': 'installed'}})
        with mock.patch('gs.version.metadata.distribution', return_value=dist), \
                mock.patch('gs.version.metadata.version', return_value='0.1.0'), \
                mock.patch('gs.adapters.claude_plugins', return_value=[
                    {'id': 'other@market', 'version': '8'},
                    {'id': 'goldstack@market', 'version': '0.2.0'}]) as plugins:
            self.assertEqual(version.installation(self.repo), version.Installation(
                '0.1.0', 'installed', 'ssh://git@example.test/kit', '0.2.0'))
        dist.read_text.assert_called_once_with('direct_url.json')
        plugins.assert_called_once_with(self.repo)

    def test_local_missing_and_unreadable_install_records_have_no_source(self):
        for raw in (None, '', '{bad', 'null', '[]', '{}',
                    '{"url":"file:///tmp/kit","dir_info":{"editable":true}}',
                    '{"url":"file:///tmp/kit","vcs_info":null}'):
            with self.subTest(raw=raw), \
                    mock.patch('gs.version.metadata.distribution') as distribution, \
                    mock.patch('gs.adapters.claude_plugins', side_effect=adapters.AdapterError('unreadable')):
                distribution.return_value.version = '0.1.0'
                distribution.return_value.read_text.return_value = raw
                self.assertEqual(version.installation(self.repo), version.Installation('0.1.0'))

    def warning(self, info, result=None, error=None):
        out = io.StringIO()
        with mock.patch('gs.version.installation', return_value=info), \
                mock.patch('gs.version.subprocess.run', return_value=result, side_effect=error) as run:
            version.warn(self.repo, out)
        return out.getvalue(), run

    def test_unreadable_distribution_record_still_warns_for_plugin(self):
        with mock.patch('gs.version.metadata.distribution', side_effect=OSError('metadata')), \
                mock.patch('gs.version.metadata.version', return_value='0.1.0'), \
                mock.patch('gs.adapters.claude_plugins', return_value=[
                    {'id': 'goldstack@market', 'version': '0.2.0'}]):
            self.assertEqual(version.installation(self.repo), version.Installation(
                '0.1.0', plugin_version='0.2.0'))

    def test_remote_main_mismatch_warns_and_uses_install_url_with_five_seconds(self):
        info = version.Installation('0.1.0', 'old', 'ssh://example.test/kit')
        text, run = self.warning(info, subprocess.CompletedProcess([], 0, 'new\trefs/heads/main\n'))
        self.assertEqual(text, '경고: 설치본이 main보다 뒤처짐 → gs self-update\n')
        self.assertEqual(run.call_args.args[0], ['git', 'ls-remote', info.url, 'main'])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)

    def test_equal_missing_and_failed_remote_are_silent(self):
        info = version.Installation('0.1.0', 'same', 'ssh://example.test/kit')
        for code, output in ((0, 'same\trefs/heads/main\n'), (1, 'other\trefs/heads/main\n'),
                             (0, ''), (0, 'other\trefs/tags/main\n')):
            self.assertEqual(self.warning(info, subprocess.CompletedProcess([], code, output))[0], '')
        for error in (OSError('offline'), subprocess.TimeoutExpired('git', 5)):
            self.assertEqual(self.warning(info, error=error)[0], '')
        text, run = self.warning(version.Installation('0.1.0'))
        self.assertEqual(text, '')
        run.assert_not_called()

    def test_plugin_mismatch_warns_even_if_remote_fails(self):
        info = version.Installation('0.1.0', 'old', 'ssh://example.test/kit', '0.2.0')
        self.assertEqual(self.warning(info, error=OSError())[0],
                         '경고: 플러그인 0.2.0 ≠ gs 0.1.0 → gs self-update\n')
        self.assertEqual(self.warning(version.Installation('0.1.0', plugin_version='0.1.0'))[0], '')

    def require(self, value):
        self.config.write_text(config.DEFAULT_CONFIG.format(base='"main"')
                               + '\n[goldstack]\nrequires = ' + value + '\n')

    def test_requirement_numeric_comparison_and_optional_section(self):
        cfg, problems = config.load(self.repo)
        self.assertEqual(cfg.goldstack.requires, '')
        self.assertEqual(problems, [])
        with mock.patch('gs.version.metadata.version', return_value='0.10.0'):
            for requirement in ('>=0.1', '>=0.9.99', '>=0.10', '>=0.10.0'):
                self.assertIsNone(version.requirement_error(requirement))
            self.assertIn('지금 0.10.0', version.requirement_error('>=0.11'))

    def test_check_rejects_malformed_and_unmet_requirement(self):
        for value in ('"0.2"', '">=0.x"', '""', '">=0.1,<1"', '2', 'true'):
            with self.subTest(value=value):
                self.require(value)
                feat, _ = check(self.repo, 'demo')
                self.assertTrue(any('goldstack.requires' in p.message for p in feat.errors))
        self.require('">=0.2"')
        with mock.patch('gs.version.metadata.version', return_value='0.1.0'):
            feat, _ = check(self.repo, 'demo')
        self.assertTrue(any(p.message == '이 레포는 goldstack >=0.2가 필요하다(지금 0.1.0) → gs self-update'
                            for p in feat.errors))

    def test_go_warns_once_and_blocks_before_running_any_feature(self):
        self.require('">=0.2"')
        for names in (['demo'], ['demo', 'next']):
            with self.subTest(names=names), mock.patch('gs.version.warn') as warn, \
                    mock.patch('gs.version.metadata.version', return_value='0.1.0'), \
                    mock.patch('gs.go.go') as go, redirect_stderr(io.StringIO()):
                self.assertEqual(cli.cmd_go(self.repo, names, None), 1)
                warn.assert_called_once()
                go.assert_not_called()
        self.require('">=0.1"')
        with mock.patch('gs.version.warn') as warn, mock.patch('gs.go.go', return_value=0) as go, \
                mock.patch('gs.version.metadata.version', return_value='0.1.0'):
            self.assertEqual(cli.cmd_go(self.repo, ['demo'], None), 0)
            warn.assert_called_once()
            go.assert_called_once_with(self.repo, 'demo', None)

    def test_check_cli_reports_requirement_error(self):
        self.require('">=0.2"')
        err = io.StringIO()
        with mock.patch('gs.version.metadata.version', return_value='0.1.0'), \
                redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(cli.cmd_check(self.repo, 'demo', None), 1)
        self.assertIn('이 레포는 goldstack >=0.2가 필요하다(지금 0.1.0) → gs self-update', err.getvalue())

    def test_go_continues_after_plugin_warning(self):
        err = io.StringIO()
        with mock.patch('gs.version.installation', return_value=version.Installation(
                '0.1.0', plugin_version='0.2.0')), \
                mock.patch('gs.go.go', return_value=0) as go, redirect_stderr(err):
            self.assertEqual(cli.cmd_go(self.repo, ['demo'], None), 0)
        go.assert_called_once()
        self.assertIn('경고: 플러그인 0.2.0 ≠ gs 0.1.0 → gs self-update', err.getvalue())

    def test_doctor_starts_with_warning_even_with_invalid_config(self):
        self.config.write_text('bad = [')
        out = io.StringIO()
        with mock.patch('gs.version.warn') as warn:
            self.assertEqual(doctor.doctor(self.repo, out), 1)
            warn.assert_called_once_with(self.repo, out)
