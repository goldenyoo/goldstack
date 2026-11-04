"""spec §6 출력으로 일시 오류를 판별한다. 실제 API·모델 호출은 하지 않는다."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, config, transient


def log(*events):
    return "\n".join(e if isinstance(e, str) else json.dumps(e) for e in events)


def claude(**fields):
    return {"type": "result", "subtype": "error_during_execution", "is_error": True, **fields}


def codex(message):
    return {"type": "error", "message": message}


MODEL = "gemini-4-argon-high"
INVALID_MODEL = (f'Error: invalid model selection (--model "{MODEL}" ...): '
                 f'model "{MODEL}" is not recognized')


class StructuredErrorsTest(unittest.TestCase):
    def test_claude_connection_failed_from_spec(self):
        for subtype in ("success", "error_during_execution"):
            with self.subTest(subtype=subtype):
                text = log({"type": "system", "subtype": "api_retry", "attempt": 1, "max_retries": 9},
                           claude(subtype=subtype, api_error="connection_failed", terminal_reason="api_error",
                                  result="API Error: Connection refused (ECONNREFUSED)"))
                self.assertTrue(transient.reason("claude", text))

    def test_connection_failure_phrases(self):
        for message in ("failed to connect to server", "unable to connect to server",
                        "could not connect to server"):
            for family, event in (("claude", claude(errors=[message])), ("codex", codex(message)),
                                  ("agy", {"event": "error", "message": message})):
                with self.subTest(family=family, message=message):
                    self.assertTrue(transient.reason(family, log(event)))

    def test_claude_only_last_result_counts(self):
        error = claude(api_error="connection_failed", terminal_reason="api_error")
        success = {"type": "result", "subtype": "success", "is_error": False, "result": "done"}
        self.assertEqual(transient.reason("claude", log(error, success)), "")
        self.assertTrue(transient.reason("claude", log(success, error)))
        self.assertEqual(transient.reason("claude", log(error, claude(errors=["test failed"]))), "")

    def test_claude_does_not_search_tool_output_or_success_response(self):
        text = log({"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "test output: ECONNREFUSED HTTP 503"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "ENOTFOUND"}]}},
            {"type": "result", "subtype": "success", "is_error": False,
             "result": "Tests cover API Error: 503 and ECONNREFUSED"})
        self.assertEqual(transient.reason("claude", text), "")
        self.assertEqual(transient.reason("claude", log({"type": "result", "result": "ECONNREFUSED"})), "")

    def test_claude_retry_event_without_result_is_not_enough(self):
        self.assertEqual(transient.reason("claude", log(
            {"type": "system", "subtype": "api_retry", "error": "ECONNREFUSED"})), "")

    def test_http_statuses_and_dns(self):
        for family in ("claude", "codex", "agy"):
            for status in (429, 500, 502, 503, 504, 599):
                with self.subTest(family=family, status=status):
                    payload = {"error": {"status_code": status, "message": "API failed"}}
                    event = (claude(**payload) if family == "claude" else
                             {"type": "error", **payload} if family == "codex" else
                             {"event": "error", **payload})
                    self.assertEqual(transient.reason(family, log(event)), f"HTTP {status}")
            for message in ("API Error: 503 unavailable", "HTTP 429", "status code: 502",
                            "429 Too Many Requests", "503 Service Unavailable", "getaddrinfo ENOTFOUND api",
                            "temporary failure in name resolution", "DNS resolution failed"):
                with self.subTest(family=family, message=message):
                    event = (claude(errors=[message]) if family == "claude" else codex(message)
                             if family == "codex" else {"event": "error", "message": message})
                    self.assertTrue(transient.reason(family, log(event)))

    def test_codex_network_messages_from_spec(self):
        for message in ("Reconnecting... waiting for network (Connection failed: offline)",
                        "stream disconnected before completion", "error sending request for url (https://api)"):
            with self.subTest(message=message):
                self.assertTrue(transient.reason("codex", log(codex(message))))
                self.assertTrue(transient.reason("codex", log(
                    {"type": "turn.failed", "error": {"message": message}})))

    def test_codex_does_not_search_item_outputs(self):
        for item_type in ("command_execution", "agent_message"):
            text = log({"type": "item.completed", "item": {"type": item_type,
                "aggregated_output": "error sending request", "text": "Reconnecting... waiting for network",
                "exit_code": 1}}, {"type": "turn.completed"})
            self.assertEqual(transient.reason("codex", text), "")

    def test_codex_recovered_or_replaced_error_is_not_transient(self):
        error = codex("stream disconnected before completion")
        self.assertEqual(transient.reason("codex", log(error, {"type": "turn.completed"})), "")
        self.assertEqual(transient.reason("codex", log(error, codex("invalid config"))), "")

    def test_agy_connection_errors_and_result(self):
        for message in ("Error: Connection refused (ECONNREFUSED)", "Connection failed: offline",
                        "Error: error sending request", "Error: DNS lookup failed"):
            with self.subTest(message=message):
                self.assertTrue(transient.reason("agy", message))
                self.assertTrue(transient.reason("agy", log({"event": "error", "message": message})))
                self.assertTrue(transient.reason("agy", log({"event": "result", "result": {
                    "status": "ERROR", "error": {"message": message}}})))

    def test_agy_does_not_search_step_outputs_or_model_response(self):
        with mock.patch.object(transient.subprocess, "run") as run:
            for status in ("SUCCESS", "ERROR"):
                text = log({"event": "step_update", "step_update": {"state": "ERROR",
                    "tool_info": {"error": {"message": "ECONNREFUSED"}}}},
                    {"event": "result", "result": {"status": status,
                        "response": INVALID_MODEL + " ECONNREFUSED"}})
                self.assertEqual(transient.reason("agy", text, model=MODEL), "")
            run.assert_not_called()

    def test_limits_auth_and_ordinary_failures_are_not_transient(self):
        messages = ("You've hit your limit · resets tomorrow", "usage_limit_reached",
                    "subscription usage limit reached", "API Error: 429 insufficient_quota",
                    "API Error: 401 authentication_error", "HTTP 403 unauthorized",
                    "invalid_api_key", "test failed", "exit code 1", "unknown API error", "HTTP 400")
        for message in messages:
            for family, event in (("claude", claude(errors=[message])), ("codex", codex(message)),
                                  ("agy", {"event": "error", "message": message})):
                with self.subTest(family=family, message=message):
                    self.assertEqual(transient.reason(family, log(event)), "")

    def test_auth_wins_over_connection_words_and_429(self):
        for event in (codex("unauthorized: error sending request HTTP 429"),
                      {"type": "error", "error": {"status_code": 401, "message": "ECONNREFUSED"}}):
            self.assertEqual(transient.reason("codex", log(event)), "")

    def test_empty_malformed_unknown_and_plain_work_output(self):
        for family in ("claude", "codex", "agy", "custom", "unknown"):
            for text in ("", "[1]", "null", '{"type":', "exit code 1", "test output ECONNREFUSED"):
                with self.subTest(family=family, text=text):
                    self.assertEqual(transient.reason(family, text), "")


class AgyModelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = self.root / "fake agy"
        patch = mock.patch.dict(os.environ, {"GS_AGY": str(self.binary)})
        patch.start()
        self.addCleanup(patch.stop)

    def fake_agy(self, stdout="", stderr="", code=0):
        # 인자·cwd·stdin도 실제 프로세스로 확인한다.
        self.binary.write_text("#!/usr/bin/env python3\nimport os, sys\n"
            "assert sys.argv[1:] == ['models']\nassert sys.stdin.read() == ''\n"
            f"assert os.getcwd() == {str(self.root.resolve())!r}\n"
            f"print({stdout!r})\nprint({stderr!r}, file=sys.stderr)\nsys.exit({code})\n")
        self.binary.chmod(0o755)

    def reason(self):
        return transient.reason("agy", INVALID_MODEL, model=MODEL, cwd=self.root)

    def test_failed_model_lookup_is_transient(self):
        for error in ("Error: timed out waiting for available models", "Error: model service unavailable"):
            with self.subTest(error=error):
                self.fake_agy(stderr=error, code=1)
                self.assertTrue(self.reason())

    def test_existing_model_selection_failure_is_transient(self):
        self.fake_agy(stdout=f"Available models:\n{MODEL}\tGemini Argon\ngemini-4-argon-medium")
        self.assertTrue(self.reason())
        self.assertTrue(transient.reason("agy", INVALID_MODEL, cwd=self.root))  # --model에서도 읽는다

    def test_unknown_model_is_configuration_error(self):
        for stdout in ("gemini-4-argon-medium", MODEL + "-other", "prefix-" + MODEL, ""):
            with self.subTest(stdout=stdout):
                self.fake_agy(stdout=stdout)
                self.assertEqual(self.reason(), "")

    def test_model_lookup_is_bounded(self):
        self.binary.write_text("#!/bin/sh\nexec sleep 5\n")
        self.binary.chmod(0o755)
        with mock.patch.object(transient, "AGY_MODELS_TIMEOUT", 0.05):
            self.assertTrue(self.reason())

    def test_missing_cli_and_auth_failure_are_not_network_errors(self):
        self.assertEqual(self.reason(), "")
        self.fake_agy(stderr="Error: authentication failed", code=1)
        self.assertEqual(self.reason(), "")

    def test_no_model_probe_for_other_errors(self):
        with mock.patch.object(transient.subprocess, "run") as run:
            for text in ("Error: test failed", "Error: invalid_api_key", "Error: usage_limit_reached"):
                self.assertEqual(transient.reason("agy", text, model=MODEL), "")
            run.assert_not_called()


class AdapterTransientTest(unittest.TestCase):
    def test_adapter_reads_log_and_preserves_outcome(self):
        models = config.ModelsConfig("judge", "review", MODEL, "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = adapters.WorkerInput(root / "brief", root, root / "worker.log")
            for family, event in (("claude", claude(api_error="connection_failed", terminal_reason="api_error")),
                                  ("codex", codex("Reconnecting... waiting for network")),
                                  ("agy", {"event": "result", "result": {
                                      "status": "ERROR", "error": "ECONNREFUSED"}})):
                with self.subTest(family=family):
                    adapter = adapters.ADAPTERS[family](models)
                    self.assertEqual(adapter.transient_reason(inp), "")
                    inp.log.write_text(log(event))
                    before = adapter.outcome(1, inp)
                    self.assertTrue(adapter.transient_reason(inp))
                    self.assertEqual(adapter.outcome(1, inp), before)
                    inp.log.unlink()

    def test_agy_adapter_passes_model_and_worktree(self):
        models = config.ModelsConfig("judge", "review", MODEL, "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = adapters.WorkerInput(root / "brief", root, root / "worker.log")
            inp.log.write_text(INVALID_MODEL)
            with mock.patch.object(transient.subprocess, "run", return_value=subprocess.CompletedProcess(
                    ["agy", "models"], 0, MODEL, "")) as run:
                self.assertTrue(adapters.Agy(models).transient_reason(inp))
                self.assertEqual(run.call_args.kwargs["cwd"], root)
                self.assertEqual(run.call_args.kwargs["timeout"], transient.AGY_MODELS_TIMEOUT)

    def test_custom_adapter_has_no_cli_error_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = adapters.WorkerInput(root / "brief", root, root / "worker.log")
            inp.log.write_text(log(codex("error sending request")))
            self.assertEqual(adapters.Custom("false").transient_reason(inp), "")


if __name__ == "__main__":
    unittest.main()
