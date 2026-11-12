"""검사 등록 유예와 보호 규칙에서 알게 된 필수 검사 이름의 게이트."""
import contextlib
import io
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

import test_config
from gs import config, finish


class ChecksGraceConfigTest(unittest.TestCase):
    setUp = test_config.ConfigTest.setUp
    def test_checks_grace_default_and_nonnegative_integer(self):
        self.assertEqual(config.load(self.repo)[0].timeouts.checks_grace_seconds, 60)
        original = self.path.read_text()
        for value in ("0", "3", "-1", "true", "1.5", '"60"'):
            with self.subTest(value=value):
                self.path.write_text(original.replace("[timeouts]", f"[timeouts]\nchecks_grace_seconds = {value}"))
                cfg, problems = config.load(self.repo)
                if value in ("0", "3"):
                    self.assertEqual(problems, [])
                    self.assertEqual(cfg.timeouts.checks_grace_seconds, int(value))
                else:
                    self.assertIsNone(cfg)
                    self.assertTrue(any("timeouts.checks_grace_seconds" in p.message for p in problems))


class ChecksGraceTest(unittest.TestCase):
    def poll(self, frames, *, required=(), grace=3):
        elapsed = [0]
        observed, queries = [], []
        r = SimpleNamespace(cfg=SimpleNamespace(git=config.GitConfig("origin", "main"),  # checks 없음: 보호 규칙 → gh 판정
                                                timeouts=SimpleNamespace(checks_minutes=1, checks_grace_seconds=grace)))

        def checks(r, **kwargs):
            queries.append(kwargs)
            frame = frames[min(len(observed), len(frames) - 1)]
            return [{"name": name, "bucket": bucket} for name, bucket in frame]

        def sleep(seconds):
            elapsed[0] += seconds

        with (mock.patch("gs.finish._required_checks", return_value=set(required)),
              mock.patch("gs.finish._checks", side_effect=checks),
              mock.patch("gs.finish._view", return_value={"state": "OPEN", "headRefOid": "head"}),
              mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)),
              contextlib.redirect_stdout(io.StringIO())):
            result = finish._poll_checks(r, "https://example.test/pr/1", "head", observed.append)
        return result, elapsed[0], observed, queries

    def test_late_checks_are_waited_until_completion(self):
        result, elapsed, observed, _ = self.poll([[], [("build", "pending")], [("build", "pass")]])
        self.assertEqual(result, ("pass", []))
        self.assertEqual(elapsed, 13)
        self.assertEqual(len(observed), 3)

    def test_no_checks_wait_exactly_grace(self):
        result, elapsed, _, _ = self.poll([[]])
        self.assertEqual(result, ("pass", []))
        self.assertEqual(elapsed, 3)

    def test_zero_grace_merges_without_sleep(self):
        result, elapsed, _, _ = self.poll([[]], grace=0)
        self.assertEqual((result, elapsed), (("pass", []), 0))

    def test_missing_required_names_wait_beyond_grace_and_ignore_optional_failure(self):
        result, elapsed, observed, queries = self.poll(
            [[("optional", "fail")], [("build", "pass")],
             [("build", "pass"), ("test", "pending")],
             [("build", "pass"), ("test", "pass"), ("optional", "fail")]],
            required=("build", "test"))
        self.assertEqual(result, ("pass", []))
        self.assertEqual(elapsed, 30)
        self.assertEqual(observed[0], [{"name": "build", "bucket": "pending"},
                                       {"name": "test", "bucket": "pending"}])
        self.assertTrue(all(not q["required"] for q in queries))

    def test_missing_required_check_times_out_even_with_zero_grace(self):
        result, elapsed, _, _ = self.poll([[('build', 'pass')]], required=("build", "test"), grace=0)
        self.assertEqual((result, elapsed), (("timeout", []), 60))

    def test_required_failure_blocks_merge(self):
        result, _, _, _ = self.poll([[("build", "fail"), ("optional", "pass")]], required=("build",))
        self.assertEqual(result, ("fail", ["build"]))

    def test_grace_cannot_exceed_overall_timeout(self):
        result, elapsed, _, _ = self.poll([[]], grace=120)
        self.assertEqual((result, elapsed), (("timeout", []), 60))

    def test_reads_classic_and_ruleset_required_names_for_configured_base(self):
        r = SimpleNamespace(repo="repo", remote="upstream", base="release/stable")
        responses = [
            '{"required_status_checks":{"contexts":["build"],"checks":[{"context":"test"}]}}',
            '[{"type":"required_status_checks","parameters":{"required_status_checks":[{"context":"lint"}]}}]',
        ]
        with (mock.patch("gs.finish.git.github_repo", return_value="owner/project") as repository,
              mock.patch("gs.finish.time.monotonic", return_value=0),
              mock.patch("gs.finish.subprocess.run", side_effect=[
                  subprocess.CompletedProcess([], 0, raw) for raw in responses]) as run):
            self.assertEqual(finish._required_checks(r, 5), {"build", "test", "lint"})
        repository.assert_called_once_with("repo", "upstream")
        self.assertEqual([c.args[0][2] for c in run.call_args_list], [
            "repos/owner/project/branches/release%2Fstable/protection",
            "repos/owner/project/rules/branches/release%2Fstable"])
        self.assertTrue(all(c.kwargs["timeout"] == 5 for c in run.call_args_list))

    def test_unknown_protection_falls_back_to_reported_checks(self):
        r = SimpleNamespace(repo="repo", remote="origin", base="main")
        with (mock.patch("gs.finish.git.github_repo", return_value="owner/project"),
              mock.patch("gs.finish.time.monotonic", return_value=0),
              mock.patch("gs.finish.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "403"))):
            self.assertEqual(finish._required_checks(r, 60), set())

    def test_partial_protection_does_not_return_incomplete_names(self):
        r = SimpleNamespace(repo="repo", remote="origin", base="main")
        responses = [
            subprocess.CompletedProcess([], 0, '{"required_status_checks":{"contexts":["build"]}}'),
            subprocess.CompletedProcess([], 0,
                '[{"type":"required_status_checks","parameters":{"required_status_checks":[{"context":"lint"}]}}]'),
        ]
        failures = [subprocess.CompletedProcess([], code, "", str(code)) for code in (403, 404, 502)]
        failures += [OSError("unavailable"), subprocess.TimeoutExpired(["gh", "api"], 20),
                     subprocess.CompletedProcess([], 0, "invalid JSON"),
                     subprocess.CompletedProcess([], 0, "null")]
        for endpoint in range(2):
            for failure in failures:
                with self.subTest(endpoint=endpoint, failure=failure):
                    partial = responses.copy()
                    partial[endpoint] = failure
                    with (mock.patch("gs.finish.git.github_repo", return_value="owner/project"),
                          mock.patch("gs.finish.time.monotonic", return_value=0),
                          mock.patch("gs.finish.subprocess.run", side_effect=partial)):
                        self.assertEqual(finish._required_checks(r, 60), set())

    def test_partial_protection_uses_gh_required_checks_to_gate_merge(self):
        r = SimpleNamespace(repo="repo", remote="origin", base="main",
                            cfg=SimpleNamespace(git=config.GitConfig("origin", "main"),
                                                timeouts=SimpleNamespace(checks_minutes=1, checks_grace_seconds=3)))
        for endpoint, unknown in ((0, "build"), (1, "lint")):
            for bucket in ("fail", "pending", "pass"):
                with self.subTest(endpoint=endpoint, bucket=bucket):
                    responses = [
                        subprocess.CompletedProcess([], 0, '{"required_status_checks":{"contexts":["build"]}}'),
                        subprocess.CompletedProcess([], 0,
                            '[{"type":"required_status_checks","parameters":{"required_status_checks":[{"context":"lint"}]}}]'),
                    ]
                    responses[endpoint] = subprocess.CompletedProcess([], 1, "", "403")
                    elapsed = [0]

                    def checks(r, *, required, **kwargs):
                        reported = [{"name": "build", "bucket": "pass"},
                                    {"name": "lint", "bucket": "pass"}]
                        for check in reported:
                            if check["name"] == unknown:
                                check["bucket"] = bucket if elapsed[0] == 0 else "pass"
                        return reported if required else reported + [{"name": "optional", "bucket": "fail"}]

                    def sleep(seconds):
                        elapsed[0] += seconds

                    with (mock.patch("gs.finish.git.github_repo", return_value="owner/project"),
                          mock.patch("gs.finish.subprocess.run", side_effect=responses),
                          mock.patch("gs.finish._checks", side_effect=checks) as query,
                          mock.patch("gs.finish._view", return_value={"state": "OPEN", "headRefOid": "head"}),
                          mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)),
                          contextlib.redirect_stdout(io.StringIO())):
                        result = finish._poll_checks(r, "https://example.test/pr/1", "head", lambda c: None)
                    self.assertEqual(result, ("fail", [unknown]) if bucket == "fail" else ("pass", []))
                    self.assertEqual(elapsed[0], 10 if bucket == "pending" else 0)
                    self.assertTrue(all(call.kwargs["required"] for call in query.call_args_list))
