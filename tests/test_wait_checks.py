"""최종 PR head의 CI 게이트와 실패·시간 초과 뒤 gs go 재개."""
import json
import subprocess
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import test_go
from gs import config, finish, go, state
from test_go import sh


CHECKS_GH = '''\
  "pr checks")
    [ -f "$here/checks.error" ] && { cat "$here/checks.error" >&2; exit 1; }
    mode=all
    for arg in "$@"; do [ "$arg" = --required ] && mode=required; done
    if [ -f "$here/checks.$mode" ]; then cat "$here/checks.$mode"
    elif [ "$mode" = required ]; then echo "no required checks reported on the 'gs/demo/integration' branch" >&2; exit 1
    else echo "no checks reported on the 'gs/demo/integration' branch" >&2; exit 1; fi ;;
'''


class WaitChecksTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = test_go.GoTest
    tearDown, go, calls = G.tearDown, G.go, G.calls
    rundir, integration, lines = G.rundir, G.integration, G.lines

    def setUp(self):
        self.G.setUp(self)
        script = test_go.FAKE_GH.replace('  "pr merge")', CHECKS_GH + '  "pr merge")')
        script = script.replace("else echo '{\"state\":\"OPEN\"}'; fi", '''else
      head=$(git ls-remote "$R" refs/heads/gs/demo/integration | cut -f1)
      echo '{"state":"OPEN","headRefOid":"'$head'","baseRefName":"'$B'"}'; fi''')
        (self.bin / "gh").write_text("#!/bin/bash\n" + script)
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("wait_checks = false", "wait_checks = true"))
        sh(self.repo, "git", "commit", "-qam", "wait for CI")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def checks(self, *checks, required=False):
        path = self.bin / ("checks.required" if required else "checks.all")
        path.write_text(json.dumps([{"name": name, "bucket": bucket} for name, bucket in checks]))

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def run_go(self):
        return self.go("--only", "01")

    def merges(self):
        return [line for line in self.lines("gh.log") if line.startswith("pr merge ")]

    def test_pending_then_pass_waits_for_report_head_and_prints_changes(self):
        self.checks(("build", "pass"), ("test", "pending"))
        heads, progress = [], []

        def sleep(seconds):
            st = state.load(self.rundir, "demo")
            progress.append(st.progress["line"])
            head = sh(self.remote, "git", "rev-parse", "gs/demo/integration")
            heads.append(head)
            self.assertEqual(st.finish["merge_head"], head)
            self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", head), "gs: demo 최종 보고서")
            if len(heads) == 2:
                self.checks(("build", "pass"), ("test", "pass"))

        with mock.patch("gs.finish.time", SimpleNamespace(monotonic=time.monotonic, sleep=sleep)):
            code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(heads), 2)
        self.assertTrue(all("CI 대기 중" in line for line in progress))
        self.assertEqual(out.count("CI 검사 대기 중(build ✓, test …)"), 1)
        self.assertEqual(out.count("CI 검사 대기 중(build ✓, test ✓)"), 1)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertIn(heads[0], self.merges()[0])

    def test_only_required_checks_gate_merge(self):
        self.checks(("build", "pass"), required=True)
        self.checks(("optional", "fail"))
        code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertIn("build ✓", out)
        self.assertNotIn("optional ✗", out)
        queries = [line for line in self.lines("gh.log") if line.startswith("pr checks ")]
        self.assertTrue(all("--required" in line for line in queries))

    def test_failure_leaves_pr_open_and_notifies_names(self):
        self.checks(("build", "fail"), ("test", "cancel"), ("slow", "pending"))
        before = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.run_go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "checks_failed")
        self.assertEqual(self.finish()["outcome"], "CI 실패: build, test")
        self.assertEqual(self.merges(), [])
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), before)
        self.assertTrue((self.bin / "gh.open").exists())
        r = SimpleNamespace(st=state.load(self.rundir, "demo"), order=["01"], name="demo", base="main")
        self.assertIn("CI 실패: build, test", go._message(r, self.finish()["url"], False))

    def timeout(self):
        self.checks(("test", "pending"))
        elapsed = [0]

        def sleep(seconds):
            elapsed[0] += seconds

        with mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)):
            # 기본 60분 대신 시험에서는 1분. 설정을 바꾸는 커밋은 만들지 않는다.
            real_load = config.load

            def load(repo):
                cfg, problems = real_load(repo)
                return replace(cfg, timeouts=replace(cfg.timeouts, checks_minutes=1)), problems

            with mock.patch("gs.go.config.load", side_effect=load):
                return self.run_go()

    def test_timeout_leaves_pr_open_and_notifies(self):
        code, out, err = self.timeout()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "checks_timeout")
        self.assertEqual(self.finish()["outcome"], "CI 대기 시간 초과")
        self.assertEqual(self.merges(), [])
        self.assertTrue((self.bin / "gh.open").exists())
        self.assertEqual(out.count("CI 검사 대기 중(test …)"), 1)
        r = SimpleNamespace(st=state.load(self.rundir, "demo"), order=["01"], name="demo", base="main")
        self.assertIn("CI 대기 시간 초과", go._message(r, self.finish()["url"], False))

    def test_no_checks_merges_after_grace(self):
        elapsed = [0]

        def sleep(seconds):
            self.assertEqual(self.merges(), [])
            elapsed[0] += seconds

        with mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)):
            code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(elapsed[0], 60)
        self.assertIn("CI 검사 대기 중(검사 없음)", out)
        self.assertIn("검사 없음 → 병합", out)
        self.assertEqual(len(self.merges()), 1)

    def assert_same_head_resume(self, phase):
        old = self.finish()
        self.assertEqual(old["phase"], phase)
        self.checks(("test", "pass"))
        real_verify = finish._verify
        labels = []

        def verify(r, wt, label):
            labels.append(label)
            return real_verify(r, wt, label)

        with mock.patch("gs.finish._verify", side_effect=verify):
            code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["merge_head"], old["merge_head"])
        self.assertEqual(labels, ["main"])
        self.assertEqual(self.calls(), ["01"])

    def test_same_head_resumes_failure_without_reverification(self):
        self.checks(("test", "fail"))
        self.assertEqual(self.run_go()[0], 1)
        self.assert_same_head_resume("checks_failed")

    def test_same_head_resumes_timeout_without_reverification(self):
        self.assertEqual(self.timeout()[0], 1)
        self.assert_same_head_resume("checks_timeout")

    def test_disabled_does_not_query_failing_checks(self):
        self.checks(("test", "fail"))
        real_load = config.load

        def load(repo):
            cfg, problems = real_load(repo)
            return replace(cfg, git=replace(cfg.git, wait_checks=False)), problems

        with mock.patch("gs.go.config.load", side_effect=load):
            code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertFalse(any(line.startswith("pr checks ") for line in self.lines("gh.log")))

    def change_pr_head(self, broken=False):
        clone = self.repo.parent / "human"
        sh(self.repo.parent, "git", "clone", "-q", str(self.remote), str(clone))
        sh(clone, "git", "checkout", "-q", "gs/demo/integration")
        (clone / ("BROKEN" if broken else "fix.txt")).write_text("human fix\n")
        sh(clone, "git", "add", "-A")
        sh(clone, "git", "commit", "-qm", "human fix")
        sh(clone, "git", "push", "-q", "origin", "HEAD")
        return sh(clone, "git", "rev-parse", "HEAD")

    def test_changed_head_reverified_before_ci_and_merge(self):
        self.checks(("test", "fail"))
        self.assertEqual(self.run_go()[0], 1)
        head = self.change_pr_head()
        self.checks(("test", "pass"))
        code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertIn("integration-recheck 검증", out)
        self.assertEqual(self.finish()["merge_head"], head)
        log = (self.rundir / "finish/integration-recheck-verify.log").read_text()
        self.assertIn(f"HEAD: {head}", log)
        self.assertIn(head, self.merges()[0])
        self.assertEqual(self.calls(), ["01"])

    def test_changed_head_from_timeout_reverified_and_failed_verify_blocks_merge(self):
        self.assertEqual(self.timeout()[0], 1)
        self.change_pr_head(broken=True)
        self.checks(("test", "pass"))
        code, out, err = self.run_go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("integration-recheck 검증", out)
        self.assertEqual(self.finish()["phase"], "not_merged")
        self.assertEqual(self.merges(), [])

    def test_api_error_is_not_treated_as_no_checks(self):
        (self.bin / "checks.error").write_text("HTTP 403: Resource not accessible")
        code, out, err = self.run_go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.merges(), [])
        self.assertIn("HTTP 403", err)
        self.assertEqual(self.finish()["phase"], "checks_pending")

    def test_check_query_timeout_counts_as_ci_timeout(self):
        real_gh = finish._gh

        def gh(r, *args, **kwargs):
            if args[0] == "checks":
                self.assertIn("deadline", kwargs)
                raise subprocess.TimeoutExpired(["gh", "pr", *args], 60)
            return real_gh(r, *args, **kwargs)

        with mock.patch("gs.finish._gh", side_effect=gh):
            code, out, err = self.run_go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "checks_timeout")
        self.assertEqual(self.finish()["outcome"], "CI 대기 시간 초과")
        self.assertEqual(self.merges(), [])

    def test_head_changes_during_check_query_blocks_merge(self):
        self.checks(("test", "pass"))
        real_checks = finish._checks
        moved = []

        def checks(r, **kwargs):
            result = real_checks(r, **kwargs)
            if not moved:
                moved.append(self.change_pr_head())
            return result

        with mock.patch("gs.finish._checks", side_effect=checks):
            code, out, err = self.run_go()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.merges(), [])
        self.assertEqual(self.finish()["phase"], "checks_pending")
        code, out, err = self.run_go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["merge_head"], moved[0])


if __name__ == "__main__":
    unittest.main()
