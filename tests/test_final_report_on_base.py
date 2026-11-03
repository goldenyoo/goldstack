"""goldstack-v3 02: 마무리 상태 줄은 코드가 state에서 쓰고, 마무리가 끝난 최종 report.md를 base에도 push한다."""
import unittest
from types import SimpleNamespace
from unittest import mock

import test_go
from gs import git, report, state
from test_go import sh

REPORT = ".goldstack/work/demo/report.md"
SUBJECT = "gs: demo 최종 보고서(병합 후)"
URL = "https://example.test/pr/1"
SHA = "abcdef0123456789abcdef0123456789abcdef01"


class StatusLineTest(unittest.TestCase):
    def line(self, merged=True, **finish):
        st = state.State(feature="demo")
        st.ticket("01").status = state.MERGED if merged else state.FAILED
        st.finish = finish
        return report.status_line(SimpleNamespace(st=st, base="main", order=["01"]))

    def test_each_phase(self):
        cases = [
            ({"phase": "verified", "url": URL, "main_ok": True}, f"마무리: verified · PR {URL} 병합 · main 검증 통과"),
            # 병합 명령은 오류였지만 실제로 병합됐다. 끝난 phase에는 오류 표시를 붙이지 않는다
            ({"phase": "verified", "url": URL, "error": "gh pr merge: x"}, f"마무리: verified · PR {URL} 병합 · main 검증 통과"),
            ({"phase": "reverted", "url": URL, "main_ok": False, "revert_sha": SHA},
             "마무리: reverted · main 검증 실패 → revert abcdef01"),
            ({"phase": "reverted", "url": URL, "revert_sha": SHA}, "마무리: reverted · main에서 이미 되돌림 → revert abcdef01"),
            ({"phase": "not_merged", "url": URL, "integration_ok": False}, "마무리: not_merged · integration 검증 실패"),
            ({"phase": "closed", "url": URL}, f"마무리: closed · PR {URL}이 병합되지 않고 닫힘"),
            ({"phase": "merge_pending", "url": URL}, f"마무리: merge_pending · PR {URL} 병합 대기 · main 검증 미실행"),
            ({"phase": "merge_requested", "url": URL}, f"마무리: merge_requested · PR {URL} 병합 대기 · main 검증 미실행"),
            ({"phase": "merged", "url": URL}, f"마무리: merged · PR {URL} 병합 · main 검증 대기"),
            ({"phase": "main_failed", "url": URL, "revert_sha": SHA, "error": "push rejected"},
             "마무리: main_failed · main 검증 실패 · revert abcdef01 push 안 됨 · 오류(아래 Merge Danger)"),
            ({"phase": "preparing"}, "마무리: preparing · 병합 전"),
            ({}, "마무리: preparing · 병합 전"),
        ]
        for finish, want in cases:
            with self.subTest(finish=finish):
                self.assertEqual(self.line(**finish), want)
        self.assertEqual(self.line(merged=False, phase="not_merged", integration_ok=True),
                         "마무리: not_merged · merged 티켓 없음")


class FinalReportOnBaseTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = test_go.GoTest
    setUp, tearDown, go = G.setUp, G.tearDown, G.go
    rundir, integration, parallel, lines, final_report = G.rundir, G.integration, G.parallel, G.lines, G.final_report
    someone, remote_files, under_report = G.someone, G.remote_files, G.under_report

    def base_report(self):
        return sh(self.remote, "git", "show", f"main:{REPORT}")

    def tip(self):
        return sh(self.remote, "git", "rev-parse", "main")

    def assert_nothing_pushed(self, before):
        self.assertEqual(self.tip(), before)
        self.assertNotIn(SUBJECT, sh(self.remote, "git", "log", "--format=%s", "main"))

    def count(self, prefix):
        return sum(x.startswith(prefix) for x in self.lines("gh.log"))

    def test_verified_report_lands_on_base_and_next_go_leaves_it(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        line = f"마무리: verified · PR {URL} 병합 · main 검증 통과"
        # 마무리 줄은 Summary 바로 아래, 코드가 쓴다. judge에게는 마무리 상태 문장을 쓰지 말라고 했다
        self.assertIn(f"## Summary\n\n티켓의 변경을 integration에서 모아 검증했다.\n\n{line}\n\n## Evidence",
                      self.final_report())
        prompt = (self.bin / "judge.input").read_text()
        self.assertIn("report-input.md", prompt)
        self.assertIn("마무리 상태(PR 병합 여부, base 검증 결과, revert)를 말하는 문장은 쓰지 마라", prompt)
        # base의 최신 끝(병합 커밋) 위에 report.md만 바꾼 커밋 하나, force 없이
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", "main"), REPORT)
        self.assertEqual(self.base_report(), self.final_report())
        self.assertIn(f"\n{line}\n", self.base_report())
        self.assertEqual(f["base_report"], self.tip())
        self.assertIn("최종 보고서를 main에 push했다", out)
        self.assertEqual(list(self.rundir.glob("gs-report-*")), [])
        self.assertNotIn("gs-report-", self.integration("worktree", "list"))

        tip, merges, creates = self.tip(), self.count("pr merge "), self.count("pr create ")
        code, out, err = self.go("--only", "01")  # 같은 feature에 이어 gs go: 보고서 커밋을 새 일로 보지 않는다
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertEqual((self.count("pr merge "), self.count("pr create ")), (merges, creates))
        self.assertEqual(self.tip(), tip)
        self.assertEqual(self.base_report(), self.final_report())
        self.assertNotIn("경고", out + err)

    def test_reverted_report_lands_on_base(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(self.base_report(), self.final_report())
        self.assertIn(f"\n마무리: reverted · main 검증 실패 → revert {f['revert_sha'][:8]}\n", self.base_report())
        self.assertNotIn("file_01", self.remote_files())  # 보고서 커밋은 revert를 되돌리지 않는다

    def test_not_merged_pushes_nothing(self):
        before = self.tip()
        code, out, err = self.go("--only", "02,03")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "not_merged")
        self.assert_nothing_pushed(before)
        self.assertIn("\n마무리: not_merged · merged 티켓 없음\n", self.final_report())

    def test_integration_failure_pushes_nothing(self):
        self.parallel(1, verify="git rev-parse -q --verify MERGE_HEAD >/dev/null")
        before = self.tip()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "not_merged")
        self.assert_nothing_pushed(before)
        self.assertIn("\n마무리: not_merged · integration 검증 실패\n", self.final_report())

    def test_merge_pending_and_closed_push_nothing(self):
        (self.bin / "gh.queue").touch()
        before = self.tip()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        self.assert_nothing_pushed(before)
        (self.bin / "gh.queue").unlink()
        (self.bin / "gh.open").unlink()
        (self.bin / "gh.closed").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "closed")
        self.assert_nothing_pushed(before)
        self.assertIn(f"\n마무리: closed · PR {URL}이 병합되지 않고 닫힘\n", self.final_report())

    def move_base_before_report_push(self, times):
        """gs의 보고서 push 직전에 다른 사람이 main에 push한다(times번까지). 그 커밋들을 돌려준다."""
        moved, real_run = [], git.run

        def run(cwd, *args, **kw):
            if args[:1] == ("push",) and "gs-report-" in str(cwd) and len(moved) < times:
                moved.append(self.someone(f"echo {len(moved)} > other.txt", "git add other.txt",
                                          f"git commit -qm 'someone else {len(moved)}'"))
            return real_run(cwd, *args, **kw)

        return moved, mock.patch("gs.git.run", side_effect=run)

    def test_rejected_push_is_rebuilt_on_latest_base(self):
        moved, patch = self.move_base_before_report_push(1)
        with patch:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(moved), 1)
        self.assertEqual(self.under_report(), moved[0])  # force 없이 최신 main 위에 다시 만들었다
        self.assertEqual(self.base_report(), self.final_report())
        self.assertIn("other.txt", self.remote_files())
        self.assertNotIn("경고", out)

    def test_twice_rejected_push_only_warns(self):
        moved, patch = self.move_base_before_report_push(2)
        with patch:
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)  # 실행 결과·종료 코드는 그대로
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertNotIn("base_report", f)
        self.assertEqual(self.tip(), moved[1])
        self.assertNotIn(SUBJECT, sh(self.remote, "git", "log", "--format=%s", "main"))
        self.assertIn("■ 경고: 최종 보고서를 main에 push하지 못했다(두 번 시도)", out)
        self.assertEqual(list(self.rundir.glob("gs-report-*")), [])
        code, out, err = self.go("--only", "01")  # 다음 gs go는 재시도하지 않는다(spec 2-6)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.tip(), moved[1])

    def test_update_failure_before_first_attempt_is_tried_on_resume(self):
        """verified 뒤 보고서 갱신(gh pr edit)이 실패해 base push를 한 번도 시도하지 못했으면 다음 gs go가 시도한다."""
        from gs import finish
        failed, real_gh = [], finish._gh

        def gh(r, *args):
            if args[:1] == ("edit",) and r.st.finish.get("phase") == "verified" and not failed:
                failed.append(args)
                raise git.GitError("gh pr edit: temporary failure")
            return real_gh(r, *args)

        before = self.tip()
        with mock.patch("gs.finish._gh", side_effect=gh):
            code, out, err = self.go("--only", "01")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(len(failed), 1)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertNotIn("base_report_tried", f)
        self.assertNotIn(SUBJECT, sh(self.remote, "git", "log", "--format=%s", "main"))
        self.assertNotEqual(self.tip(), before)  # 병합은 됐다

        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(self.base_report(), self.final_report())
        self.assertEqual(f["base_report"], self.tip())
        self.assertTrue(f["base_report_tried"])


if __name__ == "__main__":
    unittest.main()
