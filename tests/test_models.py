"""실제 홈·CLI 없이 머신 모델 목록과 config 칸을 대조한다."""
import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import config, models


class ModelsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = self.root / "models_cache.json"
        self.agy = self.root / "fake-agy"
        patch = mock.patch.dict(os.environ, CODEX_HOME=str(self.root), GS_AGY=str(self.agy))
        patch.start()
        self.addCleanup(patch.stop)

    def fake_agy(self, body):
        self.agy.write_text(f"#!{sys.executable}\nimport sys\nassert sys.argv[1:] == ['models']\n" + body)
        self.agy.chmod(0o755)

    def test_codex_cache_and_empty_list(self):
        self.cache.write_text(json.dumps({"models": [{"slug": "one"}, {"slug": "two", "extra": 1}, {"slug": "one"}]}))
        self.assertEqual(models.codex_models(), {"one", "two"})
        self.cache.write_text('{"models": []}')
        self.assertEqual(models.codex_models(), set())

    def test_codex_absent_broken_and_wrong_format_are_unknown(self):
        self.assertIsNone(models.codex_models())
        for value in (b"{", b"\xff", b"[]", b"null", b"{}", b'{"models": {}}',
                      b'{"models": [null]}', b'{"models": [{}]}', b'{"models": [{"slug": 7}]}',
                      b'{"models": [{"slug": " "}]}', b'{"models": [{"slug": "ok"}, {}]}'):
            with self.subTest(value=value):
                self.cache.write_bytes(value)
                self.assertIsNone(models.codex_models())
        self.cache.unlink()
        self.cache.mkdir()
        self.assertIsNone(models.codex_models())

    def test_codex_defaults_to_dot_codex_only_without_override(self):
        home = self.root / "home"
        (home / ".codex").mkdir(parents=True)
        (home / ".codex/models_cache.json").write_text('{"models": [{"slug": "home-model"}]}')
        with mock.patch.dict(os.environ, HOME=str(home)):
            self.assertIsNone(models.codex_models())  # 지정한 CODEX_HOME에는 캐시가 없다.
            del os.environ["CODEX_HOME"]
            self.assertEqual(models.codex_models(), {"home-model"})

    def test_agy_first_column_and_empty_output(self):
        self.fake_agy("print('  gemini-one    description\\n\\ngemini-two\\tother\\ngemini-one repeated')\n")
        self.assertEqual(models.agy_models(5), {"gemini-one", "gemini-two"})
        self.fake_agy("pass\n")
        self.assertEqual(models.agy_models(5), set())

    def test_agy_sign_in_stdout_or_stderr_and_failure_are_unknown(self):
        for body in ("print('Please sign in to view available models')\n",
                     "print('gemini-one'); print('Please sign in', file=sys.stderr)\n",
                     "print('gemini-one'); sys.exit(2)\n"):
            with self.subTest(body=body):
                self.fake_agy(body)
                self.assertIsNone(models.agy_models(5))

    def test_agy_missing_executable_and_timeout_are_unknown(self):
        self.assertIsNone(models.agy_models(5))
        with mock.patch("gs.models.subprocess.run", side_effect=subprocess.TimeoutExpired("agy", 7)) as run:
            self.assertIsNone(models.agy_models(7))
        self.assertEqual(run.call_args.args[0], [str(self.agy), "models"])
        self.assertEqual(run.call_args.kwargs["timeout"], 7)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def cfg(self):
        return config.Config(config.GitConfig("origin", "main"),
                             config.ModelsConfig("judge", "review", "agy-one/high", "codex-one/medium"),
                             config.TimeoutsConfig(1, 1, 1), config.NotifyConfig(False),
                             tiers=config.TiersConfig(
                                 codex={"small": config.ModelEffort("codex-one", "high"),
                                        "medium": config.ModelEffort(""),
                                        "large": config.ModelEffort("codex-two", "xhigh")},
                                 agy={"large": config.ModelEffort("agy-two")}))

    def test_missing_checks_each_family_cell_and_strips_effort(self):
        cfg = self.cfg()
        self.assertEqual(models.missing(cfg, "codex", {"codex-one"}), [("tiers.codex.large", "codex-two")])
        self.assertEqual(models.missing(cfg, "codex", set()), [
            ("models.codex", "codex-one"), ("tiers.codex.small", "codex-one"), ("tiers.codex.large", "codex-two")])
        self.assertEqual(models.missing(cfg, "agy", {"agy-two"}), [("models.agy", "agy-one")])
        self.assertEqual(models.missing(cfg, "agy", {"agy-one", "agy-two"}), [])
        self.assertEqual(models.missing(cfg, "codex", None), [])
        self.assertEqual(models.missing(cfg, "claude", set()), [])
        cfg = dataclasses.replace(cfg, models=dataclasses.replace(cfg.models, codex="  "), tiers=config.TiersConfig())
        self.assertEqual(models.missing(cfg, "codex", set()), [])

    def test_doctor_omits_unconfigured_families_without_query(self):
        cfg = self.cfg()
        cfg = dataclasses.replace(cfg, models=dataclasses.replace(cfg.models, codex="", agy=""),
                                  tiers=config.TiersConfig())
        with mock.patch("gs.models._codex_inventory") as codex, mock.patch("gs.models._agy_inventory") as agy:
            self.assertEqual(models.doctor_rows(cfg), [])
        codex.assert_not_called()
        agy.assert_not_called()

    def test_doctor_timeout_reason(self):
        with mock.patch("gs.models.subprocess.run", side_effect=subprocess.TimeoutExpired("agy", 15)):
            self.assertIn("agy: 확인 못 함(agy models 시간 초과)", models.doctor_rows(self.cfg()))


if __name__ == "__main__":
    unittest.main()
