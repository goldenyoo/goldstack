"""최종 PR head의 CI 게이트와 실패·시간 초과 뒤 gs go 재개."""
import json
import subprocess
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import support
import test_protected_base
from gs import config, finish, go, state
from support import sh


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
    G = support.GoTest
    tearDown, go, calls = G.tearDown, G.go, G.calls
    rundir, integration, lines = G.rundir, G.integration, G.lines

    def setUp(self):
        self.G.setUp(self)
        script = support.FAKE_GH.replace('  "pr merge")', CHECKS_GH + '  "pr merge")')
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

    # --- config `git.checks`로 기다릴 이름을 고른다(goldstack-v33 05) ---

    def name_checks(self, *names):
        """config `git.checks`를 적어 커밋하고 base에 올린다."""
        path = self.repo / config.CONFIG_PATH
        text = path.read_text()
        self.assertIn("\nchecks = []", text)
        path.write_text(text.replace("\nchecks = []", "\nchecks = " + json.dumps(list(names))))
        sh(self.repo, "git", "commit", "-qam", "named checks")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def run_go_clock(self, on_sleep=None):
        """실제 시간 대신 sleep이 더하는 시계로 gs go. (종료 코드, out, err, 지난 초)."""
        elapsed = [0]

        def sleep(seconds):
            self.assertEqual(self.merges(), [])
            elapsed[0] += seconds
            if on_sleep:
                on_sleep(elapsed[0])

        with mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)):
            code, out, err = self.run_go()
        return code, out, err, elapsed[0]

    def test_named_checks_gate_merge_without_protection_lookup(self):
        self.name_checks("linux-only")
        self.checks(("linux-only", "pass"), ("tests", "pending"), ("lint", "fail"))
        self.checks(("tests", "pending"), required=True)
        code, out, err, elapsed = self.run_go_clock()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(elapsed, 0)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(len(self.merges()), 1)
        self.assertIn("CI 검사 대기 중(linux-only ✓)", out)
        gh = self.lines("gh.log")
        self.assertFalse([line for line in gh if "/protection" in line or "/rules/" in line])
        queries = [line for line in gh if line.startswith("pr checks ")]
        self.assertTrue(queries)
        self.assertFalse([line for line in queries if "--required" in line])

    def test_named_check_failure_blocks_merge(self):
        self.name_checks("linux-only")
        self.checks(("linux-only", "fail"), ("tests", "pending"), ("lint", "cancel"))
        before = sh(self.remote, "git", "rev-parse", "main")
        code, out, err, _ = self.run_go_clock()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "checks_failed")
        self.assertEqual(self.finish()["outcome"], "CI 실패: linux-only")
        self.assertEqual(self.merges(), [])
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), before)
        self.assertTrue((self.bin / "gh.open").exists())

    def test_named_check_missing_after_grace_stays_open_and_resumes_same(self):
        self.name_checks("linux-only", "lint")
        self.checks(("tests", "pass"))

        def lint_appears(elapsed):  # 유예 안에 lint만 나타나고(아직 도는 중) linux-only는 끝까지 없다
            if elapsed >= 30:
                self.checks(("lint", "pending"), ("tests", "pass"))

        code, out, err, elapsed = self.run_go_clock(lint_appears)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(elapsed, 60)  # checks_grace_seconds 기본값. 시간 초과(60분)까지 기다리지 않는다
        f = self.finish()
        self.assertEqual(f["phase"], "checks_missing")
        self.assertEqual(f["outcome"], "CI 검사 없음: linux-only")
        self.assertEqual(self.merges(), [])
        self.assertTrue((self.bin / "gh.open").exists())
        self.assertIn("CI 검사 대기 중(lint …, linux-only …)", out)
        self.assertIn("CI 검사 없음(linux-only) → 병합 안 함", out)
        r = SimpleNamespace(st=state.load(self.rundir, "demo"), order=["01"], name="demo", base="main")
        self.assertIn("CI 검사 없음: linux-only", go._message(r, f["url"], False))

        real_verify = finish._verify
        labels = []

        def verify(r, wt, label):
            labels.append(label)
            return real_verify(r, wt, label)

        with mock.patch("gs.finish._verify", side_effect=verify):
            code, out, err, elapsed = self.run_go_clock()  # 다음 gs go가 같은 head를 다시 읽고 같은 판정을 한다
            self.assertEqual(code, 1, out + err)
            self.assertEqual(elapsed, 60)
            self.assertEqual(self.finish()["phase"], "checks_missing")
            self.assertEqual(self.finish()["outcome"], "CI 검사 없음: linux-only")
            self.assertEqual(self.finish()["merge_head"], f["merge_head"])
            self.assertEqual(self.merges(), [])
            self.assertEqual(labels, [])

            self.checks(("linux-only", "pass"), ("lint", "skipping"), ("tests", "pending"))
            code, out, err, _ = self.run_go_clock()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.finish()["merge_head"], f["merge_head"])
        self.assertIn(f["merge_head"], self.merges()[0])
        self.assertEqual(labels, ["main"])
        self.assertEqual(self.calls(), ["01"])

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


class NamedChecksSidePrTest(unittest.TestCase):
    """보호된 base의 보고서 PR(`_side_pr`)도 `git.checks`의 이름만 기다리고, 없으면 같은 판정으로 멈춘다."""
    BASE, REMOTE = "main", "origin"
    G, P = support.GoTest, test_protected_base.ProtectedBaseTest
    tearDown, calls, rundir, integration, lines = G.tearDown, G.calls, G.rundir, G.integration, G.lines
    final_report, remote_files = G.final_report, G.remote_files
    prs, finish, merges, base_report = P.prs, P.finish, P.merges, P.base_report
    assert_no_base_push, protected_go = P.assert_no_base_push, P.go

    def setUp(self):
        self.P.setUp(self, wait_checks=True)

    def go(self):
        """원격 hook이 base push를 막아 config 커밋을 올릴 수 없다. 읽은 config에 이름을 넣는다. 시계는 sleep이 더한다."""
        real_load, elapsed = config.load, [0]

        def load(repo):
            cfg, problems = real_load(repo)
            return replace(cfg, git=replace(cfg.git, checks=("linux-only", "lint"))), problems

        def sleep(seconds):
            elapsed[0] += seconds

        with mock.patch("gs.go.config.load", side_effect=load), \
                mock.patch("gs.finish.time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=sleep)):
            code, out, err = self.protected_go()
        return code, out, err, elapsed[0]

    def test_report_pr_waits_for_named_checks_and_stops_when_missing(self):
        url = test_protected_base.URL.format(2)
        checks = self.bin / "checks.all"
        checks.write_text(json.dumps([{"name": "linux-only", "bucket": "pass"}, {"name": "lint", "bucket": "pass"},
                                      {"name": "tests", "bucket": "pending"}]))
        (self.bin / "checks.2").write_text(json.dumps([{"name": "tests", "bucket": "pass"}]))
        for _ in range(2):  # 다음 gs go도 같은 판정
            code, out, err, elapsed = self.go()
            self.assertEqual(code, 1, out + err)
            self.assertEqual(elapsed, 60)  # 기능 PR은 바로 통과, 보고서 PR은 유예만큼
            f = self.finish()
            self.assertEqual(f["phase"], "report_pending")
            self.assertEqual(f["outcome"], f"report PR CI 검사 없음: linux-only, lint: {url}")
            self.assertEqual([p["state"] for p in self.prs()], ["MERGED", "OPEN"])
            self.assertFalse([m for m in self.merges() if m.startswith(f"pr merge {url} ")])
            self.assertIn("CI 검사 없음(linux-only, lint) → 병합 안 함", out)

        (self.bin / "checks.2").unlink()  # 보고서 PR에도 적은 검사가 나타나 통과했다
        code, out, err, _ = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual([p["state"] for p in self.prs()], ["MERGED", "MERGED"])
        self.assertIn("\n마무리: verified · ", self.base_report())
        gh = self.lines("gh.log")
        self.assertFalse([line for line in gh if "/protection" in line or "/rules/" in line])
        self.assertFalse([line for line in gh if line.startswith("pr checks ") and "--required" in line])
        self.assertEqual(self.calls(), ["01"])
        self.assert_no_base_push()


if __name__ == "__main__":
    unittest.main()
