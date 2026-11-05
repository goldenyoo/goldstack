"""가짜 herdr의 pane에서 실제 검사 스크립트를 돌린다. 원격 머신에는 접속하지 않는다."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import isolate_git_env
from gs import cli, remote, version

HERDR = r'''
import json, os, re, subprocess, sys
from pathlib import Path
a = sys.argv[1:]
root = Path(os.environ['FAKE_ROOT'])
with (root / 'calls').open('a') as f:
    f.write(json.dumps(a) + '\n')
if a == ['machine', 'status']:
    print('id\trunner\t' + os.environ.get('CONNECTION', 'reachable'))
    print('other-id\tbroken\terror')
    sys.exit(1)
assert a[:2] == ['--machine', 'runner'], a
a = a[2:]
if a[:2] == ['workspace', 'create']:
    print(json.dumps({'result': {'root_pane': {'pane_id': 'remote:p1'}}}))
elif a[:2] == ['pane', 'run']:
    cp = subprocess.run(' '.join(a[3:]), shell=True, text=True, capture_output=True)
    # 터미널 입력 에코와 완료 뒤 프롬프트도 섞는다.
    (root / 'output').write_text('echo ' + ' '.join(a[3:]) + '\n' + cp.stdout + '\nshell$ unrelated\n')
elif a[:2] == ['pane', 'wait-output']:
    if os.environ.get('WAIT_FAIL'):
        print(json.dumps({'error': {'code': 'timeout', 'message': 'wait timed out'}}), file=sys.stderr)
        sys.exit(1)
    assert re.search(a[a.index('--regex') + 1], (root / 'output').read_text())
elif a[:2] == ['pane', 'read']:
    print('incomplete output' if os.environ.get('BAD_OUTPUT') else (root / 'output').read_text())
elif a[:2] == ['pane', 'close']:
    pass
else:
    raise AssertionError(a)
'''

CLI = r'''
import json, os, sys
name = os.path.basename(sys.argv[0])
a = sys.argv[1:]
missing = os.environ.get('MISSING', '')
if a == ['--version']:
    print(name + ' ' + os.environ.get('REMOTE_VERSION', '0.1.0'))
    sys.exit(1 if missing == name else 0)
if a == ['plugin', 'list', '--json']:
    print(json.dumps([] if missing == 'plugin' else [{'id': 'goldstack@goldstack',
          'version': os.environ.get('PLUGIN_VERSION', '0.1.0'), 'enabled': missing != 'disabled'}]))
    sys.exit(0)
if 'status' in a:
    if missing == 'claude_logged_out' and name == 'claude':
        print(json.dumps({'loggedIn': False}))
        sys.exit(0)
    print('SECRET_AUTH_OUTPUT')
    sys.exit(1 if missing == name + '_auth' else 0)
sys.exit(1)
'''


class RemoteTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / 'local'
        self.target = self.root / "remote repo 'quoted'"
        self.bin = self.root / 'bin'
        for p in (self.repo, self.target, self.bin):
            p.mkdir()
        for p in (self.repo, self.target):
            self.git(p, 'init', '-q')
            self.git(p, 'config', 'user.email', 'test@example.com')
            self.git(p, 'config', 'user.name', '시험')
        (self.repo / '.goldstack/work/demo').mkdir(parents=True)
        (self.repo / '.goldstack/work/demo/spec.md').write_text('spec')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-qm', 'grill: demo')
        self.git(self.repo, 'checkout', '-qb', 'gs/demo/01')
        self.git(self.target, 'remote', 'add', 'origin', str(self.repo))
        (self.target / '.goldstack').mkdir()
        (self.target / '.goldstack/local.env').write_text('TOKEN=SECRET_ENV_VALUE')
        (self.repo / '.goldstack/local.env').write_text(f'GS_REMOTE_REPO_runner={self.target}\n')
        for name, script in [('herdr', HERDR)] + [(n, CLI) for n in ('gs', 'gh', 'claude', 'codex', 'agy')]:
            p = self.bin / name
            p.write_text(f'#!{sys.executable}\n' + script)
            p.chmod(0o755)
        patch = mock.patch.dict(os.environ, {
            'HERDR_BIN_PATH': str(self.bin / 'herdr'), 'FAKE_ROOT': str(self.root),
            'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
        })
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch('gs.remote.version.installation', return_value=version.Installation('0.1.0', plugin_version='0.1.0'))
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch('gs.remote._local_cli', side_effect=lambda repo, name: name + ' 0.1.0')
        patch.start()
        self.addCleanup(patch.stop)
        self.out, self.err = io.StringIO(), io.StringIO()

    def git(self, repo, *args):
        return subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()

    def check(self, machine='runner'):
        code = remote.check(self.repo, machine, self.out, self.err)
        output = self.out.getvalue() + self.err.getvalue()
        self.assertNotIn('SECRET_AUTH_OUTPUT', output)
        self.assertNotIn('SECRET_ENV_VALUE', output)
        return code, output

    def test_all_pass_even_when_other_machine_fails(self):
        code, output = self.check()
        self.assertEqual(code, 0, output)
        self.assertNotIn('빠짐', output)
        self.assertNotIn('경고', output)
        self.assertEqual(output.count('통과:'), 11)
        calls = [json.loads(line) for line in (self.root / 'calls').read_text().splitlines()]
        self.assertTrue(all(a[:2] == ['--machine', 'runner'] for a in calls[1:]))
        self.assertEqual([a[2:4] for a in calls[1:]], [['workspace', 'create'], ['pane', 'run'],
                         ['pane', 'wait-output'], ['pane', 'read'], ['pane', 'close']])

    def test_each_missing_tool_or_auth(self):
        for missing, label in [('gs', 'gs'), ('plugin', 'goldstack 플러그인'), ('disabled', 'goldstack 플러그인'),
                               ('gh_auth', 'gh 인증'), ('claude_auth', 'claude 인증'), ('claude_logged_out', 'claude 인증'),
                               ('codex_auth', 'codex 인증')]:
            with self.subTest(missing=missing), mock.patch.dict(os.environ, MISSING=missing):
                self.out.seek(0)
                self.out.truncate()
                code, output = self.check()
                self.assertEqual(code, 1, output)
                self.assertIn('빠짐: ' + label, output)

    def test_disk_env_repo_and_grill_missing(self):
        cases = [('disk', mock.patch('gs.remote.MIN_FREE', 10**30), '디스크 여유'),
                 ('grill', mock.patch('gs.remote.grill_commit', return_value='f' * 40), 'grill 커밋 수신')]
        for _, patch, label in cases:
            with self.subTest(label=label), patch:
                code, output = self.check()
                self.assertEqual(code, 1)
                self.assertIn('빠짐: ' + label, output)
        (self.target / '.goldstack/local.env').unlink()
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('빠짐: .goldstack/local.env', output)
        (self.target / '.git').rename(self.target / 'not-git')
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('빠짐: 레포 경로', output)

    def test_missing_path_key_and_unregistered_or_disconnected(self):
        (self.repo / '.goldstack/local.env').unlink()
        code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('GS_REMOTE_REPO_runner=', output)
        code, output = self.check('unknown')
        self.assertEqual(code, 1)
        self.assertIn(remote.GUIDE, output)
        with mock.patch.dict(os.environ, CONNECTION='error'):
            code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('빠짐: 연결', output)

    def test_no_herdr(self):
        with mock.patch.dict(os.environ, HERDR_BIN_PATH='/missing/herdr'):
            code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn(remote.GUIDE, output)

    def test_gs_and_plugin_version_mismatch_block(self):
        for variable, label in [('REMOTE_VERSION', 'gs'), ('PLUGIN_VERSION', 'goldstack 플러그인')]:
            with self.subTest(variable=variable), mock.patch.dict(os.environ, {variable: '9.0'}):
                code, output = self.check()
                self.assertEqual(code, 1)
                self.assertIn('빠짐: ' + label, output)
                self.assertIn('gs self-update', output)

    def test_cli_version_difference_only_warns(self):
        with mock.patch('gs.remote._local_cli', return_value='cli 9.0'):
            code, output = self.check()
        self.assertEqual(code, 0)
        for name in ('claude', 'codex', 'agy'):
            self.assertIn('경고: ' + name + ' 버전', output)

    def test_timeout_and_wait_failure_close_pane(self):
        with mock.patch.dict(os.environ, WAIT_FAIL='1'):
            code, output = self.check()
            self.assertEqual(code, 1)
            self.assertIn('시간 초과', output)
        self.assertIn('pane", "close', (self.root / 'calls').read_text())
        with mock.patch('gs.remote.probe', side_effect=subprocess.TimeoutExpired('herdr', 90)):
            code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('시간 초과', output)

    def test_incomplete_output_fails_and_closes_pane(self):
        with mock.patch.dict(os.environ, BAD_OUTPUT='1'):
            code, output = self.check()
        self.assertEqual(code, 1)
        self.assertIn('빠짐: 원격 검사', output)
        self.assertIn('pane", "close', (self.root / 'calls').read_text())

    def test_grill_commit_uses_current_feature(self):
        expected = remote.grill_commit(self.repo)
        path = self.repo / '.goldstack/work/another'
        path.mkdir()
        (path / 'spec.md').write_text('other feature')
        self.git(self.repo, 'add', str(path))
        self.git(self.repo, 'commit', '-qm', 'grill: another')
        self.assertEqual(remote.grill_commit(self.repo), expected)

    def test_cli_dispatch(self):
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            self.assertEqual(cli.main(['--repo', str(self.repo), 'remote', 'check', 'runner']), 0)


if __name__ == '__main__':
    unittest.main()
