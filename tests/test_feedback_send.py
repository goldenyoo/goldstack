"""가짜 gh로 피드백 전송·실패 보존·명시적 CLI를 확인한다."""
from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date as real_date
from pathlib import Path
from unittest import mock

import test_config
from support import isolate_git_env
from gs import cli, config, feedback

ENV = feedback.Environment("0.1.0", "Linux 6.0 x86_64", (("gh", "2.0"),))
FAKE_GH = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
root = Path(os.environ['FAKE_GH_ROOT'])
with (root / 'calls').open('a') as f:
    f.write(json.dumps(args) + '\n')
def value(flag):
    return args[args.index(flag) + 1]
if args[:2] == ['issue', 'list']:
    if os.environ.get('FAKE_FAIL') == 'list':
        print('secret auth failure', file=sys.stderr)
        sys.exit(1)
    issues = json.loads((root / 'issues').read_text()) if (root / 'issues').exists() else []
    print(json.dumps([i for i in issues if value('--search') in i['body'] and not i.get('closed')]))
elif args[:2] == ['label', 'list']:
    print(os.environ.get('FAKE_LABELS', '[]'))
elif args[:2] == ['label', 'create']:
    sys.exit(1 if os.environ.get('FAKE_FAIL') == 'label' else 0)
elif args[:2] == ['issue', 'create']:
    if os.environ.get('FAKE_FAIL') == 'create':
        sys.exit(1)
    issues = json.loads((root / 'issues').read_text()) if (root / 'issues').exists() else []
    number = len(issues) + 1
    issues.append({'number': number, 'body': value('--body')})
    (root / 'issues').write_text(json.dumps(issues))
    print('https://github.com/owner/inbox/issues/' + str(number))
elif args[:2] == ['issue', 'comment']:
    sys.exit(1 if os.environ.get('FAKE_FAIL') == 'comment' else 0)
else:
    sys.exit(2)
'''


class FeedbackSendTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.fake = self.repo / 'gh'
        self.fake.write_text(f'#!{sys.executable}\n' + FAKE_GH)
        self.fake.chmod(0o755)
        env = mock.patch.dict(os.environ, {'GS_GH': str(self.fake), 'FAKE_GH_ROOT': str(self.repo)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('GS_ROLE', None)
        probe = mock.patch('gs.feedback.environment', return_value=ENV)
        probe.start()
        self.addCleanup(probe.stop)
        self.cfg = config.Config(config.GitConfig('origin', 'main'), config.ModelsConfig('o', 'o', 'a', ''),
                                 config.TimeoutsConfig(30, 10, 60), config.NotifyConfig(False),
                                 feedback=config.FeedbackConfig('auto', 'errors', 'owner/inbox', 5))
        self.err = io.StringIO()

    def record(self, kind='GitError', cfg=None):
        return feedback.record(self.repo, cfg or self.cfg, phase='verify', kind=kind,
                               frames=[], error_lines=['fatal: permission denied', 'token=ghp_SUPERSECRET'])

    def send(self, **kw):
        return feedback.send(self.repo, self.cfg, err=self.err, **kw)

    def calls(self, *prefix):
        path = self.repo / 'calls'
        calls = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return [args for args in calls if args[:len(prefix)] == list(prefix)]

    def tomorrow(self):
        # 날짜만 바꿔 디스크에 남은 장부가 다음 실행에도 적용되는지 본다.
        patch = mock.patch('datetime.date')
        fake_date = patch.start()
        self.addCleanup(patch.stop)
        fake_date.today.return_value = real_date(2099, 1, 1)

    def test_auto_sends_safe_body_and_marks_sent(self):
        path = self.record()
        self.assertEqual(self.send(), 1)
        self.assertEqual(self.send(), 0)
        create, = self.calls('issue', 'create')
        self.assertEqual(create[create.index('--repo') + 1], 'owner/inbox')
        body = create[create.index('--body') + 1]
        self.assertIn('- 지문:', body)
        self.assertNotIn('ghp_SUPERSECRET', body)
        self.assertNotIn(feedback.LOCAL_MARKER, body)
        self.assertIn('ghp_SUPERSECRET', path.read_text())
        self.assertEqual(feedback.read_draft(path, self.cfg).meta['sent_count'], '1')
        self.assertEqual(self.err.getvalue(), '')

    def test_draft_only_stores_off_does_neither(self):
        for mode in ('draft', 'off'):
            cfg = dataclasses.replace(self.cfg, feedback=dataclasses.replace(self.cfg.feedback, mode=mode))
            path = self.record(cfg=cfg)
            self.assertEqual(path is None, mode == 'off')
            self.assertEqual(feedback.send(self.repo, cfg, err=self.err), 0)
        self.assertEqual(self.calls(), [])

    def test_off_does_not_touch_existing_drafts_even_when_forced(self):
        path = self.record()
        before = path.read_bytes()
        cfg = dataclasses.replace(self.cfg, feedback=config.FeedbackConfig('off'))
        self.assertEqual(feedback.send(self.repo, cfg, force=True), 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.calls(), [])

    def test_existing_issue_gets_one_count_comment_a_day(self):
        path = self.record()
        draft = feedback.read_draft(path, self.cfg)
        (self.repo / 'issues').write_text(json.dumps([{'number': 12, 'body': draft.body}]))
        self.assertEqual(self.send(), 1)
        self.record()
        self.assertEqual(self.send(), 0)
        self.assertEqual(self.calls('issue', 'create'), [])
        self.assertEqual(len(self.calls('issue', 'comment')), 1)
        self.tomorrow()
        self.assertEqual(self.send(), 1)
        comment = self.calls('issue', 'comment')[-1]
        self.assertIn('- 횟수: 2', comment[comment.index('--body') + 1])
        self.assertEqual(self.send(), 0)

    def test_closed_or_partial_fingerprint_is_not_a_duplicate(self):
        draft = feedback.read_draft(self.record(), self.cfg)
        (self.repo / 'issues').write_text(json.dumps([
            {'number': 1, 'body': draft.body, 'closed': True},
            {'number': 2, 'body': '- 지문: ' + draft.fingerprint + 'extra'}]))
        self.assertEqual(self.send(), 1)
        self.assertEqual(len(self.calls('issue', 'create')), 1)
        self.assertEqual(self.calls('issue', 'comment'), [])

    def test_daily_cap_persists_and_deferred_drafts_send_tomorrow(self):
        self.cfg = dataclasses.replace(self.cfg, feedback=dataclasses.replace(self.cfg.feedback, max_per_day=1))
        self.record('GitError')
        self.record('KeyError')
        self.assertEqual(self.send(), 1)
        self.assertEqual(self.send(), 0)
        self.tomorrow()
        self.assertEqual(self.send(), 1)
        self.assertEqual(len(self.calls('issue', 'create')), 2)

    def test_failures_leave_draft_retryable_and_print_only_one_line(self):
        for failure in ('list', 'create', 'missing'):
            with self.subTest(failure=failure):
                path = self.record()
                with mock.patch.dict(os.environ, {'FAKE_FAIL': failure, 'GS_GH': '/no/such/gh' if failure == 'missing' else str(self.fake)}):
                    self.assertEqual(self.send(), 0)
                self.assertNotIn('sent_count', feedback.read_draft(path, self.cfg).meta)
                self.assertEqual(len(self.err.getvalue().splitlines()), 1)
                self.assertNotIn('secret auth failure', self.err.getvalue())
                self.err.seek(0)
                self.err.truncate()
        self.assertEqual(self.send(), 1)

    def test_comment_failure_retries_and_does_not_spend_daily_quota(self):
        draft = feedback.read_draft(self.record(), self.cfg)
        (self.repo / 'issues').write_text(json.dumps([{'number': 4, 'body': draft.body}]))
        with mock.patch.dict(os.environ, {'FAKE_FAIL': 'comment'}):
            self.assertEqual(self.send(), 0)
        self.assertEqual(self.send(), 1)

    def test_missing_labels_are_created_existing_labels_are_kept(self):
        self.record()
        with mock.patch.dict(os.environ, {'FAKE_LABELS': '[{"name":"field-report"}]'}):
            self.assertEqual(self.send(), 1)
        self.assertEqual([args[2] for args in self.calls('label', 'create')], ['gs-0.1.0', 'verify'])
        self.assertEqual(self.calls('issue', 'create')[0].count('--label'), 3)

    def test_label_permission_failure_still_creates_without_labels(self):
        self.record()
        with mock.patch.dict(os.environ, {'FAKE_FAIL': 'label'}):
            self.assertEqual(self.send(), 1)
        self.assertNotIn('--label', self.calls('issue', 'create')[0])
        self.assertEqual(self.err.getvalue(), '')

    def test_minimal_at_send_time_removes_old_error_lines(self):
        self.record()
        self.cfg = dataclasses.replace(self.cfg, feedback=dataclasses.replace(self.cfg.feedback, detail='minimal'))
        self.assertEqual(self.send(), 1)
        self.assertNotIn(feedback.ERRORS_HEADING, str(self.calls('issue', 'create')))

    def test_worker_never_sends(self):
        self.record()
        with mock.patch.dict(os.environ, {'GS_ROLE': 'worker'}):
            self.assertEqual(self.send(force=True), 0)
        self.assertEqual(self.calls(), [])

    def test_invalid_drafts_do_not_block_other_drafts_or_repeat_sends(self):
        path = self.record()
        root = path.parent
        for name, body in (('00.md', 'broken'),
                           ('01.md', '---\ncount: 1\n---\nbody\n' + feedback.LOCAL_MARKER + '\n')):
            (root / name).write_text(body)
        self.assertEqual(self.send(), 1)
        self.assertEqual(len(self.err.getvalue().splitlines()), 1)
        self.assertTrue((root / '00.md').exists())
        self.assertEqual(self.send(), 0)
        self.assertEqual(len(self.calls('issue', 'create')), 1)

    def test_invalid_sent_count_does_not_block_other_drafts(self):
        path = self.record()
        draft = feedback.read_draft(path, self.cfg)
        feedback._write_draft(path.parent / '00.md',
                              {**draft.meta, 'sent_repo': self.cfg.feedback.repo, 'sent_count': 'bad'},
                              draft.body, '')
        self.assertEqual(self.send(), 1)
        self.assertEqual(len(self.err.getvalue().splitlines()), 1)

    def test_corrupt_ledger_defers_today_and_recovers_tomorrow(self):
        path = self.record()
        ledger = path.parent / '.send-state.json'
        for broken in ('{', '[]', 'null', '{"day":"2099-01-01"}',
                       json.dumps({'day': real_date.today().isoformat(), 'count': '1', 'issues': {}}),
                       json.dumps({'day': real_date.today().isoformat(), 'count': 0, 'issues': []})):
            with self.subTest(broken=broken):
                ledger.write_text(broken)
                self.err.seek(0)
                self.err.truncate()
                self.assertEqual(self.send(), 0)
                self.assertEqual(len(self.err.getvalue().splitlines()), 1)
                self.assertEqual(self.send(), 0)
                self.assertEqual(json.loads(ledger.read_text())['count'], self.cfg.feedback.max_per_day)
        self.assertEqual(self.calls(), [])
        self.tomorrow()
        self.assertEqual(self.send(), 1)

    def run_cli(self, *args, mode='draft', extra_config=''):
        (self.repo / ".goldstack").mkdir(exist_ok=True)
        (self.repo / config.CONFIG_PATH).write_text(test_config.CONFIG + '\n[feedback]\nmode = "' + mode + '"\nrepo = "owner/inbox"\n' + extra_config)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(['--repo', str(self.repo), 'feedback', *args])
        return code, out.getvalue(), err.getvalue()

    def test_status_lists_existing_drafts_without_changing_or_sending(self):
        path = self.record()
        (path.parent / 'broken.md').write_text('broken')
        for mode in ('auto', 'draft', 'off'):
            with self.subTest(mode=mode):
                before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
                listed = self.run_cli('list', mode=mode)
                self.assertEqual(listed[0], 0)
                self.assertIn('pending', listed[1])
                self.assertIn('broken.md invalid', listed[1])
                self.assertEqual(self.run_cli('status', mode=mode), listed)
                self.assertEqual({p.name: p.read_bytes() for p in path.parent.iterdir()}, before)
        self.assertEqual(self.calls(), [])

    def test_status_without_drafts_does_not_create_feedback_directory(self):
        self.assertEqual(self.run_cli('status'), self.run_cli('list'))
        self.assertEqual(self.run_cli('status'), (0, '', ''))
        self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        self.assertEqual(self.calls(), [])

    def test_status_prints_config_warnings_once_like_list(self):
        path = self.record()
        before = path.read_bytes()
        extra = '\n[unexpected]\nkey = "value"\n'
        listed = self.run_cli('list', extra_config=extra)
        self.assertEqual(listed[0], 0)
        self.assertEqual(len(listed[2].splitlines()), 1)
        self.assertIn('unexpected', listed[2])
        self.assertEqual(self.run_cli('status', extra_config=extra), listed)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.calls(), [])

    def test_unknown_single_word_never_creates_or_sends_drafts(self):
        # 따옴표 유무와 무관하게 셸은 한 단어를 같은 argv 한 항목으로 넘긴다.
        for mode in ('auto', 'draft'):
            for word in ('오타', 'statsu', 'sendd'):
                with self.subTest(mode=mode, word=word):
                    code, out, err = self.run_cli(word, mode=mode)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, '')
                    self.assertIn('subcommand가 아니다. 보내려면 gs feedback "문장"', err)
                    self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        path = self.record()
        before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
        self.assertEqual(self.run_cli('오타', mode='auto')[0], 2)
        self.assertEqual({p.name: p.read_bytes() for p in path.parent.iterdir()}, before)
        self.assertEqual(self.calls(), [])

    def test_manual_cli_sends_quoted_and_separate_words(self):
        for args in (('한 줄 이상의 문장',), ('두', '단어'), ('탭\t문장',), ('여러\n줄',)):
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(*args), (0, 'gs feedback: 1건 전송\n', ''))
                create = self.calls('issue', 'create')[-1]
                self.assertIn(' '.join(args), create[create.index('--body') + 1])
        self.assertEqual(len(self.calls('issue', 'create')), 4)

    def test_single_word_whitespace_bypasses_are_rejected(self):
        for mode in ('auto', 'draft'):
            for args in (('status ',), ('status', ''), ('', 'status'), ('\tstatus\n',),
                         ('send ',), ('list', ' '), (' ', ''), ('',)):
                with self.subTest(mode=mode, args=args):
                    self.assertEqual(self.run_cli(*args, mode=mode)[0], 2)
        self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        self.assertEqual(self.calls(), [])

    def test_body_file_preserves_text_redacts_environment_and_deduplicates(self):
        message = '## 증상\n재개 후 멈춤\n\n## 근거\n두 번 관찰\n\n## 제안\n재개 검사 추가\n'
        path = self.repo / '본문 파일.md'
        path.write_text(message, encoding='utf-8')
        unsafe_env = dataclasses.replace(ENV, os=f'Linux {self.repo}/private token=ghp_SUPERSECRET')
        with mock.patch('gs.feedback.environment', return_value=unsafe_env):
            for mode in ('draft', 'auto'):
                self.assertEqual(self.run_cli('--body-file', str(path), mode=mode)[0], 0)
        create, = self.calls('issue', 'create')
        body = create[create.index('--body') + 1]
        self.assertIn(message, body)
        self.assertNotIn(str(self.repo), body)
        self.assertNotIn('ghp_SUPERSECRET', body)
        drafts = list((self.repo / feedback.FEEDBACK_DIR).glob('*.md'))
        self.assertEqual(len(drafts), 1)
        self.assertEqual(feedback.read_draft(drafts[0], self.cfg).count, 2)
        self.tomorrow()
        self.assertEqual(self.run_cli('send')[0], 0)
        self.assertEqual(len(self.calls('issue', 'create')), 1)
        self.assertEqual(len(self.calls('issue', 'comment')), 1)

    def test_empty_or_single_word_body_file_explains_how_to_complete_file(self):
        path = self.repo / 'body.md'
        for mode in ('auto', 'draft'):
            for message in ('', ' \t\n', 'status \n'):
                with self.subTest(mode=mode, message=message):
                    path.write_text(message, encoding='utf-8')
                    code, out, err = self.run_cli('--body-file', str(path), mode=mode)
                    self.assertEqual(code, 2)
                    self.assertEqual(out, '')
                    self.assertIn('본문 파일이 비었거나 한 단어입니다.', err)
                    self.assertIn('파일에 증상·근거·제안을 채워 --body-file로 다시 보내세요.', err)
                    self.assertNotIn('subcommand', err)
                    self.assertNotIn('gs feedback "문장"', err)
        self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        self.assertEqual(self.calls(), [])

    def test_body_file_errors_and_off_leave_no_draft(self):
        path = self.repo / 'body.md'
        # off는 파일 읽기도 하지 않는다.
        code, _, err = self.run_cli('--body-file', str(path), mode='off')
        self.assertEqual(code, 1)
        self.assertIn('off', err)
        self.assertEqual(self.run_cli('--body-file', str(path))[0], 1)
        path.write_bytes(b'\xff')
        self.assertEqual(self.run_cli('--body-file', str(path))[0], 1)
        for message in ('', 'status \n', '본문 글\n' + feedback.LOCAL_MARKER):
            path.write_text(message, encoding='utf-8')
            self.assertNotEqual(self.run_cli('--body-file', str(path))[0], 0)
        path.write_text('본문 글', encoding='utf-8')
        for arg in ('send', 'status', '다른 글'):
            self.assertEqual(self.run_cli(arg, '--body-file', str(path))[0], 2)
        with mock.patch.dict(os.environ, {'GS_ROLE': 'worker'}):
            self.assertEqual(self.run_cli('--body-file', str(path))[0], 1)
        self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        self.assertEqual(self.calls(), [])

    def test_feedback_help_documents_body_file(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as result:
            cli.main(['feedback', '--help'])
        self.assertEqual(result.exception.code, 0)
        self.assertIn('--body-file', out.getvalue())

    def test_manual_cli_failure_guidance_matches_mode_and_preserves_draft(self):
        for mode in ('auto', 'draft'):
            for failure in ('list', 'create', 'missing'):
                with self.subTest(mode=mode, failure=failure):
                    message = f'{mode} {failure} 전송 실패'
                    with mock.patch.dict(os.environ, {
                        'FAKE_FAIL': failure,
                        'GS_GH': '/no/such/gh' if failure == 'missing' else str(self.fake),
                    }):
                        code, out, err = self.run_cli(message, mode=mode)
                    self.assertEqual((code, out), (0, 'gs feedback: 0건 전송\n'))
                    self.assertEqual(len(err.splitlines()), 1)
                    self.assertNotIn('secret auth failure', err)
                    if mode == 'draft':
                        self.assertIn('gs feedback send', err)
                        self.assertNotIn('다음 실행', err)
                    else:
                        self.assertIn('다음 실행 때 다시 보냅니다', err)
                    drafts = [feedback.read_draft(p, self.cfg)
                              for p in (self.repo / feedback.FEEDBACK_DIR).glob('*.md')]
                    draft, = [d for d in drafts if message in d.body]
                    self.assertNotIn('sent_count', draft.meta)

    def test_manual_cli_sends_verbatim_text_and_environment_in_draft_mode(self):
        message = '진행 요약에 기다린 시간도 보여 주세요 $(touch nope)'
        self.assertEqual(self.run_cli(message), (0, 'gs feedback: 1건 전송\n', ''))
        body = self.calls('issue', 'create')[0]
        body = body[body.index('--body') + 1]
        self.assertIn(message, body)
        for field in ('gs', 'CLI', 'OS', '단계', 'config', '지문', '횟수'):
            self.assertIn('- ' + field + ':', body)
        self.assertFalse((self.repo / 'nope').exists())
        self.assertIn('sent 1/1', self.run_cli('list')[1])

    def test_manual_cli_only_sends_its_own_draft_with_one_slot_left(self):
        automatic = self.record()
        before = automatic.read_bytes()
        # 자동 초안이 정렬상 앞서도 수동 글의 한도를 먼저 쓰지 못한다.
        (automatic.parent / '00.md').write_bytes(before)
        (automatic.parent / '.send-state.json').write_text(json.dumps({
            'day': real_date.today().isoformat(), 'count': 4, 'issues': {}}))
        self.assertEqual(self.run_cli('사람의 제안'), (0, 'gs feedback: 1건 전송\n', ''))
        create, = self.calls('issue', 'create')
        self.assertIn('사람의 제안', create[create.index('--body') + 1])
        self.assertEqual(automatic.read_bytes(), before)
        self.assertEqual((automatic.parent / '00.md').read_bytes(), before)

    def test_worker_cannot_queue_manual_feedback_even_with_explicit_repo(self):
        with mock.patch.dict(os.environ, {'GS_ROLE': 'worker'}):
            for mode in ('auto', 'draft'):
                code, _, err = self.run_cli('모델이 쓴 글', mode=mode)
                self.assertEqual(code, 1)
                self.assertIn('worker', err)
            with self.assertRaisesRegex(ValueError, 'worker'):
                feedback.record_manual(self.repo, self.cfg, '모델이 쓴 글')
        self.assertFalse((self.repo / feedback.FEEDBACK_DIR).exists())
        self.assertEqual(self.calls(), [])

    def test_cli_send_forces_drafts_and_off_explains_refusal(self):
        self.record()
        self.assertEqual(self.run_cli('send'), (0, 'gs feedback: 1건 전송\n', ''))
        self.assertEqual(self.run_cli('send'), (0, 'gs feedback: 0건 전송\n', ''))
        before = len(self.calls())
        for args in (('글',), ('send',)):
            code, _, err = self.run_cli(*args, mode='off')
            self.assertEqual(code, 1)
            self.assertIn('off', err)
        self.assertEqual(len(self.calls()), before)

    def test_manual_messages_have_distinct_fingerprints_and_repeated_text_bumps(self):
        a = feedback.record_manual(self.repo, self.cfg, '첫 제안')
        b = feedback.record_manual(self.repo, self.cfg, '다른 제안')
        self.assertNotEqual(a, b)
        self.assertEqual(feedback.record_manual(self.repo, self.cfg, '첫 제안'), a)
        self.assertEqual(feedback.read_draft(a, self.cfg).count, 2)


if __name__ == '__main__':
    unittest.main()
