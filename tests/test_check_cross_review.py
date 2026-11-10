import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import check, cli, config, git
from support import isolate_git_env

HEAD = "---\nfeature: demo\nverify: \"true\"\n---\n# demo\n\n## 7. grill 기록\n### 라운드 1 — 주제\n1. 질문 → 확정 A\n\n"
TABLE_HEAD = "| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |\n|---|---|---|---|---|\n"
PLACEHOLDER = "| 1 | <모델/effort> | <지적 한 줄> | <확인한 방법과 결과> | <반영함> |\n"
REAL = "| 1 | codex gpt-6.1-sol/high | 경계 누락 | 코드 확인, 맞다 | 반영함 |\n"
COMMENT = "<!-- 돌리지 못했으면 표 대신 한 줄 \"교차 검토 못 함: <이유>\"만 적는다 -->\n"
TICKET = '---\nid: "01"\ntitle: t\nblocked_by: []\nmodel: claude\nreviewer: codex\n---\n## 목표\n'
WARNING = "spec §7 교차 검토 기록이 없다"


class CrossReviewTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git.run(self.repo, "init", "-q")
        git.run(self.repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
        bin_dir = self.repo / "bin"
        bin_dir.mkdir()
        (bin_dir / "git").symlink_to(shutil.which("git"))
        for name in ("gh", "claude", "codex", "agy"):
            (bin_dir / name).write_text("#!/bin/sh\nexit 0\n")
            (bin_dir / name).chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PATH": str(bin_dir)})
        patch.start()
        self.addCleanup(patch.stop)
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        self.root = self.repo / ".goldstack/work/demo"
        (self.root / "tickets").mkdir(parents=True)

    def check(self, section, tickets=True, heading="### 교차 검토 (2026-11-10)\n", tail=""):
        (self.root / "spec.md").write_text(HEAD + heading + section + tail)
        if tickets:
            (self.root / "tickets/01-a.md").write_text(TICKET)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "demo"])
        self.assertEqual(code, 0, out.getvalue() + err.getvalue())
        return err.getvalue()

    def test_placeholder_row_only_warns(self):
        err = self.check(COMMENT + TABLE_HEAD + PLACEHOLDER)
        self.assertIn(f"경고: .goldstack/work/demo/spec.md: {WARNING}", err)
        self.assertIn('"교차 검토 못 함: <이유>"를 적는다', err)

    def test_real_row_is_silent(self):
        self.assertNotIn(WARNING, self.check(COMMENT + TABLE_HEAD + PLACEHOLDER + REAL))

    def test_row_with_empty_cells_warns(self):
        self.assertIn(WARNING, self.check(TABLE_HEAD + "| 1 | | | | |\n"))
        self.assertIn(WARNING, self.check(TABLE_HEAD + "| 1 | codex | 지적 | | 반영함 |\n"))

    def test_escaped_pipe_is_cell_text_not_separator(self):
        self.assertIn(WARNING, self.check(TABLE_HEAD + "| 1 | codex | a \\| b 오류 | 코드 확인 | |\n"))
        self.assertNotIn(WARNING, self.check(TABLE_HEAD + "| 1 | codex | a \\| b 오류 | 코드 확인 | 반영함 |\n"))

    def test_skip_line_is_silent(self):
        self.assertNotIn(WARNING, self.check("교차 검토 못 함: codex 한도\n"))

    def test_skip_line_only_in_comment_warns(self):
        self.assertIn(WARNING, self.check(COMMENT + TABLE_HEAD + PLACEHOLDER))

    def test_row_only_in_comment_warns(self):
        self.assertIn(WARNING, self.check(f"<!--\n{REAL}-->\n" + TABLE_HEAD))

    def test_no_heading_is_silent(self):
        (self.root / "spec.md").write_text(HEAD + "교차 검토를 했다.\n")
        (self.root / "tickets/01-a.md").write_text(TICKET)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["--repo", str(self.repo), "check", "demo"]), 0)
        self.assertNotIn(WARNING, err.getvalue())

    def test_no_tickets_is_silent(self):
        feat_text = HEAD + "### 교차 검토\n" + TABLE_HEAD + PLACEHOLDER
        (self.root / "spec.md").write_text(feat_text)
        from gs import feature as featmod
        feat = featmod.load(self.repo, "demo")
        self.assertEqual(feat.tickets, {})
        self.assertEqual(check.cross_review_problems(self.repo, feat), [])
        (self.root / "tickets/01-a.md").write_text(TICKET)
        self.assertEqual(len(check.cross_review_problems(self.repo, featmod.load(self.repo, "demo"))), 1)

    def test_real_row_in_next_section_warns(self):
        err = self.check(TABLE_HEAD + PLACEHOLDER, tail="\n### 다음 절\n" + TABLE_HEAD + REAL)
        self.assertIn(WARNING, err)
        err = self.check(TABLE_HEAD + PLACEHOLDER, tail="\n## 8. 끝\n교차 검토 못 함: 늦게 적음\n")
        self.assertIn(WARNING, err)

    def test_subheading_does_not_end_section(self):
        self.assertNotIn(WARNING, self.check("#### 세부\n" + TABLE_HEAD + REAL))


if __name__ == "__main__":
    unittest.main()
