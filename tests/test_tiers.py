"""등급표 파싱·worker 옵션·실패 승급과 네트워크 재시작의 실제 실행 경로."""
import contextlib
import io
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import adapters, check, cli, config, feature, go, state, transient
from test_config import CONFIG


class TiersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / '.goldstack').mkdir()
        self.path = self.repo / config.CONFIG_PATH
        self.default = config.DEFAULT_CONFIG.format(base='"main"')
        self.path.write_text(self.default)

    def load(self, text):
        self.path.write_text(text)
        return config.load(self.repo)

    def test_template_and_repo_tables_match_spec_and_defaults(self):
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        expected = {
            'claude': [('sonnet', 'medium'), ('sonnet', 'high'), ('opus', 'xhigh')],
            'codex': [('gpt-6-luna', 'medium'), ('gpt-6.1-sol', 'medium'), ('gpt-6.1-sol', 'high')],
            'agy': [('gemini-3.8-flash-medium', ''), ('gemini-4-argon-medium', ''), ('gemini-4-argon-high', '')],
        }
        actual_repo, problems = config.load(Path(__file__).resolve().parents[1])
        self.assertEqual(problems, [])
        for family, entries in expected.items():
            for tier, pair in zip(feature.TIERS, entries):
                self.assertEqual(cfg.tiers.worker(family, tier), (tier, config.ModelEffort(*pair)))
                if family == 'agy':  # 이 레포는 agy를 모든 티어에서 Argon High로 쓴다(기본값과 다르다).
                    self.assertEqual(actual_repo.tiers.worker(family, tier),
                                     (tier, config.ModelEffort('gemini-4-argon-high', '')))
                else:
                    self.assertEqual(cfg.tiers.worker(family, tier), actual_repo.tiers.worker(family, tier))
        cfg, problems = self.load(self.default.replace('review = "large"\nrereview = "medium"\n', ''))
        self.assertEqual(problems, [])
        self.assertEqual((cfg.tiers.review, cfg.tiers.rereview), ('large', 'medium'))
        cfg, problems = self.load(self.default.replace('review = "large"', 'review = "small"')
                                  .replace('rereview = "medium"', 'rereview = "large"'))
        self.assertEqual(problems, [])
        self.assertEqual((cfg.tiers.review, cfg.tiers.rereview), ('small', 'large'))

    def test_old_config_and_failure_summary_fallback(self):
        cfg, problems = self.load(CONFIG)
        self.assertEqual(problems, [])
        self.assertEqual(cfg.models.failure_summary, cfg.models.judge)
        for family in feature.FAMILIES:
            self.assertEqual(cfg.tiers.worker(family, 'small', failures=1), ('', None))
        cfg, problems = self.load(CONFIG.replace('[models]', '[models]\nfailure_summary = "small-judge"'))
        self.assertEqual(problems, [])
        self.assertEqual(cfg.models.failure_summary, 'small-judge')

    def test_invalid_nested_values_are_errors_without_losing_scalar_validation(self):
        cases = [('tiers = 3\n' + CONFIG, 'tiers'),
                 (CONFIG + '\n[tiers]\nclaude = "wrong"\n', 'tiers.claude'),
                 (CONFIG + '\n[tiers.claude]\nsmall = "sonnet/high"\n', 'tiers.claude.medium')]
        for bad in ('17', 'true', '[]', '""', '"sonnet/"', '"/high"', '"a/b/c"',
                    '"a b/high"', '"sonnet/unknown"', '"sonnet/minimal"'):
            cases.append((self.default.replace('small = "sonnet/medium"', 'small = ' + bad), 'tiers.claude.small'))
        for key in ('review', 'rereview'):
            for bad in ('"huge"', 'false', '[]'):
                cases.append((CONFIG + f'\n[tiers]\n{key} = {bad}\n', f'tiers.{key}'))
        for bad in ('""', '17'):
            cases.append((CONFIG.replace('[models]', f'[models]\nfailure_summary = {bad}'), 'models.failure_summary'))
        cases.append((self.default.replace('review_minutes = 30', 'review_minutes = true'), 'timeouts.review_minutes'))
        for text, key in cases:
            with self.subTest(key=key, text=text):
                cfg, problems = self.load(text)
                self.assertIsNone(cfg)
                self.assertTrue(any(p.level == '오류' and key in p.message for p in problems), problems)

    def test_ticket_tier_and_check_warning_for_legacy_config(self):
        root = self.repo / '.goldstack/work/demo'
        (root / 'tickets').mkdir(parents=True)
        (root / 'spec.md').write_text(support.SPEC)
        path = root / 'tickets/01-t.md'
        with mock.patch.object(check, 'environment_problems', return_value=[]):
            for tier in (None, 'small', 'medium', 'large', 'huge', '[]'):
                path.write_text(support.ticket('01').replace('reviewer: codex\n',
                                'reviewer: codex\n' + (f'tier: {tier}\n' if tier else '')))
                feat, _ = check.check(self.repo, 'demo')
                self.assertEqual(bool(feat.errors), tier in ('huge', '[]'), feat.problems)
                if not feat.errors:
                    self.assertEqual(feat.tickets['01'].tier, tier)
            path.write_text(support.ticket('01'))
            self.path.write_text(CONFIG.replace('telegram = true', 'telegram = false'))
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(['--repo', str(self.repo), 'check', 'demo'])
            self.assertEqual(code, 0, err.getvalue())
            self.assertIn('모델·effort가 사용자 설정을 따른다', err.getvalue())
            self.path.write_text(self.default.replace('medium = "sonnet/high"', 'medium = 3'))
            feat, _ = check.check(self.repo, 'demo')
            self.assertTrue(any('tiers.claude.medium' in p.message for p in feat.errors))

    def test_adapter_options_and_legacy_models(self):
        inp = adapters.WorkerInput(self.repo / 'brief file', self.repo, self.repo / 'log')
        models = config.ModelsConfig('judge', 'review', 'legacy-agy', 'legacy-codex')
        with mock.patch.dict(os.environ), \
                mock.patch.object(adapters.Claude, 'isolation', return_value=''), \
                mock.patch.object(adapters.Codex, 'writable_dirs', return_value=[]):
            os.environ.pop('GS_WORKER_CMD', None)
            cfg = config.load(self.repo)[0]
            for family in feature.FAMILIES:
                for effort in ('', 'high'):
                    with self.subTest(family=family, effort=effort):
                        selection = config.ModelEffort('chosen-model', effort)
                        adapter = adapters.for_model(family, models, selection)
                        argv = shlex.split(adapter.command(inp))
                        self.assertEqual(argv[argv.index('--model') + 1], 'chosen-model')
                        if effort and family == 'codex':
                            self.assertIn('model_reasoning_effort=high', argv)
                        elif effort:
                            self.assertEqual(argv[argv.index('--effort') + 1], effort)
                        else:
                            self.assertNotIn('--effort', argv)
                            self.assertFalse(any(a.startswith('model_reasoning_effort=') for a in argv))
                # 티켓 tier 생략은 medium. legacy 모델이 있어도 표의 모델이 우선한다.
                _, selection = cfg.tiers.worker(family)
                argv = shlex.split(adapters.for_model(family, models, selection).command(inp))
                self.assertEqual(argv[argv.index('--model') + 1], selection.model)
                argv = shlex.split(adapters.for_model(family, models).command(inp))
                self.assertNotIn('--effort', argv)
                if family == 'claude':
                    self.assertNotIn('--model', argv)
                else:
                    self.assertEqual(argv[argv.index('--model') + 1], getattr(models, family))
            argv = shlex.split(adapters.Codex(config.ModelsConfig('j', 'r', 'a', '')).command(inp))
            self.assertNotIn('--model', argv)

    def test_coordinator_selects_table_or_legacy_and_records_each_attempt(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('GS_WORKER_CMD', None)
            for text in (self.default, CONFIG):
                cfg, problems = self.load(text)
                self.assertEqual(problems, [])
                for family in feature.FAMILIES:
                    ts = state.TicketState()
                    st = state.State('demo', tickets={'01': ts})
                    run = SimpleNamespace(cfg=cfg, st=st)
                    ticket = feature.Ticket('01', 'test', [], family, 'unused', self.repo / 'ticket')
                    for failures in (0, 1):
                        with self.subTest(table=text == self.default, family=family, failures=failures):
                            ts.failures = failures
                            state.begin_phase(ts, 'worker', family, attempt=failures + 1)
                            adapter = go._worker_adapter(run, ticket)
                            if text == self.default:
                                tier = 'medium' if failures == 0 else 'large'
                                expected = cfg.tiers.worker(family, tier)[1]
                            else:
                                tier = ''
                                expected = config.ModelEffort('' if family == 'claude' else getattr(cfg.models, family))
                            self.assertEqual(adapter.selection, expected)
                            self.assertEqual((ts.phases[-1]['tier'], ts.phases[-1]['actual_model'],
                                              ts.phases[-1]['effort']), (tier, expected.model, expected.effort))

    def test_agy_transient_detection_uses_selected_model(self):
        inp = adapters.WorkerInput(self.repo / 'brief', self.repo, self.repo / 'log')
        inp.log.write_text('connection log')
        cfg = config.load(self.repo)[0]
        _, selected = cfg.tiers.worker('agy')
        with mock.patch.object(transient, 'reason', return_value='network') as reason:
            self.assertEqual(adapters.Agy(cfg.models, selected).transient_reason(inp), 'network')
        reason.assert_called_once_with('agy', 'connection log', model=selected.model, cwd=self.repo)

    def test_retry_promotes_exactly_one_tier_and_caps_at_large(self):
        cfg = config.load(self.repo)[0]
        for family in feature.FAMILIES:
            for tier, expected in ((None, 'large'), ('small', 'medium'), ('medium', 'large'), ('large', 'large')):
                self.assertEqual(cfg.tiers.worker(family, tier, failures=1),
                                 cfg.tiers.worker(family, expected))


class TierExecutionTest(support.GoTest):
    def test_failure_then_transient_restart_and_fix_keep_promoted_tier_in_state(self):
        os.environ.pop('GS_WORKER_CMD')
        os.environ['GS_NETWORK_MINUTE'] = '0.01'
        script = self.bin / 'claude'
        script.write_text('''#!/bin/bash
here="$(dirname "$0")"
if [ "$1" = plugin ]; then echo '[]'; exit 0; fi
echo "$@" >> "$here/worker.args"
n=$(( $(cat "$here/worker.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/worker.n"
if [ "$n" = 1 ]; then echo boom; exit 1; fi
if [ "$n" = 2 ]; then
  echo '{"type":"result","is_error":true,"api_error":"connection_failed","result":"Connection refused (ECONNREFUSED)"}'
  exit 1
fi
echo "$n" > file_01; git add -A; git commit -qm "worker $n"
''')
        script.chmod(0o755)
        path = self.repo / '.goldstack/work/demo/tickets/01-t.md'
        path.write_text(support.ticket('01').replace('reviewer: codex\n', 'reviewer: codex\ntier: small\n'))
        support.sh(self.repo, 'git', 'add', '-A')
        support.sh(self.repo, 'git', 'commit', '-qm', 'tier')
        support.sh(self.repo, 'git', 'push', '-q', self.REMOTE, self.BASE)
        with self.review_with([{'severity': 'high', 'location': 'file_01:1', 'claim': 'FIX: wrong',
                                'evidence': 'value'}]):
            code, out, err = self.go('--only', '01')
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, 'demo').ticket('01')
        self.assertEqual((ts.status, ts.failures, ts.transient_errors), ('merged', 1, 1))
        phases = [p for p in ts.phases if p['phase'] in ('worker', 'fix', 'fix2')]
        self.assertGreaterEqual(len(phases), 4)
        self.assertEqual([p['tier'] for p in phases], ['small'] + ['medium'] * (len(phases) - 1))
        self.assertEqual([p['effort'] for p in phases], ['medium'] + ['high'] * (len(phases) - 1))
        self.assertTrue(all(p['actual_model'] == 'sonnet' for p in phases))
        self.assertEqual([p['attempt'] for p in phases[:3]], [1, 2, 3])
        args = (self.bin / 'worker.args').read_text().splitlines()
        self.assertEqual(len(args), len(phases))
        self.assertIn('--model sonnet --effort medium', args[0])
        self.assertTrue(all('--model sonnet --effort high' in line for line in args[1:]))
