"""빠른 티켓 검증, 명령 재시도, 보고서만 바뀐 최종 검증의 생략."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_check
import support
from gs import feature, finish, report, state, verify


class VerifySpecTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def spec(self, extra=""):
        (self.repo / ".goldstack/work/demo/spec.md").write_text(
            '---\nfeature: demo\nverify: "true"\n' + extra + '---\n')
        self.write("01-a.md", test_check.ticket("01"))

    def test_defaults_and_optional_modes_pass_check(self):
        for extra, command, retries in (("", "true", 0),
                                        ('verify_ticket: echo fast\nverify_retries: 2\n', "echo fast", 2),
                                        ('verify_retries: 0\n', "true", 0)):
            with self.subTest(extra=extra):
                self.spec(extra)
                code, out, err = self.run_check()
                self.assertEqual((code, err), (0, ""), out + err)
                spec = feature.load(self.repo, "demo").spec
                self.assertEqual((spec.ticket_verify, spec.verify_retries), (command, retries))

    def test_invalid_optional_values_are_check_errors(self):
        for key, values in (("verify_ticket", ["", " ", "echo a\necho b", "echo a\recho b", []]),
                            ("verify_retries", [-1, "", " ", "1.5", "true", []])):
            for value in values:
                with self.subTest(key=key, value=value):
                    self.spec(f'{key}: {json.dumps(value)}\n')
                    code, out, err = self.run_check()
                    self.assertEqual(code, 1, out + err)
                    self.assertIn("오류:", err)


class VerifyRetriesTest(unittest.TestCase):
    def test_success_retry_exhaustion_and_default(self):
        for retries, needed, ok, count in ((1, 2, True, 2), (2, 10, False, 3), (0, 2, False, 1)):
            with self.subTest(retries=retries), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                spec = SimpleNamespace(verify=f'n=$(cat count 2>/dev/null || echo 0); n=$((n+1)); '
                                              f'echo $n > count; echo attempt-$n; test $n -ge {needed}',
                                       verify_minutes=1, verify_retries=retries)
                with (cwd / "verify.log").open("w") as stream:
                    result = verify.run(spec, cwd, stream)
                    verify.flaky(result, "point", stream)
                self.assertEqual((result.ok, result.retries), (ok, count - 1))
                self.assertEqual(int((cwd / "count").read_text()), count)
                log = (cwd / "verify.log").read_text()
                self.assertIn("attempt-1", log)
                self.assertEqual("flaky: point 재시도 1번 만에 통과" in log, ok)

    def test_timeout_and_launch_failure_also_retry(self):
        spec = SimpleNamespace(verify="true", verify_minutes=1, verify_retries=1)
        for first in (verify.Result(-15, True, "1"), verify.Result(1, False, "1")):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as tmp:
                with mock.patch("gs.verify._run_once", side_effect=[first, verify.Result(0, False, "1")]) as run:
                    with (Path(tmp) / "verify.log").open("w") as stream:
                        result = verify.run(spec, Path(tmp), stream)
                self.assertEqual((result.ok, result.retries, run.call_count), (True, 1, 2))


class VerifyModesTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    setUp, tearDown, go, calls = G.setUp, G.tearDown, G.go, G.calls
    rundir, integration, final_report, lines = G.rundir, G.integration, G.final_report, G.lines

    def configure(self, **settings):
        path = self.repo / ".goldstack/work/demo/spec.md"
        path.write_text('---\nfeature: demo\nmax_workers: 1\n' + ''.join(
            f'{key}: {json.dumps(value)}\n' for key, value in settings.items()) + '---\n')
        support.sh(self.repo, "git", "add", "-A")
        support.sh(self.repo, "git", "commit", "-qm", "verify modes")
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def test_ticket_command_runs_in_merge_tree_and_is_in_brief(self):
        full = f'echo "$PWD" >> {self.bin / "full"}'
        fast = f'git rev-parse -q --verify MERGE_HEAD && echo "$PWD" >> {self.bin / "fast"}'
        self.configure(verify=full, verify_ticket=fast)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual([Path(p).name for p in self.lines("fast")], ["integration"])
        self.assertEqual([Path(p).name for p in self.lines("full")], ["integration", "base"])
        brief = (self.rundir / "01/1/brief.md").read_text()
        self.assertIn(f'검증 명령 `{fast}`', brief)
        self.assertNotIn(f'검증 명령 `{full}`', brief)
        self.assertIn(f'티켓 검증 명령: `{fast}`', self.final_report())
        self.assertIn("integration-final: 보고서만 바뀜, 건너뜀", self.final_report())

    def change_code_with_report(self):
        commit_report = finish._commit_report
        changed = []

        def commit(r, summary):
            path = commit_report(r, summary)
            if not changed:
                changed.append(True)
                (r.iwt / "extra").write_text("code change\n")
                support.sh(r.iwt, "git", "add", "extra")
                support.sh(r.iwt, "git", "commit", "-qm", "extra code")
            return path
        return mock.patch("gs.finish._commit_report", side_effect=commit)

    def test_other_changed_file_runs_final_verify_and_blocks_merge_on_failure(self):
        self.configure(verify="test ! -f extra")
        with self.change_code_with_report():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        log = (self.rundir / "finish/integration-final-verify.log").read_text()
        self.assertIn("종료 코드: 1", log)
        self.assertNotIn("건너뜀", log)
        self.assertFalse(any(line.startswith("pr merge ") for line in self.lines("gh.log")))

    def retry_script(self, *, always_fail=""):
        script = self.bin / "verify.sh"
        script.write_text(f'''\
here={self.bin}
if [ "${{PWD##*/}}" = base ]; then point=main
elif git rev-parse -q --verify MERGE_HEAD >/dev/null; then point=ticket-01
elif [ -f extra ]; then point=integration-final
else point=integration; fi
echo "$point" >> "$here/verifies"
if [ "$point" = "{always_fail}" ]; then echo failed-$point; exit 1; fi
if [ ! -f "$here/passed-$point" ]; then touch "$here/passed-$point"; echo first-failure-$point; exit 1; fi
echo passed-$point
''')
        return f"bash {script}"

    def test_all_points_retry_once_and_record_flaky_in_report(self):
        command = self.retry_script()
        self.configure(verify=command, verify_ticket=command, verify_retries=1)
        with self.change_code_with_report():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertEqual(self.lines("verifies"), [p for p in (
            "ticket-01", "integration", "integration-final", "main") for _ in range(2)])
        body = self.final_report()
        compact = report.evidence(SimpleNamespace(
            rundir=self.rundir, order=["01"], st=state.load(self.rundir, "demo"),
            feat=feature.load(self.repo, "demo")), tail=0)
        for point in ("ticket-01", "integration", "integration-final", "main"):
            self.assertIn(f"flaky: {point} 재시도 1번 만에 통과", body)
            self.assertIn(f"flaky: {point} 재시도 1번 만에 통과", compact)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")

    def test_exhausted_retries_leave_integration_failed(self):
        command = self.retry_script(always_fail="integration")
        self.configure(verify=command, verify_ticket=command, verify_retries=2)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket-01"] * 2 + ["integration"] * 3)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "not_merged")
        body = self.final_report()
        self.assertIn("failed-integration", body)
        self.assertNotIn("flaky: integration ", body)
        self.assertFalse(any(line.startswith("pr merge ") for line in self.lines("gh.log")))


if __name__ == "__main__":
    unittest.main()
