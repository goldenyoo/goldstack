"""리뷰·재리뷰의 등급별 argv, 읽기 전용 장치, 모델 기록과 판단 호출별 모델 선택."""
import json
import os
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config, failure, report, review, state


class ReviewTiersTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / '.goldstack').mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        self.cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.cfg = replace(self.cfg, models=config.ModelsConfig('judge-model', 'legacy-review', 'legacy-agy',
                                                               'legacy-codex', 'summary-model'))
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('GS_REVIEWER_CMD', None)
        self.rdir = self.repo / 'review'
        self.found = asdict(review.Finding(1, 'high', 'a:1', 'claim', 'evidence', action=review.FIX))

    def run_review(self, family, cfg=None, nth=0, error=False):
        answer = json.dumps({'findings': [], 'verdicts': [
            {'id': 1, 'status': 'resolved', 'evidence': 'fixed'}]})

        def call(argv, **kwargs):
            if error:
                raise review.ReviewError('failed')
            # codex는 stdout 대신 지정한 파일에 최종 답을 쓴다.
            if '--output-last-message' in argv:
                Path(argv[argv.index('--output-last-message') + 1]).write_text(answer)
                return 'events'
            return answer

        with mock.patch.object(review, '_call', side_effect=call) as called, \
                mock.patch.object(review, '_env', return_value={}), \
                mock.patch.object(review, 'write_diff', return_value=('base', False)), \
                mock.patch.object(review.git, 'run', return_value=SimpleNamespace(stdout='diff')):
            common = dict(repo=self.repo, worktree=self.repo, rdir=self.rdir,
                          ticket=self.repo / 'ticket', spec=self.repo / 'spec', reviewer=family,
                          cfg=cfg or self.cfg)
            if nth:
                rec = review.rereview(**common, base='base', head='head', found=[self.found], nth=nth)
            else:
                rec = review.run(**common, base='base', branch='branch',
                                 model='codex' if family == 'claude' else 'claude')
        called.assert_called_once()
        return rec, called.call_args.args[0], called.call_args.kwargs

    def assert_options(self, argv, family, model, effort):
        if model:
            self.assertEqual(argv[argv.index('--model') + 1], model)
        else:
            self.assertNotIn('--model', argv)
        if effort and family == 'codex':
            self.assertEqual(argv[argv.index('-c') + 1], 'model_reasoning_effort=' + effort)
            self.assertNotIn('--effort', argv)
        elif effort:
            self.assertEqual(argv[argv.index('--effort') + 1], effort)
            self.assertNotIn('-c', argv)
        else:
            self.assertNotIn('--effort', argv)
            self.assertNotIn('-c', argv)
        if family == 'claude':
            self.assertEqual(argv[argv.index('--tools') + 1], 'Read,Grep,Glob')
        elif family == 'codex':
            self.assertEqual(argv[argv.index('-s') + 1], 'read-only')
        else:
            self.assertIn('--sandbox', argv)

    def test_first_review_and_both_rereviews_use_configured_tiers_and_record_selection(self):
        for cfg in (self.cfg, replace(self.cfg, tiers=replace(self.cfg.tiers, review='small', rereview='large'))):
            for family in ('claude', 'codex', 'agy'):
                rec = None
                for nth in (0, 1, 2):
                    with self.subTest(review_tier=cfg.tiers.review, family=family, nth=nth):
                        tier = cfg.tiers.rereview if nth else cfg.tiers.review
                        selected = getattr(cfg.tiers, family)[tier]
                        result, argv, kwargs = self.run_review(family, cfg, nth)
                        self.assert_options(argv, family, selected.model, selected.effort)
                        expected = (tier, selected.model, selected.effort)
                        self.assertEqual(tuple(result[k] for k in ('tier', 'actual_model', 'effort')), expected)
                        self.assertEqual(kwargs['model'], selected.model if family == 'agy' else '')
                        if nth:
                            review.apply_rereview(rec, [self.found], result, nth)
                            self.assertEqual(tuple(rec['rereviews'][-1][k]
                                                   for k in ('tier', 'actual_model', 'effort')), expected)
                        else:
                            rec = result
                            rec['findings'] = [self.found]
                # state를 썼다 읽어도 회차별 선택을 보존한다.
                st = state.State('demo', tickets={'01': state.TicketState(review=rec)})
                state.save(self.repo / 'run', st)
                self.assertEqual(state.load(self.repo / 'run', 'demo').ticket('01').review, rec)

    def test_effort_is_optional_for_all_families_including_agy(self):
        for family in ('claude', 'codex', 'agy'):
            for effort in ('', 'high'):
                for nth in (0, 1):
                    with self.subTest(family=family, effort=effort, nth=nth):
                        selected = config.ModelEffort('chosen-model', effort)
                        tiers = replace(self.cfg.tiers, **{family: {tier: selected for tier in config.TIERS}})
                        result, argv, _ = self.run_review(family, replace(self.cfg, tiers=tiers), nth)
                        self.assert_options(argv, family, selected.model, effort)
                        self.assertEqual(result['effort'], effort)

    def test_missing_family_table_preserves_legacy_models_and_default_effort(self):
        for tiers in (config.TiersConfig(), replace(self.cfg.tiers, codex=None)):
            cfg = replace(self.cfg, tiers=tiers)
            families = ('claude', 'codex', 'agy') if tiers.claude is None else ('codex',)
            for family in families:
                for nth in (0, 1, 2):
                    with self.subTest(family=family, nth=nth, partial=tiers.claude is not None):
                        model = cfg.models.claude_review if family == 'claude' else getattr(cfg.models, family)
                        result, argv, _ = self.run_review(family, cfg, nth)
                        self.assert_options(argv, family, model, '')
                        self.assertEqual((result['tier'], result['actual_model'], result['effort']), ('', model, ''))
        cfg = replace(cfg, models=replace(cfg.models, codex=''))
        for nth in (0, 1):
            result, argv, _ = self.run_review('codex', cfg, nth)
            self.assert_options(argv, 'codex', '', '')
            self.assertEqual(result['actual_model'], '')

    def test_failed_calls_keep_selected_model_and_effort(self):
        for family in ('claude', 'codex', 'agy'):
            for nth in (0, 1):
                with self.subTest(family=family, nth=nth):
                    result, _, _ = self.run_review(family, nth=nth, error=True)
                    tier = 'medium' if nth else 'large'
                    selected = getattr(self.cfg.tiers, family)[tier]
                    self.assertEqual((result['tier'], result['actual_model'], result['effort']),
                                     (tier, selected.model, selected.effort))
                    self.assertTrue(result['note'])

    def test_old_rereview_result_can_still_be_applied(self):
        rec = {'findings': []}
        review.apply_rereview(rec, [], dict(dir='', base='', head='', note='', failed='', verdicts={}, findings=[]), 1)
        self.assertEqual(rec['rereviews'][0]['actual_model'], '')

    def test_failure_summary_uses_its_model_while_classification_and_report_keep_judge(self):
        for models in (self.cfg.models, config.ModelsConfig('old-judge', 'r', 'a', 'c')):
            cfg = replace(self.cfg, models=models)
            log = self.repo / 'failure.log'
            log.write_text('failed')
            self.rdir.mkdir(exist_ok=True)
            with mock.patch.object(review, '_call', return_value='summary') as called:
                summary = failure.summarize(self.repo, log, cfg)
            self.assertIn('summary', summary.read_text())
            self.assert_judge(called, models.failure_summary)

            with mock.patch.object(review, '_call', return_value='{"decisions": []}') as called, \
                    mock.patch.object(review, '_env', return_value={}):
                review.classify(self.rdir, self.repo, [review.Finding(1, 'high', 'a', 'c', 'e')],
                                self.repo / 'diff', self.repo / 'ticket', self.repo / 'spec', cfg)
            self.assert_judge(called, models.judge)

            run = SimpleNamespace(cfg=cfg, rundir=self.repo, iwt=self.repo, base_ref='base',
                                  feat=SimpleNamespace(spec=SimpleNamespace(path=self.repo / 'spec')),
                                  st=SimpleNamespace(finish={}))
            with mock.patch.object(report, 'evidence', return_value='facts'), \
                    mock.patch.object(report.git, 'out', return_value='diff'), \
                    mock.patch.object(review, '_env', return_value={}), \
                    mock.patch.object(review, '_call', return_value='summary') as called:
                self.assertEqual(report.summarize(run), 'summary')
            self.assert_judge(called, models.judge)

    def assert_judge(self, called, model):
        called.assert_called_once()
        argv = called.call_args.args[0]
        self.assertEqual(argv[argv.index('--model') + 1], model)
        self.assertEqual(argv[argv.index('--tools') + 1], 'Read')


if __name__ == '__main__':
    unittest.main()
