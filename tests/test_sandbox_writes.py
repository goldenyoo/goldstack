"""레포 밖 쓰기 선언이 worker 환경·hook·codex에 전달되고 git 보호는 유지되는가."""
import contextlib
import io
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, cli, config, hook, hook_agy, worker
from gs.feature import Ticket
from support import isolate_git_env, sh


class SandboxWritesTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        sh(self.repo, 'git', 'init', '-q', '-b', 'main')
        sh(self.repo, 'git', '-c', 'user.name=t', '-c', 'user.email=t@t',
           'commit', '-qm', 'init', '--allow-empty')
        self.wt = self.repo / '.goldstack/work/demo/run/wt/01'
        sh(self.repo, 'git', 'worktree', 'add', '-qb', 'gs/demo/01', str(self.wt))
        self.shared = self.root / 'shared data'
        self.shared.mkdir()
        self.missing = self.root / 'missing'
        self.run = self.root / 'run'
        self.run.mkdir()
        self.inp = adapters.WorkerInput(self.run / 'brief.md', self.wt, self.run / 'worker.log')
        self.models = config.ModelsConfig('judge', 'review', 'agy', 'codex')
        self.write_config([str(self.shared)])

    def write_config(self, writes=None):
        text = config.DEFAULT_CONFIG.format(base='"main"')
        if writes is not None:
            text += '\n[sandbox]\nwrites = ' + json.dumps(writes) + '\n'
        (self.repo / config.CONFIG_PATH).write_text(text)

    def adapter(self, family, mode='os'):
        return adapters.for_model(family, self.models, sandbox=adapters.Sandbox(mode))

    def verdict(self, family, env, tool, **args):
        if family == 'agy':
            name = {'Write': 'write_to_file', 'Edit': 'replace_file_content', 'Bash': 'run_command'}[tool]
            args = {'CommandLine': args['command']} if tool == 'Bash' else {'TargetFile': args['file_path']}
            return hook_agy.decide({'workspacePaths': [str(self.wt)],
                                   'toolCall': {'name': name, 'args': args}}, env)
        return hook.decide({'cwd': str(self.wt), 'tool_name': tool, 'tool_input': args}, env)

    def test_worker_hooks_use_config_roots_and_snapshot(self):
        for family in ('claude', 'agy'):
            with self.subTest(family=family):
                self.write_config([str(self.shared), str(self.missing)])
                adapter = self.adapter(family)
                env = adapter.env(self.inp)
                self.assertEqual(json.loads(env[config.SANDBOX_WRITES_ENV]),
                                 [str(self.shared), str(self.missing)])
                # worker가 worktree의 config를 고쳐도 이미 전달한 판정은 그대로다.
                path = self.wt / config.CONFIG_PATH
                path.parent.mkdir(exist_ok=True)
                path.write_text('[sandbox]\nwrites = ["/untrusted"]\n')
                self.write_config()
                self.assertEqual(adapter.env(self.inp)[config.SANDBOX_WRITES_ENV], env[config.SANDBOX_WRITES_ENV])
                for tool in ('Write', 'Edit'):
                    self.assertIsNone(self.verdict(family, env, tool, file_path=str(self.shared / 'y')))
                for command in (f'cp x {shlex.quote(str(self.shared / "y"))}',
                                f'echo x > {shlex.quote(str(self.shared / "y"))}',
                                f'mkdir {shlex.quote(str(self.shared / "sub"))}'):
                    self.assertIsNone(self.verdict(family, env, 'Bash', command=command))
                self.assertIsNone(self.verdict(family, env, 'Write', file_path=str(self.missing / 'y')))
                self.assertIsNotNone(self.verdict(family, env, 'Write', file_path=str(self.root / 'other')))
                empty = self.adapter(family).env(self.inp)
                for tool, args in [('Write', {'file_path': str(self.shared / 'y')}),
                                   ('Bash', {'command': f'cp x {shlex.quote(str(self.shared / "y"))}'})]:
                    self.assertIn('[sandbox] writes', self.verdict(family, empty, tool, **args))
                self.assertIsNotNone(self.verdict(family, env, 'Write', file_path='/untrusted/y'))

    def test_config_root_keeps_secrets_and_git_protected(self):
        sh(self.shared, 'git', 'init', '-q')
        for family in ('claude', 'agy'):
            env = self.adapter(family).env(self.inp)
            for command in ('git remote add other /repo', 'git config user.name x', 'git stash clear'):
                reason = self.verdict(family, env, 'Bash',
                                      command=f'cd {shlex.quote(str(self.shared))} && {command}')
                self.assertIsNotNone(reason, (family, command))
            self.assertIn('비밀 파일', self.verdict(family, env, 'Edit', file_path=str(self.shared / '.env')))
            self.assertIn('비밀 파일', self.verdict(family, env, 'Bash',
                                                  command=f'cd {shlex.quote(str(self.shared))} && cat .env'))
        ctx = hook.Ctx(worktree=str(self.wt), cwd=str(self.wt), env=env)
        self.assertNotIn(str(self.shared), hook.temporary_outside(ctx))

    def test_codex_existing_dirs_in_os_and_landlock(self):
        file = self.root / 'plain-file'
        file.touch()
        self.write_config([str(self.shared), str(self.missing), str(file)])
        for mode, flag in [('os', '--add-dir'), ('landlock', '--write')]:
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex-home')}):
                adapter = self.adapter('codex', mode)
                adapter.prepare(self.inp)
                self.write_config()  # prepare에서 고정한 목록을 command도 쓴다.
                argv = shlex.split(adapter.command(self.inp))
                paths = [argv[i + 1] for i, arg in enumerate(argv) if arg == flag]
                self.assertIn(str(self.shared), paths)
                self.assertNotIn(str(self.missing), paths)
                self.assertNotIn(str(file), paths)
                self.assertFalse(self.missing.exists())
            self.write_config([str(self.shared), str(self.missing), str(file)])

    def test_script_exports_roots_and_clears_inherited_value(self):
        ticket = Ticket('01', 'writes', [], 'claude', 'codex', self.repo / 'ticket.md')
        job = worker.Job(ticket, self.wt, self.run)
        for family in ('claude', 'agy', 'codex'):
            adapter = self.adapter(family)
            with mock.patch.object(adapter, 'command', return_value='true'):
                worker.write_script(job, adapter)
            line = next(line for line in job.script.read_text().splitlines()
                        if line.startswith('export ' + config.SANDBOX_WRITES_ENV + '='))
            value = shlex.split(line)[1].split('=', 1)[1]
            self.assertEqual(json.loads(value), [str(self.shared)])
        class Bare(adapters.Adapter):
            def env(self, inp):
                return {}
            def command(self, inp):
                return 'true'
        worker.write_script(job, Bare(self.models))
        self.assertIn("export GS_SANDBOX_WRITES=''", job.script.read_text())

    def test_search_message_suggests_narrow_path_and_command_v(self):
        (self.wt / '.env').touch()
        env = self.adapter('claude').env(self.inp)
        for tool, args in [('Bash', {'command': 'find . -name python'}), ('Glob', {'pattern': '**/python'})]:
            reason = hook.decide({'cwd': str(self.wt), 'tool_name': tool, 'tool_input': args}, env)
            self.assertIn('검색 시작점', reason)
            self.assertIn('command -v', reason)
            self.assertIn('비밀 파일을 품지 않는 좁은 경로', reason)

    def test_config_rejects_symlink_into_main_repo(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.repo, target_is_directory=True)
        self.write_config([str(alias / '.git')])
        cfg, problems = config.load(self.repo)
        self.assertIsNone(cfg)
        self.assertTrue(any(p.level == '오류' and '주 레포와 겹친다' in p.message for p in problems))

    def test_expanded_home_and_invalid_config_at_launch(self):
        with mock.patch.dict(os.environ, {'HOME': str(self.root)}):
            self.write_config(['~/shared data', '~/missing'])
            env = self.adapter('claude').env(self.inp)
            self.assertEqual(json.loads(env[config.SANDBOX_WRITES_ENV]),
                             [str(self.shared), str(self.missing)])
        self.write_config(['relative'])
        with self.assertRaisesRegex(adapters.AdapterError, 'sandbox.writes'):
            self.adapter('claude').env(self.inp)
        for command in ('check', 'go'):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(['--repo', str(self.repo), command, 'demo'])
            self.assertNotEqual(code, 0)
            self.assertIn('sandbox.writes', out.getvalue() + err.getvalue())

    def test_bad_env_does_not_grant_outside_writes(self):
        env = self.adapter('claude').env(self.inp)
        for value in ('{', '{}', '[null, 1, "relative"]'):
            with self.subTest(value=value):
                env[config.SANDBOX_WRITES_ENV] = value
                self.assertIsNotNone(self.verdict('claude', env, 'Write', file_path=str(self.shared / 'y')))
