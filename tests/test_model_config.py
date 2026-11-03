"""설정 파일을 바꾸면 실제 모델 인자와 subprocess 시간 제한이 바뀐다."""
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import adapters, config, failure, report, review


class ModelConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / ".goldstack").mkdir()
        self.path = self.repo / config.CONFIG_PATH
        self.inp = adapters.WorkerInput(self.repo / "brief.md", self.repo, self.repo / "worker.log")
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("GS_WORKER_CMD", "GS_REVIEWER_CMD", "GS_AGY"):
            os.environ.pop(name, None)

    def configured(self, suffix, codex=None):
        self.path.write_text(f'''[git]
remote = "upstream"
base = "trunk"
[models]
judge = "judge-{suffix}"
claude_review = "review-{suffix}"
agy = "agy-{suffix}"
codex = "{codex if codex is not None else 'codex-' + str(suffix)}"
[timeouts]
review_minutes = {11 + suffix}
judge_minutes = {3 + suffix}
summary_seconds = {21 + suffix}
[notify]
telegram = false
''')
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        return cfg

    def assert_model(self, argv, model):
        self.assertEqual(argv[argv.index("--model") + 1], model)

    def test_worker_and_reviewer_models_follow_config(self):
        for value in (1, 2):
            cfg = self.configured(value)
            for family, expected in (("agy", cfg.models.agy), ("codex", cfg.models.codex)):
                with self.subTest(value=value, family=family), \
                        mock.patch.object(adapters.Codex, "writable_dirs", return_value=[]):
                    worker = adapters.for_model(family, cfg.models)
                    self.assert_model(shlex.split(worker.command(self.inp)), expected)
            for family, expected in (("claude", cfg.models.claude_review), ("agy", cfg.models.agy),
                                     ("codex", cfg.models.codex)):
                argv, _, _ = review.reviewer_argv(family, self.repo, "prompt", self.repo / "out", cfg.models)
                self.assert_model(argv, expected)

    def test_empty_codex_model_omits_flag_for_worker_and_reviewer(self):
        cfg = self.configured(1, codex="")
        with mock.patch.object(adapters.Codex, "writable_dirs", return_value=[]):
            self.assertNotIn("--model", shlex.split(adapters.for_model("codex", cfg.models).command(self.inp)))
        argv, _, _ = review.reviewer_argv("codex", self.repo, "prompt", self.repo / "out", cfg.models)
        self.assertNotIn("--model", argv)

    def test_review_and_classification_use_configured_models_and_timeouts(self):
        findings = '{"findings": [{"severity": "high", "location": "a", "claim": "bug", "evidence": "line"}]}'
        for value in (1, 2):
            cfg = self.configured(value)
            with mock.patch.object(review, "write_diff", return_value=("base", False)), \
                    mock.patch.object(review, "_env", return_value={}), \
                    mock.patch.object(review, "_call", side_effect=[findings, '{"decisions": []}']) as call:
                rec = review.run(repo=self.repo, worktree=self.repo, rdir=self.repo / "review", base="base",
                                 branch="ticket", ticket=self.repo / "ticket", spec=self.repo / "spec",
                                 model="codex", reviewer="claude", cfg=cfg)
            self.assertEqual(rec["note"], "")
            reviewer, judge = call.call_args_list
            self.assert_model(reviewer.args[0], cfg.models.claude_review)
            self.assertEqual(reviewer.kwargs["timeout"], cfg.timeouts.review_minutes * 60)
            self.assert_model(judge.args[0], cfg.models.judge)
            self.assertEqual(judge.kwargs["timeout"], cfg.timeouts.judge_minutes * 60)

    def test_failure_summary_uses_configured_judge_and_seconds(self):
        for value in (1, 2):
            cfg = self.configured(value)
            with mock.patch.object(failure.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok")) as call:
                path = failure.summarize(self.repo, self.repo / "failure.log", cfg)
            self.assertIn("ok", path.read_text())
            self.assert_model(call.call_args.args[0], cfg.models.judge)
            self.assertEqual(call.call_args.kwargs["timeout"], cfg.timeouts.summary_seconds)

    def test_report_uses_configured_judge_and_minutes(self):
        for value in (1, 2):
            cfg = self.configured(value)
            r = SimpleNamespace(cfg=cfg, rundir=self.repo, iwt=self.repo, base_ref="upstream/trunk",
                                feat=SimpleNamespace(spec=SimpleNamespace(path=self.repo / "spec")),
                                st=SimpleNamespace(finish={}))
            with mock.patch.object(report, "evidence", return_value="facts"), \
                    mock.patch.object(report.git, "out", return_value="diff"), \
                    mock.patch.object(review, "_env", return_value={}), \
                    mock.patch.object(review, "_call", return_value="summary") as call:
                self.assertEqual(report.summarize(r), "summary")
            self.assert_model(call.call_args.args[0], cfg.models.judge)
            self.assertEqual(call.call_args.kwargs["timeout"], cfg.timeouts.judge_minutes * 60)
