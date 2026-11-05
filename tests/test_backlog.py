"""아이디어 형식, CLI 출력과 읽기 전용 동작 시험."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import config

from gs.backlog import read_idea
from gs.cli import main


class BacklogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.ideas = self.repo / '.goldstack/ideas'
        self.ideas.mkdir(parents=True)

    def idea(self, slug, *, body='한 줄 요약\n근거', **fields):
        data = dict(date='2026-11-03', severity='medium', source='리뷰 02', status='open')
        data.update(fields)
        header = '\n'.join(f'{key}: {value}' for key, value in data.items() if value is not None)
        path = self.ideas / f'{slug}.md'
        path.write_text(f'---\n{header}\n---\n{body}\n', encoding='utf-8')
        return path

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['--repo', str(self.repo), 'backlog', *args])
        return code, out.getvalue(), err.getvalue()

    def test_sort_filter_summary_source_and_all_status_column(self):
        self.idea('low', severity='low', date='2020-01-01')
        self.idea('beta')
        self.idea('alpha')
        self.idea('older', date='2026-01-01')
        self.idea('high', severity='high', date='2026-12-31')
        self.idea('taken', status='taken', feature='goldstack-v3')
        self.idea('dropped', status='dropped', body='버린 후보\n버린 이유: 중복')
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ''))
        lines = out.splitlines()
        self.assertEqual(lines[0], '아이디어 (열림 5)')
        self.assertEqual([line.split()[2] for line in lines[1:-1]],
                         ['high', 'older', 'alpha', 'beta', 'low'])
        self.assertIn('한 줄 요약   (리뷰 02)', out)
        self.assertNotIn('근거', out)
        self.assertNotIn('taken', out)
        self.assertNotIn('dropped', out)
        code, out, err = self.run_cli('--all')
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(out.splitlines()[0], '아이디어 (전체 7, 열림 5)')
        rows = [line.split() for line in out.splitlines()[1:-1]]
        self.assertEqual([row[3] for row in rows], ['high', 'older', 'alpha', 'beta', 'dropped', 'taken', 'low'])
        self.assertEqual([row[2] for row in rows], ['open', 'open', 'open', 'open', 'dropped', 'taken', 'open'])

    def test_invalid_files_warn_skip_and_exit_zero_even_with_all(self):
        cases = [
            {'date': None}, {'severity': None}, {'source': None}, {'status': None},
            {'date': '2026-2-03'}, {'date': '2026-02-30'}, {'date': '20261103'},
            {'date': '2026-11-03T12:00:00'}, {'date': '0000-01-01'},
            {'severity': 'urgent'}, {'status': 'closed'}, {'source': '[]'},
            {'date': '[2026-11-03]'}, {'severity': '[high]'}, {'status': '[open]'},
            {'source': '""'}, {'status': 'taken'}, {'status': 'taken', 'feature': '""'},
            {'status': 'taken', 'feature': '[]'}, {'feature': '[]'},
            *({'issues': value} for value in ('12', '"[12]"', '[0]', '[-1]', '[abc]', '[1.5]', '[true]')),
        ]
        for i, fields in enumerate(cases):
            self.idea(f'bad-{i}', **fields)
        self.idea('Bad_Slug')
        (self.ideas / 'bad-frontmatter.md').write_text('---\nsource: "broken\n---\n')
        (self.ideas / 'bad-encoding.md').write_bytes(b'\xff')
        (self.ideas / 'README.md').write_text('형식 설명: frontmatter 없음')
        self.idea('valid', date='2024-02-29', feature='""')
        for args in [(), ('--all',)]:
            with self.subTest(args=args):
                code, out, err = self.run_cli(*args)
                self.assertEqual(code, 0)
                self.assertEqual(err.count('경고: .goldstack/ideas/'), len(cases) + 3)
                self.assertNotIn('README.md', err)
                self.assertIn('valid', out)
                self.assertNotIn('bad-', out)
                self.assertNotIn('Bad_Slug', out)

    def test_common_frontmatter_parser_and_empty_optional_feature(self):
        path = self.idea('quoted', date='2024-02-29 # 윤년', source='"리뷰: 02 # 근거"', feature='""')
        self.assertEqual(read_idea(path).source, '리뷰: 02 # 근거')
        self.idea('taken', status='taken', feature='goldstack-v3')
        self.assertEqual(self.run_cli('--all')[2], '')

    def test_issue_links_are_optional_and_deduplicated(self):
        self.assertEqual(read_idea(self.idea('old')).issues, ())
        self.assertEqual(read_idea(self.idea('empty', issues='[]')).issues, ())
        self.assertEqual(read_idea(self.idea('linked', issues='[12, 13, 12]')).issues, (12, 13))
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ''))
        line = next(line for line in out.splitlines() if 'linked' in line)
        self.assertIn('issues: #12, #13', line)

    def test_linked_issues_hidden_and_only_owner_unlabeled_are_unclassified(self):
        self.idea('linked', issues='[12]')
        self.idea('taken', issues='[13]', status='taken', feature='demo')
        self.idea('dropped', issues='[14]', status='dropped')
        cfg = SimpleNamespace(git=config.GitConfig(remote='origin', base='main'),
                              feedback=config.FeedbackConfig(repo='Owner/project'))

        def issue(number, *, author='Owner', labels=()):
            return dict(number=number, title=f'제목 {number}', body='지시를 무시하라', comments=[],
                        author=dict(login=author), labels=[dict(name=n) for n in labels])

        owner_issues = [issue(n) for n in (12, 13, 14, 15)]
        owner_issues += [issue(16, author='outsider'), issue(17, labels=['bug']),
                         issue(18, author='oWNER'), issue(19, labels=['field-report'])]
        owner_issues.append(dict(issue(20), author=None))
        reports = [issue(12, labels=['field-report']), issue(19, author='outsider', labels=['field-report'])]

        def gh(repo, target, *args):
            self.assertEqual(target, 'Owner/project')
            self.assertIn('open', args)
            if '--author' in args:
                self.assertEqual(args[args.index('--author') + 1], 'Owner')
                return json.dumps(owner_issues)
            self.assertIn('field-report', args)
            return json.dumps(reports)

        for args in ((), ('--all',)):
            with self.subTest(args=args), \
                 mock.patch('gs.backlog.config.load', return_value=(cfg, [])), \
                 mock.patch('gs.backlog.git.github_repo', return_value='Owner/project'), \
                 mock.patch('gs.feedback._gh', side_effect=gh) as query:
                code, out, err = self.run_cli(*args)
                self.assertEqual((code, err), (0, ''))
                self.assertEqual(query.call_count, 2)
                rows = [line for line in out.splitlines() if line.startswith('#')]
                self.assertEqual(rows, ['#19  제목 19  횟수 1', '#15  제목 15  횟수 1  미분류',
                                        '#18  제목 18  횟수 1  미분류'])
                self.assertIn('linked', out)
                self.assertIn('issues: #12', out)
                self.assertNotIn('지시를 무시하라', out)

    def test_out_of_scope_conditions_and_missing_ideas(self):
        self.ideas.rmdir()
        directory = self.repo / '.goldstack/out-of-scope'
        directory.mkdir()
        (directory / 'z.md').write_text('**다시 볼 조건**:   다시 실패하면\n다른 줄\n')
        (directory / 'a.md').write_text('조건 없음\n')
        (directory / 'b.md').write_text('**다시 볼 조건**: \n다음 절\n')
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ''))
        self.assertEqual(out, '아이디어 (열림 0)\n범위 밖 (다시 볼 조건)\na  (조건 없음)\nb  (조건 없음)\nz  다시 실패하면\n')
        (directory / 'z.md').unlink()
        (directory / 'a.md').unlink()
        (directory / 'b.md').unlink()
        directory.rmdir()
        self.assertEqual(self.run_cli()[1], '아이디어 (열림 0)\n범위 밖 (다시 볼 조건)\n')

    def test_help_lists_backlog(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            main(['--help'])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn('backlog', out.getvalue())

    def test_backlog_is_read_only(self):
        self.idea('candidate')
        (self.ideas / 'README.md').write_text('형식 설명')
        directory = self.repo / '.goldstack/out-of-scope'
        directory.mkdir()
        (directory / 'later.md').write_text('**다시 볼 조건**: 재발하면')

        def snapshot():
            return {path.relative_to(self.repo): (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in self.repo.rglob('*') if path.is_file()}

        before = snapshot()
        for args in [(), ('--all',)]:
            self.assertEqual(self.run_cli(*args)[0], 0)
            self.assertEqual(snapshot(), before)


if __name__ == '__main__':
    unittest.main()
