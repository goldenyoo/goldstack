"""티켓 검증: 병합 트리에서 돌고 트리를 바꾸면 실패, 티켓 `verify` 키, worker 지시문, 보고서 표시(goldstack-v7 02)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import support
import test_check
import test_verify_modes
from gs import feature, report, setup, state
from gs.feature import Spec, Ticket
from support import sh

SUFFIX = "개발 중에는 관련 시험만 돌리고, 커밋 전에 이 명령을 한 번 돌린다"
CHANGED = "검증 중 worktree가 바뀌었다"


class TicketVerifyKeyTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def test_valid_key_passes_check_without_warning(self):
        self.write("01-a.md", test_check.ticket("01", extra='verify: "echo doc && true"\n'))
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""), out + err)
        self.assertNotIn("알 수 없는 키", out)
        self.assertEqual(feature.load(self.repo, "demo").tickets["01"].verify, "echo doc && true")

    def test_no_key_is_none(self):
        self.write("01-a.md", test_check.ticket("01"))
        self.assertIsNone(feature.load(self.repo, "demo").tickets["01"].verify)

    def test_empty_or_multiline_is_check_error(self):
        for value in ("", " ", "echo a\necho b", "echo a\recho b", []):
            with self.subTest(value=value):
                self.write("01-a.md", test_check.ticket("01", extra=f"verify: {json.dumps(value)}\n"))
                code, out, err = self.run_check()
                self.assertEqual(code, 1, out + err)
                self.assertIn("`verify`는 비어 있지 않은 한 줄 셸 명령이어야 한다", err)

    def test_missing_value_is_check_error(self):
        self.write("01-a.md", test_check.ticket("01", extra="verify:\n"))
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out + err)
        self.assertIn("오류:", err)

    def test_priority(self):
        def spec(verify_ticket):
            return Spec(feature="demo", verify="full", max_workers=1, idle_minutes=1, verify_minutes=1,
                        path=Path("spec.md"), verify_ticket=verify_ticket)

        def ticket(verify):
            return Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex",
                          path=Path("01-t.md"), verify=verify)

        self.assertEqual(spec("fast").verify_for(ticket("own")), "own")
        self.assertEqual(spec(None).verify_for(ticket("own")), "own")
        self.assertEqual(spec("fast").verify_for(ticket(None)), "fast")
        self.assertEqual(spec(None).verify_for(ticket(None)), "full")


class IsCleanStagedTest(unittest.TestCase):
    """미완 병합의 트리: index의 변경은 괜찮고, index와 다른 파일·untracked는 더럽다."""

    def setUp(self):
        support.isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = Path(self.tmp.name)
        sh(self.wt, "git", "init", "-q")
        (self.wt / "a").write_text("a\n" * 20)
        sh(self.wt, "git", "add", "a")
        sh(self.wt, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")

    def clean(self):
        return setup.is_clean(self.wt), setup.is_clean(self.wt, staged_ok=True)

    def test_clean_tree(self):
        self.assertEqual(self.clean(), (True, True))

    def test_staged_changes_only_pass_with_flag(self):
        (self.wt / "b").write_text("b\n")
        sh(self.wt, "git", "add", "b")
        self.assertEqual(self.clean(), (False, True))

    def test_staged_rename_passes_with_flag(self):
        sh(self.wt, "git", "mv", "a", "renamed")
        self.assertEqual(self.clean(), (False, True))

    def test_unstaged_change_on_staged_file_fails(self):
        (self.wt / "b").write_text("b\n")
        sh(self.wt, "git", "add", "b")
        (self.wt / "b").write_text("changed\n")
        self.assertEqual(self.clean(), (False, False))

    def test_untracked_fails_unless_setup_artifact(self):
        (self.wt / "stray").write_text("x\n")
        self.assertEqual(self.clean(), (False, False))
        setup.remember(self.wt)
        self.assertEqual(self.clean(), (True, True))


class TicketVerifyRunTest(support.GoTest):
    change_code_with_report = test_verify_modes.VerifyModesTest.change_code_with_report

    def configure(self, verify, verify_ticket=None, tickets=None):
        """spec과 티켓 `verify`를 적고 커밋·push한다."""
        settings = {"verify": verify}
        if verify_ticket is not None:
            settings["verify_ticket"] = verify_ticket
        fdir = self.repo / ".goldstack/work/demo"
        (fdir / "spec.md").write_text("---\nfeature: demo\nmax_workers: 1\n" + "".join(
            f"{key}: {json.dumps(value)}\n" for key, value in settings.items()) + "---\n")
        self.ticket_commands(tickets or {})

    def ticket_commands(self, tickets):
        fdir = self.repo / ".goldstack/work/demo"
        for tid, command in tickets.items():
            path = fdir / "tickets" / f"{tid}-t.md"
            path.write_text(path.read_text().replace("reviewer: codex\n",
                                                     f"reviewer: codex\nverify: {json.dumps(command)}\n"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "verify 설정")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def record(self, name):
        """돈 위치(디렉터리 이름)를 bin/<name>에 적는 명령."""
        return f'echo "${{PWD##*/}}" >> {self.bin / name}'

    def brief(self, tid):
        return (self.rundir / tid / "1/brief.md").read_text()

    # --- 병합 트리에서 돈다 ---
    def leave_uncommitted_file(self):
        (self.bin / "worker.sh").write_text(
            'echo "$GS_TICKET" >> "$(dirname "$0")/calls.log"\n'
            'echo left > leftover\n'
            'echo done > "file_$GS_TICKET"; git add "file_$GS_TICKET"; git commit -qm "t$GS_TICKET"\n')

    def assert_leftover_does_not_pass(self):
        self.leave_uncommitted_file()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts), ("failed", 2), out)
        self.assertIn("검증 실패", ts.reason)
        self.assertIn("worktree에 커밋 안 된 변경이 남았다", out)
        self.assertIn("cwd: ", (self.rundir / "01/1/verify.log").read_text())
        self.assertIn(str(self.rundir / "wt/integration"), (self.rundir / "01/1/verify.log").read_text())

    def test_verify_ticket_does_not_see_uncommitted_file(self):
        self.configure("true", verify_ticket="test -f leftover")
        self.assert_leftover_does_not_pass()

    def test_ticket_verify_does_not_see_uncommitted_file(self):
        self.configure("true", tickets={"01": "test -f leftover"})
        self.assert_leftover_does_not_pass()

    def test_committed_file_is_in_merge_tree(self):
        self.configure("true", verify_ticket="test -f file_01 && git rev-parse -q --verify MERGE_HEAD")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01"])

    # --- 검증이 트리를 바꾸면 실패 ---
    def assert_left_files_are_repaired(self, change):
        """첫 검증만 파일을 남긴다. 병합 상태는 그대로라 브랜치의 결함일 수 있어 수리로 간다. 다시 검증은 깨끗한 integration에서 통과한다."""
        once = self.bin / "changed"
        self.configure("true", verify_ticket=f"if [ ! -f {once} ]; then touch {once}; {change}; fi")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0), out)
        self.assertIn(CHANGED, (self.rundir / "01/1/verify.log").read_text())
        self.assertNotIn(CHANGED, (self.rundir / "01/1/repair/verify.log").read_text())
        self.assertEqual(self.merged(), ["01"])
        return ts.repairs[0]["reason"]

    def assert_change_fails_once(self, change):
        """첫 검증만 트리를 바꾼다. 그 시도는 실패하고, 재시도는 제 브랜치의 깨끗한 integration에서 통과한다."""
        once = self.bin / "changed"
        self.configure("true", verify_ticket=f"if [ ! -f {once} ]; then touch {once}; {change}; fi")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1), out)
        self.assertIn(CHANGED, (self.rundir / "01/1/verify.log").read_text())
        self.assertNotIn(CHANGED, (self.rundir / "01/2/verify.log").read_text())
        self.assertEqual(self.merged(), ["01"])
        return (self.rundir / "01/1/failure.log").read_text()

    def test_untracked_file_fails(self):
        self.assertIn(CHANGED, self.assert_left_files_are_repaired("touch stray"))
        self.assertNotIn("stray", self.integration("ls-tree", "-r", "--name-only", "gs/demo/integration").split())

    def test_modified_tracked_file_fails(self):
        self.assertIn(CHANGED, self.assert_left_files_are_repaired("echo more >> file_01"))

    def test_staged_file_fails(self):
        self.assert_change_fails_once("touch staged; git add staged")
        self.assertNotIn("staged", self.integration("ls-tree", "-r", "--name-only", "gs/demo/integration").split())

    def test_head_change_fails(self):
        self.assert_change_fails_once("git commit -qm 'merge by verify'")
        self.assertNotIn("merge by verify", self.integration("log", "--format=%s", "gs/demo/integration"))

    def test_branch_change_fails_and_integration_returns_to_branch(self):
        self.assert_change_fails_once("git checkout -q -b elsewhere")
        self.assertEqual(sh(self.repo, "git", "branch", "--list", "elsewhere").strip(), "elsewhere")
        self.assertNotIn("file_01", sh(self.repo, "git", "ls-tree", "-r", "--name-only", "elsewhere").split())

    def test_detached_head_fails_and_integration_returns_to_branch(self):
        self.assert_change_fails_once("git checkout -q --detach")

    def test_ticket_key_change_fails_too(self):
        self.configure("true", tickets={"01": "touch stray"})
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts), ("failed", 2), out)
        self.assertIn(CHANGED, ts.reason)
        self.assertIn(CHANGED, (self.rundir / "01/2/verify.log").read_text())

    def test_failed_command_that_changes_tree_logs_both(self):
        self.configure("true", tickets={"01": "touch stray; exit 3"})
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertIn(CHANGED, (self.rundir / "01/1/verify.log").read_text())
        self.assertIn("검증 실패", state.load(self.rundir, "demo").tickets["01"].reason)

    # --- 우선순위, brief, 보고서 ---
    def test_ticket_key_beats_verify_ticket_and_verify_ticket_beats_verify(self):
        own, fast, full = self.record("own"), self.record("fast"), self.record("full")
        self.configure(full, verify_ticket=fast, tickets={"01": own})
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("own"), ["integration"])  # 01
        self.assertEqual(self.lines("fast"), ["integration"])  # 04
        self.assertEqual(self.lines("full"), ["integration", "base"])  # 마무리
        self.assertIn(f"검증 명령 `{own}`", self.brief("01"))
        self.assertNotIn(f"검증 명령 `{fast}`", self.brief("01"))
        self.assertIn(f"검증 명령 `{fast}`", self.brief("04"))
        body = self.final_report()
        self.assertIn(f"티켓 검증 명령(01): `{own}`", body)
        self.assertIn(f"티켓 검증 명령: `{fast}`", body)

    def test_spec_verify_is_last_and_report_shows_only_own(self):
        own, full = self.record("own"), self.record("full")
        self.configure(full, tickets={"01": own})
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("own"), ["integration"])
        self.assertEqual(self.lines("full"), ["integration", "integration", "base"])  # 04, 마무리 둘
        self.assertIn(f"검증 명령 `{full}`", self.brief("04"))
        body = self.final_report()
        self.assertIn(f"티켓 검증 명령(01): `{own}`", body)
        self.assertNotIn("티켓 검증 명령: ", body)

    def test_no_override_runs_spec_verify_without_ticket_line(self):
        full = self.record("full")
        self.configure(full)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("full"), ["integration", "integration", "base"])
        self.assertIn(f"검증 명령 `{full}`", self.brief("01"))
        self.assertNotIn("티켓 검증 명령", self.final_report())

    def test_report_groups_tickets_and_hides_unused_verify_ticket(self):
        def commands(fast, **verifies):
            return report.ticket_commands(SimpleNamespace(
                order=list(verifies),
                feat=SimpleNamespace(spec=SimpleNamespace(verify="full", verify_ticket=fast),
                                     tickets={tid: SimpleNamespace(verify=v) for tid, v in verifies.items()})))
        self.assertEqual(commands("fast", a="own", b="own"), "티켓 검증 명령(a, b): `own`\n\n")
        self.assertEqual(commands("fast", a="own", b=None),
                         "티켓 검증 명령: `fast`\n\n티켓 검증 명령(a): `own`\n\n")
        self.assertEqual(commands(None, a=None), "")

    def test_brief_names_ticket_command_for_worker_and_fix_worker(self):
        own = self.record("own")
        self.configure("true", tickets={"01": own})
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        fix = (self.rundir / "01/1/fix/brief.md").read_text()
        self.assertIn("## 리뷰 지적(고칠 것)", fix)
        self.assertIn(f"검증 명령 `{own}`: {SUFFIX}", self.brief("01"))
        self.assertIn(f"검증 명령 `{own}`: 전체 검증은 gs가", fix)  # 수정 worker는 좁은 시험만(tests/test_fix_brief.py)
        for brief in (self.brief("01"), fix):
            self.assertNotIn("검증 명령 `true`", brief)

    # --- 마무리는 늘 spec verify ---
    def assert_log_runs(self, label, command):
        log = (self.rundir / "finish" / f"{label}-verify.log").read_text()
        self.assertEqual(log.splitlines()[0], f"$ {command}")

    def test_integration_and_final_run_spec_verify(self):
        own, full = self.record("own"), self.record("full")
        self.configure(full, verify_ticket=self.record("fast"), tickets={"01": own})
        with self.change_code_with_report():
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("own"), ["integration"])
        self.assertEqual(self.lines("fast"), [])
        self.assertEqual(self.lines("full"), ["integration", "integration", "base"])
        for label in ("integration", "integration-final", "main"):
            self.assert_log_runs(label, full)

    def test_main_recheck_runs_spec_verify(self):
        self.break_main(advance=True)
        command = f"bash {self.bin / 'verify.sh'}"
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        own = self.record("own")
        self.ticket_commands({"01": own})
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "main_failed")
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assert_log_runs("main-recheck", command)
        self.assertEqual(self.lines("own"), ["integration"])


if __name__ == "__main__":
    unittest.main()
