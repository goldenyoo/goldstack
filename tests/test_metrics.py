"""v7 측정: 실제 종료·처리 대기, 호출별 검증·리뷰, 마무리, 설치본, 옛 상태와 측정 오류 격리."""
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from gs import config, go, metrics, report, review, state, status, transient, verify, worker
from gs.feature import Ticket


class MetricsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.st = state.State('demo')
        self.run = SimpleNamespace(st=self.st, save=lambda: state.save(self.root, self.st))

    def test_exit_mtime_and_first_processing_are_separate_and_persisted(self):
        ts = self.st.ticket('01')
        state.begin_phase(ts, 'worker', 'codex', attempt=3)
        metrics.worker_selection(ts, 'large', config.ModelEffort('chosen', 'high'))
        job = worker.Job(Ticket('01', 't', [], 'codex', 'claude', self.root / 'ticket'), self.root, self.root)
        metrics.worker_started(self.run, job)
        rec = self.st.metrics['workers'][0]
        start = datetime.now().astimezone() - timedelta(seconds=90)
        rec['started_at'] = start.isoformat()
        exited = (start + timedelta(seconds=60)).timestamp()
        job.exit_file.write_text('0')
        os.utime(job.exit_file, (exited, exited))
        metrics.worker_finished(self.run, job)
        before = dict(rec)
        metrics.worker_finished(self.run, job)  # 네트워크 대기 뒤 다시 처리해도 시각을 덮어쓰지 않는다
        got = state.load(self.root, 'demo').metrics['workers'][0]
        self.assertEqual(got, before)
        self.assertEqual((got['attempt'], got['actual_model'], got['effort']), (3, 'chosen', 'high'))
        self.assertAlmostEqual(datetime.fromisoformat(got['worker_exited_at']).timestamp(), exited, places=5)
        self.assertAlmostEqual(got['seconds'], 60, places=4)
        self.assertGreaterEqual(got['processing_wait_seconds'], 30)
        self.assertGreaterEqual(got['processing_started_at'], got['worker_exited_at'])

    def test_old_finished_worker_has_unknown_time_and_its_own_phase(self):
        for phase, dirname in [('worker', '3'), ('fix', '3/fix'), ('fix2', '3/fix2-net1')]:
            with self.subTest(phase=phase):
                ts = self.st.ticket('01')
                ts.phases = []
                state.begin_phase(ts, phase, 'codex', attempt=3)
                metrics.worker_selection(ts, 'large', config.ModelEffort('actual', 'high'))
                state.begin_phase(ts, 'review', 'claude')
                state.begin_phase(ts, phase, 'agy', attempt=4)
                metrics.worker_selection(ts, 'medium', config.ModelEffort('other', 'low'))
                state.begin_phase(ts, 'review', 'claude')
                directory = self.root / dirname
                directory.mkdir(parents=True, exist_ok=True)
                job = worker.Job(Ticket('01', 't', [], 'codex', 'claude', self.root / 'ticket'),
                                 self.root, directory)
                job.exit_file.write_text('0')
                metrics.worker_finished(self.run, job)
                rec = state.load(self.root, 'demo').metrics['workers'][-1]
                self.assertEqual((rec['attempt'], rec['phase'], rec['model'], rec['actual_model'], rec['effort']),
                                 (3, phase, 'codex', 'actual', 'high'))
                self.assertEqual(rec['started_at'], '')
                self.assertIsNone(rec['seconds'])
                self.assertTrue(rec['worker_exited_at'])
                self.assertGreaterEqual(rec['processing_wait_seconds'], 0)
                text = report.measurements(SimpleNamespace(st=self.st, order=['01']))
                self.assertIn(f'| 01/3/{phase} | codex | actual/high | 기록 없음 |', text)

    def test_old_finished_worker_without_phase_history_still_records_exit(self):
        directory = self.root / '2'
        directory.mkdir()
        job = worker.Job(Ticket('01', 't', [], 'codex', 'claude', self.root / 'ticket'), self.root, directory)
        job.exit_file.write_text('0')
        metrics.worker_finished(self.run, job)
        rec = state.load(self.root, 'demo').metrics['workers'][0]
        self.assertEqual((rec['attempt'], rec['phase'], rec['model']), (2, 'worker', 'codex'))
        self.assertIsNone(rec['seconds'])
        self.assertTrue(rec['worker_exited_at'])

    def test_verify_records_each_retry_command_sha_time_and_result(self):
        spec = SimpleNamespace(verify='test command', verify_retries=1)
        with mock.patch.object(verify, '_run_once', side_effect=[verify.Result(1, False, '1'), verify.Result(0, False, '1')]), \
                mock.patch.object(metrics, 'monotonic', side_effect=[10, 13, 13, 20]):
            result = verify.run(spec, self.root, io.StringIO())
        metrics.validation(self.run, 'ticket-01', spec.verify, 'head-sha', result, tree_sha='merged-tree', merge_head='ticket-sha')
        rows = state.load(self.root, 'demo').metrics['validations']
        self.assertEqual([(r['seconds'], r['result'], r['attempt']) for r in rows], [(3, 'failed', 1), (7, 'passed', 2)])
        self.assertTrue(all((r['label'], r['command'], r['sha'], r['tree_sha'], r['merge_head']) ==
                            ('ticket-01', 'test command', 'head-sha', 'merged-tree', 'ticket-sha') for r in rows))

    def test_timeout_and_changed_tree_remain_failed_in_metrics(self):
        for result, changed, expected in [(verify.Result(-15, True, '1'), False, 'timeout'),
                                          (verify.Result(0, False, '1'), True, 'tree_changed')]:
            samples = []
            metrics.sample(samples, metrics.clock(), result)
            metrics.validation(self.run, 'main-recheck', 'check', 'sha', replace(result, samples=tuple(samples)), changed)
            rec = state.load(self.root, 'demo').metrics['validations'][-1]
            self.assertEqual(rec['result'], expected)
            self.assertFalse(rec['accepted'])

    def test_install_commit_comes_from_distribution_not_target_repo(self):
        for raw, expected in [(json.dumps({'vcs_info': {'commit_id': 'installed-commit'}}), 'installed-commit'),
                              ('{"url":"file:///local/path"}', ''), ('broken', '')]:
            with mock.patch.object(metrics.metadata, 'version', return_value='0.1.0'), \
                    mock.patch.object(metrics.metadata, 'distribution') as dist:
                dist.return_value.read_text.return_value = raw
                metrics.runtime(self.run)
            self.assertEqual(self.st.metrics['runtime'][-1]['install_commit'], expected)
            self.assertEqual(self.st.metrics['runtime'][-1]['version'], '0.1.0')

    def test_stage_failure_keeps_original_exception_and_elapsed(self):
        @metrics.stage('publish')
        def action(r):
            raise ValueError('original failure')
        with self.assertRaisesRegex(ValueError, 'original failure'):
            action(self.run)
        rec = state.load(self.root, 'demo').metrics['finish_stages'][0]
        self.assertEqual(rec['label'], 'publish')
        self.assertIsInstance(rec['seconds'], float)
        self.assertTrue(rec['ended_at'])
        with mock.patch.object(metrics, 'monotonic', side_effect=OSError('clock')), \
                mock.patch.object(self.run, 'save', side_effect=OSError('measurement storage')):
            with self.assertRaisesRegex(ValueError, 'original failure'):
                action(self.run)

    def test_resume_closes_interrupted_stages_before_overwriting_last_save_time(self):
        self.st.metrics['finish_stages'] = [
            dict(label='total', started_at='2020-01-01T00:00:00+00:00', ended_at='', seconds=None),
            dict(label='checks', started_at='2020-01-01T00:00:10+00:00', ended_at='', seconds=None),
            dict(label='total', seconds=5, ended_at='2020-01-01T00:00:00+00:00'),
        ]
        state.save(self.root, self.st)
        raw = json.loads(state.path(self.root).read_text())
        raw['updated_at'] = '2020-01-01T00:00:30+00:00'
        state.path(self.root).write_text(json.dumps(raw))  # finally 없이 종료된 state
        r = SimpleNamespace(rundir=self.root, repo=self.root, name='demo', only=None, remote='origin')
        r.save = lambda: state.save(self.root, r.st)
        with mock.patch.object(go, '_graph', return_value={}):
            go._begin(r)
            go._begin(r)  # 次の再開でも終了時刻・時間を増やさない
        rows = state.load(self.root, 'demo').metrics['finish_stages']
        self.assertEqual([x['seconds'] for x in rows], [30, 20, 5])
        self.assertTrue(all(x['ended_at'] == raw['updated_at'] and x['interrupted'] for x in rows[:2]))
        # 再開後の進行中段階は従来通り報告時点までを足す。12時間の停止は足さない。
        r.st.metrics['finish_stages'].append(
            dict(label='total', started_at='2020-01-01T12:00:00+00:00', seconds=None))
        with mock.patch.object(state, 'now', return_value='2020-01-01T12:00:10+00:00'):
            text = report.measurements(r)
        self.assertIn('| total | 45.0 |', text)
        self.assertIn('| checks | 20.0 |', text)
        self.assertIn('| checks | 20.0 |\n\n중단된 마무리 단계는 ', text)
        self.assertIn('실제 소요의 하한', text)

    def test_old_state_status_and_report_without_metrics(self):
        run = self.root / '.goldstack/work/demo/run'
        run.mkdir(parents=True)
        state.path(run).write_text(json.dumps({'feature': 'demo', 'tickets': {'01': {'status': 'merged'}}}))
        got = state.load(run, 'demo')
        self.assertEqual(got.metrics, {})
        out = io.StringIO()
        self.assertEqual(status.status(self.root, 'demo', out), 0)
        self.assertIn('01', out.getvalue())
        r = SimpleNamespace(st=got, order=['01'])
        self.assertIn('gs 버전·설치 commit: 기록 없음', report.measurements(r))
        self.assertIn('일시 오류 0회', report.measurements(r))

    def test_report_has_network_and_all_measurement_summaries(self):
        self.st.metrics = {
            'runtime': [dict(version='0.1.0', install_commit='install-sha', started_at='now')],
            'workers': [dict(ticket='01', attempt=2, phase='fix', model='codex', actual_model='worker-model', effort='high',
                             seconds=60, processing_wait_seconds=30)],
            'reviewers': [dict(ticket='01', reviewer='claude', round=0, actual_model='review-model', effort='xhigh',
                               seconds=50, findings_count=3, fix_count=2)],
            'validations': [dict(label='integration', attempt=1, command='check | tee log', sha='verify-sha', seconds=20,
                                 result='passed')],
            'finish_stages': [dict(label='summary', seconds=5)],
        }
        self.st.network = dict(errors=3, waited_seconds=123)
        self.st.ticket('01').transient_errors = 2
        self.st.ticket('01').network_wait_seconds = 60
        r = SimpleNamespace(st=self.st, order=['01'])
        text = report.measurements(r)
        for expected in ['gs 0.1.0', 'install-sha', 'worker-model/high', 'review-model/xhigh', '50 | 3 | 2',
                         'summary | 5', 'verify-sha', 'check \\| tee log', '일시 오류 3회 · 대기 123.0초',
                         '01: 일시 오류 2회 · 대기 60.0초']:
            self.assertIn(expected, text)

    def test_measurement_errors_do_not_change_verification_result(self):
        class Broken(dict):
            def setdefault(self, *args):
                raise OSError('metrics sink')
        self.st.metrics = Broken()
        @metrics.stage('test')
        def action(r):
            return True
        self.assertTrue(action(self.run))
        metrics.runtime(self.run)
        self.assertIsNone(report.measurements(SimpleNamespace(st=SimpleNamespace(metrics=None))))
        with mock.patch.object(metrics, 'monotonic', side_effect=ValueError('clock')), \
                mock.patch.object(verify, '_run_once', return_value=verify.Result(0, False, '1')):
            result = verify.run(SimpleNamespace(verify_retries=0), self.root, io.StringIO())
        self.assertTrue(result.ok)

    def test_reviewer_retry_records_model_effort_and_failed_attempt(self):
        cfg = SimpleNamespace(models=None, timeouts=config.TimeoutsConfig(30, 10, 60))
        wait = review.CallWait(self.st, self.run.save, '01')
        answers = [review.ReviewTransient('network'), '{"findings": []}']
        with mock.patch.object(review, '_call', side_effect=answers), \
                mock.patch.object(review, '_env', return_value={}), \
                mock.patch.object(review, 'reviewer_argv', return_value=(['fake'], 'prompt', False)):
            # 직접 _ask_reviewer의 on_wait는 즉시 대기로 바꿔도 측정의 state·lock을 유지한다.
            class InstantWait:
                def __init__(self):
                    self.st, self.save, self.tid, self.lock = wait.st, wait.save, wait.tid, wait.lock

                def __call__(self, *args):
                    pass
            review._ask_reviewer('claude', self.root, 'prompt', self.root, 60, cfg, InstantWait(),
                                 config.ModelEffort('actual', 'high'))
        rows = state.load(self.root, 'demo').metrics['review_calls']
        self.assertEqual([x['result'] for x in rows], ['error', 'passed'])
        self.assertTrue(all((x['actual_model'], x['effort']) == ('actual', 'high') for x in rows))

    def test_aborted_review_call_keeps_its_model_and_time(self):
        wait = review.CallWait(self.st, self.run.save, '01')
        cfg = SimpleNamespace(models=None, timeouts=config.TimeoutsConfig(30, 10, 60, network_wait_minutes=0))
        with mock.patch.object(review, '_call', side_effect=review.ReviewTransient('network')), \
                mock.patch.object(review, '_env', return_value={}), \
                mock.patch.object(review, 'reviewer_argv', return_value=(['fake'], 'prompt', False)):
            with self.assertRaises(transient.NetworkAbort):
                review._ask_reviewer('claude', self.root, 'prompt', self.root, 60, cfg, wait,
                                     config.ModelEffort('actual', 'high'))
        rec = state.load(self.root, 'demo').metrics['review_calls'][0]
        self.assertEqual((rec['actual_model'], rec['effort'], rec['result']), ('actual', 'high', 'error'))
        self.assertIsInstance(rec['seconds'], float)


class MetricsExecutionTest(support.GoTest):
    def test_failed_worker_attempt_is_preserved_after_retry(self):
        (self.bin / 'worker.sh').write_text(
            'here="$(dirname "$0")"\n'
            'if [ ! -f "$here/once" ]; then touch "$here/once"; exit 1; fi\n'
            'echo done > file_01; git add file_01; git commit -qm done\n')
        code, out, err = self.go('--only', '01')
        self.assertEqual(code, 0, out + err)
        rows = state.load(self.rundir, 'demo').metrics['workers']
        self.assertEqual([x['attempt'] for x in rows], [1, 2])
        self.assertTrue(all(x['worker_exited_at'] and x['processing_started_at'] for x in rows))

    def test_worker_review_fix_finish_metrics_reach_state_and_report(self):
        with self.review_with([{'severity': 'high', 'location': 'file_01', 'claim': 'FIX value', 'evidence': 'wrong'}]):
            code, out, err = self.go('--only', '01')
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, 'demo')
        data = st.metrics
        self.assertEqual([x['phase'] for x in data['workers']], ['worker', 'fix'])
        for x in data['workers']:
            self.assertTrue(x['worker_exited_at'])
            self.assertTrue(x['processing_started_at'])
            self.assertGreaterEqual(x['seconds'], 0)
            self.assertGreaterEqual(x['processing_wait_seconds'], 0)
        self.assertEqual([x['label'] for x in data['validations']], ['ticket-01', 'integration', 'main'])
        self.assertTrue(all(x['result'] == 'passed' and x['sha'] for x in data['validations']))
        self.assertTrue(data['validations'][0]['tree_sha'])
        self.assertTrue(data['validations'][0]['merge_head'])
        self.assertEqual(data['reviewers'][0]['fix_count'], 1)
        self.assertEqual(data['reviewers'][0]['findings_count'], 1)
        self.assertGreaterEqual(st.ticket('01').review['seconds'], 0)
        self.assertGreaterEqual(st.ticket('01').review['rereviews'][0]['seconds'], 0)
        self.assertEqual(len(data['review_calls']), 2)
        self.assertTrue({'summary', 'verify', 'report', 'push', 'publish', 'merge-pr'} <=
                        {x['label'] for x in data['finish_stages']})
        for x in data['finish_stages']:
            self.assertIsInstance(x['seconds'], float)
        text = self.final_report()
        self.assertEqual(sum(line.startswith('| 01 |') for line in text.splitlines()), 1)
        for s in ['worker 시도별', '리뷰어별 소요와 채택', '마무리 단계별 시간', 'gs 0.1.0', '일시 오류', 'integration/1']:
            self.assertIn(s, text)

    def test_measurement_clock_and_metadata_errors_still_merge(self):
        with mock.patch.object(metrics, 'clock', return_value=None), \
                mock.patch.object(metrics.metadata, 'distribution', side_effect=OSError('metadata')), \
                mock.patch.object(metrics.metadata, 'version', return_value='0.1.0'):
            code, out, err = self.go('--only', '01')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, 'demo').finish['phase'], 'verified')

    def test_old_state_can_resume_execution(self):
        self.rundir.mkdir(parents=True)
        state.path(self.rundir).write_text(json.dumps({'feature': 'demo', 'tickets': {'01': {'status': 'pending'}}}))
        code, out, err = self.go('--only', '01')
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, 'demo').ticket('01').status, 'merged')


if __name__ == '__main__':
    unittest.main()
