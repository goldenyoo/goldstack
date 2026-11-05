"""가짜 herdr의 pane에서 실제 검사 스크립트를 돌린다. 원격 머신에는 접속하지 않는다."""
from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from support import isolate_git_env
from gs import cli, config, remote, state, version

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
def refuse(code):
    # 메시지는 원격에서 온 글이다. gs가 그대로 내보내면 시험이 잡는다.
    print(json.dumps({'error': {'code': code, 'message': 'SECRET_HERDR_DETAIL'}}), file=sys.stderr)
    sys.exit(1)
if a[:2] == ['workspace', 'create']:
    if '--cwd' in a and os.environ.get('SESSION_CREATE_FAIL'):
        refuse('workspace_create_failed')
    (root / 'shell').write_text('')
    print(json.dumps({'result': {'workspace': {'workspace_id': 'remote:w1'}, 'root_pane': {'pane_id': 'remote:p1'}}}))
elif a[:2] == ['agent', 'start']:
    # 실제 herdr처럼 셸이 명령을 받는 pane에만 띄운다.
    assert 'GS_REMOTE_READY_' in (root / 'output').read_text(), a
    if os.environ.get('AGENT_FAIL') == 'start':
        refuse('agent_not_ready')
elif a[:2] == ['agent', 'prompt']:
    if os.environ.get('AGENT_FAIL') == 'prompt':
        refuse('agent_blocked')
elif a[:2] == ['workspace', 'close']:
    if os.environ.get('CLOSE_FAIL'):
        refuse('close_failed')
elif a[:2] == ['pane', 'run']:
    command = ' '.join(a[3:])
    # 새 pane에 아직 프롬프트가 없어 canonical 모드인 macOS를 재현한다.
    if len(command.encode()) >= 1024:
        print('command exceeds canonical line-input limit', file=sys.stderr)
        sys.exit(1)
    # pane의 셸 변수는 다음 pane run에서도 유지된다.
    history = root / 'shell'
    previous = history.read_text()
    cp = subprocess.run(previous + command, shell=True, text=True, capture_output=True)
    if command.startswith('GS_CHECK_'):
        history.write_text(previous + command.split(';', 1)[0] + '\n')
    # 터미널 입력 에코와 완료 뒤 프롬프트도 섞는다.
    (root / 'output').write_text('echo ' + ' '.join(a[3:]) + '\n' + cp.stdout + '\nshell$ unrelated\n')
elif a[:2] == ['pane', 'wait-output']:
    failure = os.environ.get('WAIT_FAIL')
    pattern = a[a.index('--regex') + 1]
    if failure == '1' or (failure == 'final' and 'GS_CHECK_END_' in pattern) or (failure == 'ready' and 'GS_REMOTE_READY_' in pattern):
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
if name == 'gs' and a[-2:-1] == ['status']:
    print('REMOTE_STATUS_TABLE ' + ' '.join(a))
    sys.exit(int(os.environ.get('STATUS_CODE', '0')))
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


class RemoteFixture(unittest.TestCase):
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
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
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


class RemoteTest(RemoteFixture):
    def test_all_pass_even_when_other_machine_fails(self):
        code, output = self.check()
        self.assertEqual(code, 0, output)
        self.assertNotIn('빠짐', output)
        self.assertNotIn('경고', output)
        self.assertEqual(output.count('통과:'), 11)
        calls = [json.loads(line) for line in (self.root / 'calls').read_text().splitlines()]
        self.assertTrue(all(a[:2] == ['--machine', 'runner'] for a in calls[1:]))
        actions = [a[2:4] for a in calls[1:]]
        self.assertEqual(actions[0], ['workspace', 'create'])
        self.assertEqual(actions[-2:], [['pane', 'read'], ['pane', 'close']])
        self.assertEqual(actions[1:-2], [['pane', 'run'], ['pane', 'wait-output']] * ((len(actions) - 3) // 2))
        commands = [a[5] for a in calls if a[2:4] == ['pane', 'run']]
        self.assertGreater(len(commands), 1)
        self.assertTrue(all(len(command.encode()) < 1024 for command in commands))

    def test_long_arguments_stay_below_canonical_limit(self):
        # 경로·원격 이름은 압축 전송하여 마지막 실행 명령도 짧게 유지한다.
        data = remote.probe('runner', str(self.target) + '/x' * 300,
                            remote.grill_commit(self.repo), git_remote='upstream' * 300)
        self.assertIs(data['repo'], False)

    def test_grill_fetch_uses_configured_remote(self):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('remote = "origin"', 'remote = "upstream"'))
        self.git(self.target, 'remote', 'rename', 'origin', 'upstream')
        # 커밋이 없는 원격 레포에서 upstream으로 dry-run fetch해야 한다.
        self.assertNotEqual(subprocess.run(['git', 'cat-file', '-e', remote.grill_commit(self.repo)],
                                          cwd=self.target, capture_output=True).returncode, 0)
        code, output = self.check()
        self.assertEqual(code, 0, output)
        # dry-run도 받은 객체를 저장할 수 있으므로 실패 검사에는 새 커밋을 쓴다.
        (self.repo / '.goldstack/work/demo/spec.md').write_text('updated spec')
        self.git(self.repo, 'commit', '-qam', 'grill: demo update')
        self.git(self.target, 'remote', 'remove', 'upstream')
        self.out.seek(0)
        self.out.truncate()
        code, output = self.check()
        self.assertEqual(code, 1, output)
        self.assertIn('빠짐: grill 커밋 수신', output)
        self.assertIn('원격 레포의 upstream과 git 인증', output)

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
        for stage in ('1', 'final'):
            with self.subTest(stage=stage), mock.patch.dict(os.environ, WAIT_FAIL=stage):
                self.out.seek(0)
                self.out.truncate()
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
        # gs remote go는 현재 브랜치와 상관없이 지정한 feature의 커밋을 본다.
        self.assertEqual(remote.grill_commit(self.repo, 'demo'), expected)
        self.assertEqual(remote.grill_commit(self.repo, 'another'), self.git(self.repo, 'rev-parse', 'HEAD'))
        self.assertEqual(remote.grill_commit(self.repo, 'absent'), '')

    def test_cli_dispatch(self):
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            self.assertEqual(cli.main(['--repo', str(self.repo), 'remote', 'check', 'runner']), 0)


class RemoteGoFixture(RemoteFixture):
    """로컬·원격 레포가 같은 bare origin을 본다. 원격은 base에 있고 grill 커밋까지 받았다."""

    def setUp(self):
        super().setUp()
        self.origin = self.root / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(self.origin)], check=True)
        self.git(self.repo, 'remote', 'add', 'origin', str(self.origin))
        self.git(self.repo, 'push', '-q', 'origin', 'HEAD:refs/heads/main')
        self.git(self.target, 'remote', 'set-url', 'origin', str(self.origin))
        self.git(self.target, 'fetch', '-q', 'origin')
        self.git(self.target, 'checkout', '-q', '-B', 'main', 'origin/main')
        with (self.repo / '.goldstack/local.env').open('a') as f:
            f.write('TG_TOKEN=SECRET_LOCAL_TOKEN\n')

    def commit_spec(self, text='updated spec'):
        (self.repo / '.goldstack/work/demo/spec.md').write_text(text)
        self.git(self.repo, 'commit', '-qam', 'grill: demo update')

    def push_spec(self, text='updated spec'):
        """로컬 grill 커밋을 origin base에 올린다. 원격 레포는 그만큼 뒤처진다."""
        self.commit_spec(text)
        self.git(self.repo, 'push', '-q', 'origin', 'HEAD:refs/heads/main')

    def calls(self):
        path = self.root / 'calls'
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def actions(self):
        return [a[2:4] for a in self.calls() if a[0] == '--machine']

    def payloads(self):
        """pane으로 보낸 압축 스크립트와 인자를 풀어 돌려준다."""
        chunks = {}
        for a in self.calls():
            if a[2:4] == ['pane', 'run']:
                found = re.match(r"""(GS_CHECK_[0-9a-f]+)=(?:"\$\1")?'?([A-Za-z0-9+/=]+)'?;""", a[5])
                if found:
                    chunks.setdefault(found[1], []).append(found[2])
        return [zlib.decompress(base64.b64decode(''.join(parts))).decode() for parts in chunks.values()]

    def assert_no_secret(self, output):
        sent = json.dumps(self.calls()) + '\n'.join(self.payloads())
        for secret in ('SECRET_LOCAL_TOKEN', 'SECRET_ENV_VALUE', 'SECRET_AUTH_OUTPUT', 'SECRET_HERDR_DETAIL', 'SECRET_URL_TOKEN'):
            self.assertNotIn(secret, output)
        for secret in ('SECRET_LOCAL_TOKEN', 'SECRET_ENV_VALUE', 'TG_TOKEN'):
            self.assertNotIn(secret, sent)
        self.assertFalse([a for a in self.calls() if '--env' in a])

    def assert_no_session(self):
        self.assertFalse([a for a in self.calls() if a[2:4] == ['workspace', 'create'] and '--cwd' in a])
        self.assertFalse([a for a in self.actions() if a[0] == 'agent'])

    def go(self, feature='demo', machine='runner'):
        self.out, self.err = io.StringIO(), io.StringIO()
        code = remote.go(self.repo, machine, feature, self.out, self.err)
        output = self.out.getvalue() + self.err.getvalue()
        self.assert_no_secret(output)
        return code, output

    def status(self, feature='demo', machine='runner'):
        self.out, self.err = io.StringIO(), io.StringIO()
        code = remote.status(self.repo, machine, feature, self.out, self.err)
        return code, self.out.getvalue(), self.err.getvalue()

    def target_head(self):
        return self.git(self.target, 'rev-parse', 'HEAD')


class RemoteGoTest(RemoteGoFixture):
    def test_success_pulls_starts_claude_and_returns(self):
        self.push_spec()
        before = self.target_head()
        code, output = self.go()
        self.assertEqual(code, 0, output)
        # 원격 레포가 실제로 fast-forward됐다.
        self.assertNotEqual(self.target_head(), before)
        self.assertEqual(self.target_head(), self.git(self.repo, 'rev-parse', 'HEAD'))
        calls = self.calls()
        created = next(i for i, a in enumerate(calls) if a[2:4] == ['workspace', 'create'] and '--cwd' in a)
        cwd = calls[created][calls[created].index('--cwd') + 1]
        self.assertEqual(cwd, str(self.target.resolve()))
        self.assertIn('--no-focus', calls[created])
        self.assertEqual([a[2:4] for a in calls[created + 1:]],
                         [['pane', 'run'], ['pane', 'wait-output'], ['agent', 'start'], ['agent', 'prompt']])
        start, prompt = calls[-2:]
        self.assertEqual(start[start.index('--kind') + 1], 'claude')
        self.assertEqual(start[start.index('--pane') + 1], 'remote:p1')
        self.assertRegex(start[4], r'^[a-z][a-z0-9_-]{0,31}$')  # herdr의 agent 이름 규칙
        # --wait 없이 보내고 바로 돌아온다.
        self.assertEqual(prompt[4:], ['remote:p1', '/go demo'])
        # 세션 pane은 닫지 않는다. 앞선 임시 pane만 닫았다.
        self.assertEqual(self.actions().count(['pane', 'close']), 2)
        self.assertNotIn(['workspace', 'close'], self.actions())
        self.assertIn('workspace: remote:w1', output)
        self.assertIn('pane: remote:p1', output)
        self.assertIn('gs remote status runner demo', output)
        self.assertIn('herdr --machine runner pane read remote:p1', output)
        self.assertTrue(any('pull' in payload for payload in self.payloads()))

    def test_check_failure_starts_nothing(self):
        self.push_spec()
        before = self.target_head()
        with mock.patch.dict(os.environ, MISSING='gh_auth'):
            code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('빠짐: gh 인증', output)
        self.assertIn('세션을 띄우지 않았다', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_unpushed_commit_fails_grill_check(self):
        self.commit_spec()
        before = self.target_head()
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('빠짐: grill 커밋 수신', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_commit_on_other_branch_is_not_pushed_to_base(self):
        # 검사는 원격이 커밋을 받을 수 있는지만 본다. base에 없으면 여기서 막힌다.
        self.commit_spec()
        self.git(self.repo, 'push', '-q', 'origin', 'HEAD:refs/heads/other')
        before = self.target_head()
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertNotIn('빠짐', output)
        self.assertIn('origin/main와 다르다', output)
        self.assertIn('push', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_uncommitted_spec_or_tickets_are_rejected(self):
        before = self.target_head()
        tickets = self.repo / '.goldstack/work/demo/tickets'
        tickets.mkdir()
        (tickets / '01-a.md').write_text('new ticket')
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('origin/main와 다르다', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_base_fetch_failure_is_rejected(self):
        self.git(self.repo, 'remote', 'set-url', 'origin', str(self.root / 'SECRET_URL_TOKEN'))
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('origin/main를 받지 못했다', output)
        self.assert_no_session()

    def test_already_running_starts_nothing_and_does_not_pull(self):
        self.push_spec()
        before = self.target_head()
        with state.Lock(self.target / '.goldstack/work/demo/run'):
            code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn(f'이미 돌고 있다(pid {os.getpid()})', output)
        self.assertIn('gs remote status runner demo', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)
        # 잠금이 풀리면 lock 파일이 남아 있어도 돌지 않는 것이다.
        code, output = self.go()
        self.assertEqual(code, 0, output)
        self.assertNotEqual(self.target_head(), before)

    def test_session_create_failure(self):
        with mock.patch.dict(os.environ, SESSION_CREATE_FAIL='1'):
            code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('원격 세션을 띄우지 못했다(workspace_create_failed)', output)
        self.assertIn('workspace list', output)
        self.assertFalse([a for a in self.actions() if a[0] == 'agent'])

    def test_malformed_create_response(self):
        for result in ({'workspace': {'workspace_id': 'w'}}, {'root_pane': {'pane_id': 'p'}}, {'workspace': 'w', 'root_pane': {'pane_id': 'p'}}):
            with self.subTest(result=result), mock.patch('gs.remote.herdr.machine_call', return_value=result), \
                    mock.patch('gs.remote.herdr.machine_run') as run:
                with self.assertRaises(remote.herdr.HerdrError):
                    remote.launch('runner', '/repo', 'demo')
                run.assert_not_called()

    def test_failure_after_create_closes_workspace(self):
        cases = [('AGENT_FAIL', 'start', 'agent_not_ready', ['agent', 'start']),
                 ('AGENT_FAIL', 'prompt', 'agent_blocked', ['agent', 'prompt']),
                 ('WAIT_FAIL', 'ready', '시간 초과', ['pane', 'wait-output'])]
        for variable, value, reason, last in cases:
            with self.subTest(value=value), mock.patch.dict(os.environ, {variable: value}):
                (self.root / 'calls').unlink(missing_ok=True)
                code, output = self.go()
                self.assertEqual(code, 1, output)
                self.assertIn(reason, output)
                calls = self.calls()
                self.assertEqual(calls[-1][2:], ['workspace', 'close', 'remote:w1'])
                self.assertEqual(calls[-2][2:4], last)

    def test_agent_not_ready_tells_how_to_fix(self):
        with mock.patch.dict(os.environ, AGENT_FAIL='start'):
            code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('폴더 신뢰', output)

    def test_close_failure_reports_leftover_workspace(self):
        with mock.patch.dict(os.environ, AGENT_FAIL='prompt', CLOSE_FAIL='1'):
            code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('herdr --machine runner workspace close remote:w1', output)

    def test_pull_failure_hides_git_output(self):
        self.git(self.target, 'remote', 'set-url', 'origin', str(self.root / 'SECRET_URL_TOKEN'))
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('git pull --ff-only origin main 실패', output)
        self.assert_no_session()

    def test_diverged_remote_is_not_overwritten(self):
        self.push_spec()
        (self.target / 'local-only').write_text('x')
        self.git(self.target, 'add', 'local-only')
        self.git(self.target, 'commit', '-qm', 'remote only')
        before = self.target_head()
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('갈라짐', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_remote_on_other_branch_is_not_moved(self):
        self.push_spec()
        self.git(self.target, 'checkout', '-qb', 'elsewhere')
        before = self.target_head()
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('main 브랜치가 아니다', output)
        self.assert_no_session()
        self.assertEqual(self.target_head(), before)

    def test_remote_without_spec_starts_nothing(self):
        (self.target / '.goldstack/work/demo/spec.md').unlink()
        code, output = self.go()
        self.assertEqual(code, 1, output)
        self.assertIn('spec.md가 없다', output)
        self.assert_no_session()

    def test_configured_remote_and_base_are_used(self):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('remote = "origin"', 'remote = "upstream"').replace('base = "main"', 'base = "trunk"'))
        self.git(self.repo, 'remote', 'rename', 'origin', 'upstream')
        self.git(self.target, 'remote', 'rename', 'origin', 'upstream')
        self.git(self.repo, 'push', '-q', 'upstream', 'HEAD:refs/heads/trunk')
        self.git(self.target, 'fetch', '-q', 'upstream')
        self.git(self.target, 'checkout', '-q', '-b', 'trunk', 'upstream/trunk')
        self.commit_spec()
        self.git(self.repo, 'push', '-q', 'upstream', 'HEAD:refs/heads/trunk')
        code, output = self.go()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.target_head(), self.git(self.repo, 'rev-parse', 'HEAD'))
        self.assertEqual(self.git(self.origin, 'rev-parse', 'refs/heads/main'),
                         self.git(self.repo, 'rev-parse', 'HEAD~1'))

    def test_bad_feature_name_reaches_nothing(self):
        for feature in ('a b', '../x', '-x', '.hidden', 'x;touch y', 'a\nb', '/go', ''):
            with self.subTest(feature=feature):
                code, output = self.go(feature)
                self.assertEqual(code, 1, output)
                self.assertEqual(self.calls(), [])
                code, _, err = self.status(feature)
                self.assertEqual(code, 1, err)
                self.assertEqual(self.calls(), [])

    def test_unknown_feature_reaches_nothing(self):
        code, output = self.go('absent')
        self.assertEqual(code, 1, output)
        self.assertIn('/grill absent', output)
        self.assertEqual(self.calls(), [])

    def test_cli_dispatch(self):
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            self.assertEqual(cli.main(['--repo', str(self.repo), 'remote', 'go', 'runner', 'demo']), 0)
            self.assertEqual(cli.main(['--repo', str(self.repo), 'remote', 'status', 'runner', 'demo']), 0)
        self.assertIn('/go demo', json.dumps(self.calls()))
        self.assertIn('REMOTE_STATUS_TABLE', self.out.getvalue())


class RemoteStatusTest(RemoteGoFixture):
    def test_shows_remote_status(self):
        code, out, err = self.status()
        self.assertEqual(code, 0, err)
        self.assertEqual(out.strip(), f'REMOTE_STATUS_TABLE --repo {self.target} status demo')
        self.assertNotIn(remote.EXIT_PREFIX, out)
        self.assertEqual(self.actions()[-1], ['pane', 'close'])
        self.assertFalse([a for a in self.actions() if a[0] == 'agent'])

    def test_remote_exit_code_is_returned(self):
        with mock.patch.dict(os.environ, STATUS_CODE='1'):
            code, out, err = self.status()
        self.assertEqual(code, 1, err)
        self.assertIn('REMOTE_STATUS_TABLE', out)

    def test_remote_without_gs(self):
        (self.bin / 'gs').unlink()
        (self.bin / 'python3').symlink_to(sys.executable)
        with mock.patch.dict(os.environ, PATH=str(self.bin)):
            code, out, err = self.status()
        self.assertEqual(code, 127, err)
        self.assertIn('gs를 실행하지 못했다', out)

    def test_missing_path_or_herdr(self):
        (self.repo / '.goldstack/local.env').unlink()
        code, _, err = self.status()
        self.assertEqual(code, 1)
        self.assertIn('GS_REMOTE_REPO_runner=', err)
        self.assertEqual(self.calls(), [])
        with mock.patch.dict(os.environ, HERDR_BIN_PATH='/missing/herdr'):
            code, _, err = self.status()
        self.assertEqual(code, 1)
        self.assertIn(remote.GUIDE, err)

    def test_failures_close_pane(self):
        for variable, value, reason in [('WAIT_FAIL', 'final', '시간 초과'), ('BAD_OUTPUT', '1', '요청 실패')]:
            with self.subTest(variable=variable), mock.patch.dict(os.environ, {variable: value}):
                code, _, err = self.status()
                self.assertEqual(code, 1)
                self.assertIn(reason, err)
                self.assertNotIn('SECRET_HERDR_DETAIL', err)
                self.assertEqual(self.actions()[-1], ['pane', 'close'])

    def test_output_without_exit_line_is_an_error(self):
        with mock.patch('gs.remote._script_in_pane', return_value='잘린 표'):
            code, _, err = self.status()
        self.assertEqual(code, 1)
        self.assertIn('잘렸다', err)


if __name__ == '__main__':
    unittest.main()
