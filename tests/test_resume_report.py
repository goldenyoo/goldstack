"""goldstack-v6 03: 재개는 끝나면 멈추고, base 보고서 커밋을 먼저 넣은 뒤 base를 integration에 합친다.

보호된 base의 가짜 gh(test_protected_base)에 고장 스위치를 더했다. merge는 실제 git merge라 report.md가 충돌하면 병합이 실패한다.
"""
import json
import os
import sys
import unittest
from unittest import mock

import support
import test_protected_base as protected
from gs import finish, state
from support import sh

URL = protected.URL
POLICY = "base branch policy"
LIST_OPEN = """    print(next((p["url"] for p in db if p["head"] == head and p["state"] == "OPEN"), ""))\n"""
CREATED = """    save()\n    print(url)\n"""
for part in (LIST_OPEN, CREATED):
    assert part in protected.FAKE_GH
# gh.fault 한 줄: `<명령> <head 브랜치> <before|error|empty>`. 그 브랜치에 그 명령이 처음 올 때 한 번 고장 난다.
FAKE_GH = (protected.FAKE_GH
           .replace("cmd = args[1]\n", """cmd = args[1]
fault = ""
faults = here / "gh.fault"
if cmd in ("list", "create") and faults.exists():
    want, branch, kind = faults.read_text().split()
    if want == cmd and branch == opt("--head"):
        faults.unlink()
        fault = kind
if fault == "before":
    fail("HTTP 502 Bad Gateway")
""")
           .replace(LIST_OPEN, """    if opt("--state") == "merged":
        print(next((p["url"] for p in db if p["head"] == head and p["state"] == "MERGED"
                    and p["merged_head"] in opt("--jq")), ""))
    else:
        print(next((p["url"] for p in db if p["head"] == head and p["state"] == "OPEN"), ""))
""")
           .replace(CREATED, """    save()
    if fault == "error":
        fail("HTTP 502 Bad Gateway")
    if fault != "empty":
        print(url)
"""))


class Fixture(unittest.TestCase):
    P = protected.ProtectedBaseTest
    BASE, REMOTE, G = P.BASE, P.REMOTE, P.G
    tearDown, calls, rundir, integration, lines = P.tearDown, P.calls, P.rundir, P.integration, P.lines
    final_report, remote_files, protect, prs, approve = P.final_report, P.remote_files, P.protect, P.prs, P.approve
    human_merge, finish, merges, base_report = P.human_merge, P.finish, P.merges, P.base_report
    assert_no_base_push = P.assert_no_base_push

    def setUp(self, **kw):
        self.P.setUp(self, **kw)
        (self.bin / "gh").write_text(f"#!{sys.executable}\n" + FAKE_GH)

    def go(self, only="01"):
        return self.P.go(self, "--only", only)

    def add_ticket(self, tid):
        """사람이 티켓 파일을 base에 병합했다(보호 규칙 통과)."""
        with mock.patch.dict(os.environ, {"GS_FAKE_GH": "1"}):
            self.G.add_ticket(self, tid)

    def fault(self, cmd, kind, name):
        (self.bin / "gh.fault").write_text(f"{cmd} gs/demo/{name} {kind}\n")

    def assert_base_in_integration(self):
        """다음 gs go의 출발점: integration이 base(보고서 커밋 포함)를 품고, 보고서가 base판과 같다."""
        sh(self.repo, "git", "fetch", "-q", self.REMOTE)
        f = self.finish()
        sh(self.repo, "git", "merge-base", "--is-ancestor", f"{self.REMOTE}/{self.BASE}", f["head"])
        self.assertEqual(self.base_report(), self.integration("show", f"{f['head']}:{protected.REPORT}"))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "gs/demo/integration"), f["head"])

    def creates(self, branch):
        return sum(line.startswith("pr create ") and f"--head gs/demo/{branch} " in line for line in self.lines("gh.log"))


class ProtectedResumeTest(Fixture):
    def report_pending_then_new_ticket(self):
        self.protect("report")
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["phase"], "report_pending")
        pending = self.final_report()
        self.add_ticket("11")
        self.approve(2)

        code, out, err = self.go("01,11")  # 재개: 보고서 PR만 끝내고 멈춘다
        self.assertEqual(code, 1, out + err)  # 11이 남았다(gs go a b의 다음 feature로 넘어가지 않는다)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("■ 남은 티켓 1개 → 다음 gs go", out)
        self.assertIn("남은 티켓 1개 → 다음 gs go", self.messages[-1])
        self.assertEqual(state.load(self.rundir, "demo").tickets["11"].status, state.PENDING)
        self.assertEqual(len(self.prs()), 2)  # 두 번째 마무리가 없다
        self.assertEqual(self.base_report(), pending)
        self.assert_base_in_integration()

        code, out, err = self.go("01,11")  # 남은 티켓: 새 PR이 report.md에서 충돌하지 않는다
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "report_pending")
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertEqual([p["state"] for p in self.prs()], ["MERGED"] * 3 + ["OPEN"])
        self.assertIn("file_11", self.remote_files())
        self.approve(4)

        code, out, err = self.go("01,11")
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertNotIn("남은 티켓", out)
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.base_report(), self.final_report())
        self.assertFalse(sh(self.repo, "git", "branch", "--list", "gs/demo/integration"))  # 마지막 재개가 정리했다
        self.assert_no_base_push()

    def test_report_pending_then_new_ticket(self):  # v5 04 리뷰 agy [high] 경로
        self.report_pending_then_new_ticket()

    def test_report_pending_then_new_ticket_squash(self):
        self.tearDown()
        self.setUp(method="squash")
        self.report_pending_then_new_ticket()

    def test_report_pending_without_new_ticket(self):
        self.protect("report")
        self.assertEqual(self.go()[0], 1)
        self.approve(2)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertNotIn("남은 티켓", out)
        self.assertEqual(self.calls(), ["01"])
        self.assertFalse(sh(self.repo, "git", "branch", "--list", "gs/demo/integration"))
        sh(self.repo, "git", "fetch", "-q", self.REMOTE)
        sh(self.repo, "git", "merge-base", "--is-ancestor", f"{self.REMOTE}/{self.BASE}", f["head"])
        self.assertEqual(self.base_report(), self.final_report())

    def test_report_still_pending_does_not_merge_base_or_finish(self):
        self.protect("report")
        self.assertEqual(self.go()[0], 1)
        self.add_ticket("11")
        code, out, err = self.go("01,11")  # 승인 전 재개: 티켓도 시작하지 않고 그대로 기다린다
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "report_pending")
        self.assertEqual(self.calls(), ["01"])
        self.assertNotIn("남은 티켓", out)
        self.assertEqual(len(self.prs()), 2)

    def test_merge_pending_resume_stops_before_new_ticket(self):
        self.protect("integration")
        self.assertEqual(self.go()[0], 1)
        self.human_merge(1)
        self.add_ticket("11")
        code, out, err = self.go("01,11")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("■ 남은 티켓 1개 → 다음 gs go", out)
        self.assert_base_in_integration()
        self.protect()  # 새 PR까지 승인을 기다리게 하지 않는다
        code, out, err = self.go("01,11")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertEqual(self.base_report(), self.final_report())

    def test_reverted_resume_with_new_ticket_stops_then_next_go_merges(self):
        self.tearDown()
        self.setUp(break_main=True)
        self.protect("revert")
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["phase"], "revert_pending")
        self.add_ticket("11")
        self.human_merge(2)

        code, out, err = self.go("01,11")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("■ 남은 티켓 1개 → 다음 gs go", out)
        self.assertIn("\n마무리: reverted · ", self.base_report())
        self.assertNotIn("file_01", self.remote_files())
        self.assert_base_in_integration()
        self.integration("show", f"{f['head']}:file_01")  # feature 코드를 잃지 않았다(revert의 revert)

        code, out, err = self.go("01,11")  # 새 PR은 report.md에서 충돌하지 않는다. base 검증은 다시 실패한다(fixture)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertEqual(self.finish()["phase"], "revert_pending")
        self.assertEqual([(p["head"], p["state"]) for p in self.prs()][3], ("gs/demo/integration", "MERGED"))
        self.assertIn("file_11", self.remote_files())
        self.assertNotIn("충돌", out + err)


class DirectPushResumeTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = support.GoTest
    setUp, tearDown, go, calls, rundir, integration = G.setUp, G.tearDown, G.go, G.calls, G.rundir, G.integration
    add_ticket, final_report, under_report, remote_files = G.add_ticket, G.final_report, G.under_report, G.remote_files
    parallel = G.parallel

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def base_report(self):
        return sh(self.remote, "git", "show", f"main:{protected.REPORT}")

    def stop_at_merged(self):
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(self.finish()["phase"], "merged")

    def test_merged_recovery_then_new_ticket(self):
        self.stop_at_merged()
        self.add_ticket("11")
        code, out, err = self.go("--only", "01,11")
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("■ 남은 티켓 1개 → 다음 gs go", out)
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", "main"), "gs: demo 최종 보고서(병합 후)")
        self.assertEqual(self.base_report(), self.final_report())
        self.assertTrue(sh(self.repo, "git", "branch", "--list", "gs/demo/integration"))  # 다음 실행의 출발점
        sh(self.repo, "git", "merge-base", "--is-ancestor", sh(self.remote, "git", "rev-parse", "main"),
           "gs/demo/integration")

        code, out, err = self.go("--only", "01,11")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertIn("file_11", self.remote_files())
        self.assertEqual(self.base_report(), self.final_report())

    def test_merged_recovery_without_new_ticket(self):
        self.stop_at_merged()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertNotIn("남은 티켓", out)
        self.assertEqual(self.base_report(), self.final_report())
        self.assertFalse(sh(self.repo, "git", "branch", "--list", "gs/demo/integration"))

    def test_report_goes_to_base_before_base_is_merged(self):
        order = []
        real_report, real_merge = finish._report_to_base, finish.merge_base

        def report_to_base(r):
            order.append("report")
            real_report(r)

        def merge_base(r):
            order.append("merge_base")
            real_merge(r)

        with mock.patch("gs.finish._report_to_base", side_effect=report_to_base), \
                mock.patch("gs.finish.merge_base", side_effect=merge_base):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(order, ["merge_base", "report", "merge_base"])  # 첫 merge_base는 integration 준비
        self.assertEqual(self.base_report(), self.final_report())

    def test_reverted_then_new_ticket_keeps_base_report(self):
        # 되살림 커밋까지 보고서에 남기고, 그 보고서를 base에 넣은 뒤 합쳐도 report.md가 충돌하지 않는다.
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(self.base_report(), self.final_report())
        self.assertEqual(len(f["reintroduced"]), 1)
        self.assertIn(f["reintroduced"][0]["commit"], self.base_report())
        self.assertNotIn("file_01", self.remote_files())
        self.integration("show", "gs/demo/integration:file_01")

        self.add_ticket("11")
        code, out, err = self.go("--only", "01,11")
        self.assertEqual(self.finish()["phase"], "reverted", out + err)
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertIn("\n마무리: reverted · ", self.base_report())
        self.assertEqual(self.base_report(), self.final_report())
        self.assertNotIn("충돌", out + err)


class OldErrorTest(Fixture):
    def assert_no_old_error(self, *needles):
        self.assertNotIn("error", self.finish())
        for text in (self.base_report(), self.final_report()):
            for needle in needles:
                self.assertNotIn(needle, text)

    def test_merge_refusal_is_gone_after_merge_confirmed(self):
        self.protect("integration")
        self.assertEqual(self.go()[0], 1)
        self.assertIn(POLICY, self.finish()["error"])
        self.human_merge(1)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_no_old_error(POLICY)

    def test_report_refusal_is_gone_after_report_pr_merged(self):
        self.protect("report")
        self.assertEqual(self.go()[0], 1)
        self.assertIn(POLICY, self.finish()["error"])
        self.approve(2)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_no_old_error(POLICY)

    def test_revert_refusal_is_gone_after_revert_pr_merged(self):
        self.tearDown()
        self.setUp(break_main=True)
        self.protect("revert")
        self.assertEqual(self.go()[0], 1)
        self.assertIn(POLICY, self.finish()["error"])
        self.assertIn(POLICY, self.final_report())  # 기다리는 동안에는 보인다
        self.human_merge(2)
        self.assertEqual(self.go()[0], 1)
        self.assertEqual(self.finish()["phase"], "reverted")
        self.assert_no_old_error(POLICY)

    def test_transient_error_is_gone_after_report_pr_merged(self):
        self.tearDown()
        self.setUp(wait_checks=True)
        (self.bin / "checks.all").write_text(json.dumps([{"name": "test", "bucket": "pass"}]))
        (self.bin / "checks.2.error").write_text("HTTP 502 Bad Gateway")
        self.assertEqual(self.go()[0], 1)
        self.assertIn("HTTP 502", self.finish()["error"])
        (self.bin / "checks.2.error").unlink()
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assert_no_old_error("HTTP 502")


class LostSidePrTest(Fixture):
    def report_recovers(self, kind, *, created):
        self.fault("create", kind, "report")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending", f)
        self.assertNotIn("report_pr", f)
        self.assertFalse(f.get("base_report_tried"))
        self.assertIn("gs/demo/report", f["outcome"])
        self.assertEqual(len(self.prs()), 2 if created else 1)
        self.assertIn("gs/demo/report", self.messages[-1])

        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(f["outcome"], "integration·main 검증 통과, PR 병합 완료")
        self.assertEqual(f["report_pr"], URL.format(2))
        self.assertTrue(f["base_report_tried"])
        self.assertNotIn("error", f)
        self.assertEqual(self.creates("report"), 1 if created else 2)
        self.assertEqual([p["state"] for p in self.prs()], ["MERGED", "MERGED"])
        self.assertIn("\n마무리: verified · ", self.base_report())
        self.assertEqual(self.base_report(), self.final_report())
        self.assert_no_base_push()

    def test_create_error_after_github_made_the_pr(self):
        self.report_recovers("error", created=True)

    def test_create_empty_output_after_github_made_the_pr(self):
        self.report_recovers("empty", created=True)

    def test_create_really_failed_is_created_next_time(self):
        self.report_recovers("before", created=False)

    def test_list_error_stays_pending(self):
        self.fault("list", "before", "report")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending")
        self.assertFalse(f.get("base_report_tried"))
        self.assertEqual(len(self.prs()), 1)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.creates("report"), 1)
        self.assertEqual(self.finish()["phase"], "verified")

    def test_human_merged_the_lost_pr(self):
        self.fault("create", "error", "report")
        self.assertEqual(self.go()[0], 1)
        self.human_merge(2)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(f["report_pr"], URL.format(2))
        self.assertEqual(self.creates("report"), 1)
        self.assertEqual(self.base_report(), self.final_report())

    def test_lost_pr_with_new_ticket_stops_after_resume(self):
        self.fault("create", "error", "report")
        self.assertEqual(self.go()[0], 1)
        self.add_ticket("11")
        code, out, err = self.go("01,11")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("■ 남은 티켓 1개 → 다음 gs go", out)
        self.assert_base_in_integration()
        code, out, err = self.go("01,11")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertEqual(self.base_report(), self.final_report())

    def test_interrupted_before_pr_saved_resumes_report_pending(self):
        real = finish._gh

        def gh(r, *args, **kw):
            if args[0] == "create" and "gs/demo/report" in args:
                real(r, *args, **kw)
                raise RuntimeError("interrupted")
            return real(r, *args, **kw)

        with mock.patch("gs.finish._gh", side_effect=gh):
            code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending")
        self.assertNotIn("report_pr", f)
        self.assertEqual(len(self.prs()), 2)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assertEqual(self.creates("report"), 1)

    def revert_recovers(self, kind):
        self.tearDown()
        self.setUp(break_main=True)
        self.fault("create", kind, "revert")
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "revert_pending", f)
        self.assertNotIn("revert_pr", f)
        self.assertEqual(f["revert_head"], f["revert_sha"])
        self.assertIn("gs/demo/revert", f["outcome"])
        self.assertEqual([p["head"] for p in self.prs()], ["gs/demo/integration", "gs/demo/revert"])
        self.assertIn("file_01", self.remote_files())
        sha = f["revert_sha"]

        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)  # reverted는 실패다
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual((f["revert_sha"], f["revert_pr"]), (sha, URL.format(2)))
        self.assertNotIn("error", f)
        self.assertEqual(self.creates("revert"), 1)
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(self.base_report(), self.final_report())
        self.assert_no_base_push()

    def test_revert_create_error_after_github_made_the_pr(self):
        self.revert_recovers("error")

    def test_revert_create_empty_output_after_github_made_the_pr(self):
        self.revert_recovers("empty")


if __name__ == "__main__":
    unittest.main()
