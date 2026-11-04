"""외부 설치 명령을 가짜 실행 파일로 바꾼 self-update 시험."""
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from gs import cli, selfupdate


FAKE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
root = Path(os.environ['UPDATE_FIXTURE'])
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / 'calls').open('a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'uv':
    if os.environ.get('FAIL_UV'):
        print('fatal: Authentication failed for private repository', file=sys.stderr)
        sys.exit(1)
    (root / 'cli-version').write_text('2.0.0')
    (root / 'gs/CHANGELOG.md').write_text('## 2.0.0 — 새 릴리스\\n')
elif args == ['plugin', 'list', '--json']:
    print(json.dumps([{'id': 'goldstack@goldstack', 'version': (root / 'plugin-version').read_text()}]))
elif os.environ.get('FAIL_PLUGIN') == ('marketplace' if 'marketplace' in args else 'update'):
    print('plugin update failed', file=sys.stderr)
    sys.exit(1)
elif args == ['plugin', 'update', 'goldstack@goldstack']:
    (root / 'plugin-version').write_text('2.0.0')
'''


class SelfUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'gs').mkdir()
        (self.root / 'gs/CHANGELOG.md').write_text('## 1.0.0 — 이전\n')
        for name in ('uv', 'claude'):
            binary = self.root / name
            binary.write_text(FAKE)
            binary.chmod(0o755)
        (self.root / 'cli-version').write_text('1.0.0')
        (self.root / 'plugin-version').write_text('1.0.0')
        self.env = mock.patch.dict(os.environ, {
            'GS_UV': str(self.root / 'uv'), 'GS_CLAUDE': str(self.root / 'claude'),
            'UPDATE_FIXTURE': str(self.root), 'FAIL_UV': '', 'FAIL_PLUGIN': '',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dist = mock.Mock()
        self.dist.read_text.return_value = json.dumps({
            'url': 'https://example.test/private/goldstack.git',
            'vcs_info': {'vcs': 'git', 'commit_id': 'abc'},
        })
        self.dist.locate_file.side_effect = lambda name: self.root / name
        for patcher in (
                mock.patch('gs.version.metadata.distribution', return_value=self.dist),
                mock.patch('gs.version.metadata.version', side_effect=lambda _: (self.root / 'cli-version').read_text()),
                mock.patch('gs.selfupdate.running_go', return_value=[])):
            patcher.start()
            self.addCleanup(patcher.stop)

    def calls(self):
        path = self.root / 'calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def run_update(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(['self-update', *args])
        return code, out.getvalue(), err.getvalue()

    def test_main_updates_both_and_shows_fresh_versions_and_changelog(self):
        code, out, err = self.run_update()
        self.assertEqual(code, 0, err)
        mutations = [call for call in self.calls() if call[1:] != ['plugin', 'list', '--json']]
        self.assertEqual(mutations, [
            ['uv', 'tool', 'install', '--reinstall', 'git+https://example.test/private/goldstack.git@main'],
            ['claude', 'plugin', 'marketplace', 'update', 'goldstack'],
            ['claude', 'plugin', 'update', 'goldstack@goldstack'],
        ])
        self.assertIn('CLI: 성공 — gs 2.0.0', out)
        self.assertIn('플러그인: 성공 — goldstack 2.0.0', out)
        self.assertIn('CHANGELOG.md: 2.0.0 — 새 릴리스', out)
        self.assertIn(selfupdate.LIMIT, out)

    def test_explicit_source_and_tag_work_outside_repo(self):
        with mock.patch('gs.cli.featmod.find_repo_root') as find:
            code, _, err = self.run_update('--from', 'git+ssh://git@example.test/gs.git', '--version', 'v2')
        self.assertEqual(code, 0, err)
        self.assertIn(['uv', 'tool', 'install', '--reinstall', 'git+ssh://git@example.test/gs.git@v2'], self.calls())
        find.assert_not_called()

    def test_local_install_needs_from_and_changes_nothing(self):
        self.dist.read_text.return_value = '{"url": "file:///tmp/local"}'
        code, _, err = self.run_update()
        self.assertEqual(code, 1)
        self.assertIn('--from <주소>', err)
        self.assertFalse(any(call[0] == 'uv' or 'update' in call for call in self.calls()))

    def test_running_go_refuses_before_any_external_installation_query(self):
        with mock.patch('gs.selfupdate.running_go', return_value=[42]), \
                mock.patch('gs.selfupdate.version.installation') as installation:
            code, out, err = self.run_update()
        self.assertEqual(code, 1)
        self.assertIn('PID 42', err)
        self.assertIn(selfupdate.LIMIT, out)
        installation.assert_not_called()
        self.assertEqual(self.calls(), [])

    def test_process_query_failure_refuses(self):
        with mock.patch('gs.selfupdate.running_go', side_effect=OSError('denied')):
            code, _, err = self.run_update()
        self.assertEqual(code, 1)
        self.assertIn('프로세스를 확인할 수 없다', err)
        self.assertEqual(self.calls(), [])

    def test_auth_failure_explains_recovery_and_cli_result(self):
        with mock.patch.dict(os.environ, {'FAIL_UV': '1'}):
            code, out, err = self.run_update()
        self.assertEqual(code, 1)
        self.assertIn('CLI: 실패 — gs 1.0.0', out)
        self.assertIn('gh auth login', err)
        self.assertIn('git 자격 증명', err)
        self.assertFalse(any('update' in call for call in self.calls()))

    def test_plugin_failures_preserve_cli_success_and_exit_one(self):
        for failure in ('marketplace', 'update'):
            with self.subTest(failure=failure), mock.patch.dict(os.environ, {'FAIL_PLUGIN': failure}):
                code, out, err = self.run_update()
                self.assertEqual(code, 1)
                self.assertIn('CLI: 성공 — gs 2.0.0', out)
                self.assertIn('플러그인: 실패/미실행', out)
                self.assertIn('plugin update failed', err)

    def test_help_mentions_race(self):
        with redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit):
            cli.main(['self-update', '--help'])
        self.assertIn('machine-wide-lock', out.getvalue())


class ProcessTest(unittest.TestCase):
    def test_go_command_shapes_and_unrelated_arguments(self):
        for command in ('/bin/gs go feature', '/bin/python /bin/gs --repo /tmp go f',
                        '/bin/python3.12 -m gs.cli --repo=/tmp go f',
                        '/Library/Frameworks/Python.framework/Resources/Python.app/Contents/MacOS/Python /bin/gs go f',
                        '/Library/Frameworks/Python.framework/Resources/Python.app/Contents/MacOS/Python -m gs.cli go f'):
            self.assertTrue(selfupdate._is_go(command), command)
        for command in ('bash -c "gs go f"', 'gs self-update', 'gs --repo go doctor',
                        'python worker.py gs go', 'Python worker.py gs go',
                        'gs --version', 'ps -axo pid=,args='):
            self.assertFalse(selfupdate._is_go(command), command)

    def test_framework_python_go_refuses_before_any_installation(self):
        pid = os.getpid() + 1
        command = '/opt/homebrew/Frameworks/Python.framework/Resources/Python.app/Contents/MacOS/Python /bin/gs go f'
        cp = subprocess.CompletedProcess([], 0, f'{pid} {command}\n', '')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch('gs.selfupdate.subprocess.run', return_value=cp) as run, \
                mock.patch('gs.selfupdate.version.installation') as installation:
            code = selfupdate.self_update(Path.cwd(), None, 'main', out, err)
        self.assertEqual(code, 1)
        self.assertIn(f'PID {pid}', err.getvalue())
        installation.assert_not_called()
        run.assert_called_once_with(['ps', '-axo', 'pid=,args='], capture_output=True,
                                    text=True, timeout=10, stdin=subprocess.DEVNULL)

    def test_ps_excludes_self_and_checks_other_machine_repos(self):
        cp = subprocess.CompletedProcess([], 0, f'{os.getpid()} gs go own\n42 /bin/gs --repo /other go f\n43 gs status\n', '')
        with mock.patch('gs.selfupdate.subprocess.run', return_value=cp) as run:
            self.assertEqual(selfupdate.running_go(), [42])
        self.assertEqual(run.call_args.args[0], ['ps', '-axo', 'pid=,args='])

    def test_ps_failure_is_not_an_empty_process_list(self):
        cp = subprocess.CompletedProcess([], 1, '', 'denied')
        with mock.patch('gs.selfupdate.subprocess.run', return_value=cp), self.assertRaises(OSError):
            selfupdate.running_go()
