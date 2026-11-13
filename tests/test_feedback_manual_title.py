"""수동 피드백 제목은 사람이 쓴 본문을 요약한다."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import isolate_git_env
from gs import config, feedback


class ManualFeedbackTitleTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.cfg = config.Config(config.GitConfig('origin', 'main'), config.ModelsConfig('o', 'o', 'a', ''),
                                 config.TimeoutsConfig(30, 10, 60), config.NotifyConfig(False),
                                 feedback=config.FeedbackConfig('draft', 'errors', 'owner/inbox', 5))
        self.env = feedback.Environment('9.9.9', 'Linux 6.0 x86_64')
        patcher = mock.patch('gs.feedback.environment', return_value=self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('GS_ROLE', None)

    def title(self, message):
        path = feedback.record_manual(self.repo, self.cfg, message)
        return feedback.read_draft(path, self.cfg).title

    def test_manual_titles_use_the_first_heading_and_differ(self):
        first = self.title('# 첫 기능 제안\n내용 하나')
        second = self.title('# 다른 기능 제안\n내용 둘')
        self.assertEqual(first, '[field] 첫 기능 제안 (gs 9.9.9)')
        self.assertEqual(second, '[field] 다른 기능 제안 (gs 9.9.9)')
        self.assertNotEqual(first, second)

    def test_without_heading_uses_first_nonempty_line(self):
        self.assertEqual(self.title('\n  첫 내용 줄  \n다음 줄'), '[field] 첫 내용 줄 (gs 9.9.9)')

    def test_manual_title_skips_subheadings_and_fenced_code(self):
        self.assertEqual(self.title('## 증상\n\nworker가 멈춘다'), '[field] worker가 멈춘다 (gs 9.9.9)')
        self.assertEqual(self.title('설명\n```python\n# 주석\n```\n다음'),
                         '[field] 설명 (gs 9.9.9)')
        self.assertEqual(self.title('~~~\n# 주석\n~~~\n본문'), '[field] 본문 (gs 9.9.9)')
        self.assertEqual(self.title('## 증상\n# 제목\n본문'), '[field] 제목 (gs 9.9.9)')

    def test_manual_title_falls_back_when_no_body_line_exists(self):
        for message in ('## 증상\n### 재현', '```\n본문\n```', '~~~\n# 제목\n~~~', '# '):
            with self.subTest(message=message):
                self.assertEqual(self.title(message), '[field] 수동 피드백 (gs 9.9.9)')

    def test_title_is_limited_to_eighty_characters(self):
        title = self.title('# ' + '가' * 81)
        self.assertEqual(title, '[field] ' + '가' * 79 + '… (gs 9.9.9)')

    def test_korean_title_is_not_redacted(self):
        self.assertEqual(self.title('# 설정이 꼬여서 한글 제목을 그대로 보여 주세요'),
                         '[field] 설정이 꼬여서 한글 제목을 그대로 보여 주세요 (gs 9.9.9)')

    def test_title_contains_no_line_breaks_or_control_characters(self):
        title = self.title('# 한 줄\t제목\x00 끝\n본문')
        self.assertEqual(title, '[field] 한 줄 제목 끝 (gs 9.9.9)')
        self.assertFalse(any(ord(char) < 32 or 127 <= ord(char) < 160 for char in title))

    def test_automatic_compose_title_keeps_phase_and_kind(self):
        issue = feedback.compose(phase='verify', kind='GitError', frames=[], error_lines=[], cfg=self.cfg,
                                 redactor=feedback.Redactor(), env=self.env)
        self.assertEqual(issue.title, '[field] verify: GitError (gs 9.9.9)')


if __name__ == '__main__':
    unittest.main()
