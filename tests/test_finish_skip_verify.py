"""goldstack-v41 01: 마무리 integration 전체 검증은 이번 실행이 이미 전체 검증한 트리면 건너뛴다(finish._skip_reason).

가짜 worker로 gs go를 끝까지 돈다. verify는 돈 자리(티켓 병합 전·integration·main)를 bin/verifies에 한 줄씩 적는다.
티켓 31·34는 spec `verify`(전체 검증), 32·33은 티켓 `verify`(좁은 검증)로 검증한다. 가짜 worker는 `file_<id>` 하나를 커밋한다.
병합 뒤 base 검증 건너뛰기(`_same_as_verified`)는 진짜를 쓴다: 건너뛴 integration 검증이 남긴 `verified_head`를 그대로 잇는지 본다.
"""
import json
import subprocess
import textwrap
import unittest
from unittest import mock

import support
from gs import git, metrics, state
from support import sh

URL = "https://example.test/pr/1"
VERIFIED = f"마무리: verified · PR {URL} 병합 · main 검증 통과"


class SkipIntegrationVerifyTest(support.GoTest):
    POSTMERGE_SKIP = True  # 병합 뒤 첫 base 검증 건너뛰기도 진짜로 돈다

    def setUp(self):
        super().setUp()
        (self.bin / "verify.sh").write_text(textwrap.dedent(f"""\
            here="{self.bin}"
            if git rev-parse -q --verify MERGE_HEAD >/dev/null; then where=ticket
            elif git symbolic-ref -q HEAD >/dev/null; then where=integration
            else where=main; fi
            echo "$where${{1:+ $1}}" >> "$here/verifies"
            test ! -f BROKEN
            """))
        self.full = f"bash {self.bin / 'verify.sh'}"
        self.narrow = f"{self.full} narrow"
        fdir = self.repo / ".goldstack/work/demo"
        (fdir / "spec.md").write_text(f"---\nfeature: demo\nverify: {json.dumps(self.full)}\nmax_workers: 1\n---\n")
        self.write_ticket("31")
        self.write_ticket("32", deps='["31"]', touches=["docs/", "file_*2"], verify=self.narrow)  # glob·디렉터리 touches
        self.write_ticket("33", deps='["31"]', touches=["docs/"], verify=self.narrow)  # file_33은 touches 밖이다
        self.write_ticket("34", deps='["31"]')
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "skip verify tickets")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def write_ticket(self, tid, deps="[]", touches=None, verify=None):
        extra = "".join(f"{key}: {json.dumps(value)}\n" for key, value in (("touches", touches), ("verify", verify))
                        if value is not None)
        text = support.ticket(tid, deps).replace("reviewer: codex\n", "reviewer: codex\n" + extra)
        (self.repo / ".goldstack/work/demo/tickets" / f"{tid}-t.md").write_text(text)

    def commit_tickets(self):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "more tickets")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def verifies(self, where="integration"):
        return [line for line in self.lines("verifies") if line == where]

    def log(self):
        return (self.rundir / "finish/integration-verify.log").read_text()

    def finish(self):
        return state.load(self.rundir, "demo").finish

    def merge_commit(self, tid):
        """integration의 티켓 tid 병합 커밋(첫 부모 줄)."""
        found = self.integration("log", "--first-parent", "--format=%H", f"--grep=^Merge {tid}:", "gs/demo/integration")
        self.assertEqual(len(found.split()), 1, found)
        return found

    def tree(self, rev):
        return sh(self.repo, "git", "rev-parse", f"{rev}^{{tree}}")

    def assert_skipped(self, reason, head):
        """건너뜀: integration 검증 명령은 돌지 않고, 근거 한 줄과 통과했을 때의 기록이 남는다. 측정 표에 integration 줄이 없다."""
        self.assertEqual(self.verifies(), [])
        self.assertEqual(self.log(), f"integration: {reason}, 건너뜀\n")
        f = self.finish()
        self.assertEqual((f["phase"], f["integration_ok"], f["verified_head"]), ("verified", True, head))
        self.assertEqual(f["integration_skipped"], reason)
        report = self.final_report()
        self.assertIn(f"\n\n{VERIFIED}\nintegration 검증 건너뜀: {reason}\n", report)
        labels = [x["label"] for x in state.load(self.rundir, "demo").metrics["validations"]]
        self.assertNotIn("integration", labels)
        self.assertNotIn("| integration |", report)
        # base 검증도 verified_head(건너뛴 integration 끝)와 병합 커밋이 보고서만 달라 건너뛴다(_same_as_verified 그대로)
        self.assertEqual(self.verifies("main"), [])
        self.assertEqual((self.rundir / "finish/main-verify.log").read_text(), f"integration과 같은 코드({head}), 건너뜀\n")

    def assert_verified(self, count=1, phase="verified"):
        """검증함: integration 검증 명령이 count번 돌고 로그는 그 명령의 로그다. 건너뜀 줄은 어디에도 없다."""
        self.assertEqual(len(self.verifies()), count, self.lines("verifies"))
        self.assertTrue(self.log().startswith(f"$ {self.full}\nHEAD: "), self.log())
        f = self.finish()
        self.assertEqual(f["phase"], phase)
        self.assertNotIn("integration_skipped", f)
        self.assertNotIn("integration 검증 건너뜀", self.final_report())
        self.assertIn("integration", [x["label"] for x in state.load(self.rundir, "demo").metrics["validations"]])

    def interrupt_finish(self, *only):
        """마무리가 integration 판정 뒤, 보고서 커밋 전에 git 오류로 멈춘다. 다음 gs go는 마무리를 새로 시작한다."""
        with mock.patch("gs.finish._commit_report", side_effect=git.GitError("보고서 커밋 실패(시험)")):
            code, out, err = self.go("--only", ",".join(only))
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "preparing")
        return out

    # (a) 마지막 티켓이 전체 검증 → 같은 트리
    def test_a_last_full_verify_same_tree_skips(self):
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket"])
        head = self.merge_commit("31")
        self.assert_skipped("ticket-31 전체 검증과 같은 트리", head)
        self.assertIn("■ integration: ticket-31 전체 검증과 같은 트리, 건너뜀", out)

    # (b) 전체 검증 뒤 좁은 검증 티켓 하나 → 그 티켓 touches 안이면 건너뜀
    def test_b_narrow_ticket_inside_touches_after_full_skips(self):
        code, out, err = self.go("--only", "31,32")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket", "ticket narrow"])
        self.assert_skipped("ticket-31 전체 검증 뒤 좁은 검증 티켓(32)만 바뀜", self.merge_commit("32"))

    # (c) 좁은 검증 티켓이 touches 밖 파일을 바꿈 → 검증
    def test_c_narrow_ticket_outside_touches_verifies(self):
        code, out, err = self.go("--only", "31,33")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies")[:2], ["ticket", "ticket narrow"])
        self.assert_verified()
        self.assertIn(f"HEAD: {self.merge_commit('33')}\n", self.log())

    # 티켓 id가 라벨 접미어(`-repair`)로 끝난다: 접미어를 떼어 낸 다른 티켓(32)의 touches로 보지 않는다
    def test_c_repair_id_label_of_two_tickets_verifies(self):
        """32-repair의 검증 라벨 `ticket-32-repair`는 32의 수리 검증 라벨이기도 하다. 둘 다 좁은 검증이면 어느 touches인지 몰라 검증한다."""
        self.write_ticket("32", deps='["31"]', touches=["file_*"], verify=self.narrow)
        self.write_ticket("32-repair", deps='["31"]', touches=["docs/"], verify=self.narrow)  # file_32-repair는 touches 밖
        self.commit_tickets()
        code, out, err = self.go("--only", "31,32-repair")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies")[:2], ["ticket", "ticket narrow"])
        self.assert_verified()
        self.assertIn(f"HEAD: {self.merge_commit('32-repair')}\n", self.log())

    def test_c_repair_id_uses_its_own_touches_verifies(self):
        """32는 전체 검증이라 좁은 검증 기록 `ticket-32-repair`는 32-repair의 것이다. 그 touches(docs/) 밖이니 검증한다."""
        self.write_ticket("32", deps='["31"]', touches=["file_*"])
        self.write_ticket("32-repair", deps='["31"]', touches=["docs/"], verify=self.narrow)
        self.commit_tickets()
        code, out, err = self.go("--only", "31,32-repair")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies")[:2], ["ticket", "ticket narrow"])
        self.assert_verified()

    def test_b_repair_id_of_full_verify_prefix_skips(self):
        """32는 전체 검증이라 좁은 검증 기록 `ticket-32-repair`는 32-repair의 것이다. 그 touches 안이니 건너뛴다."""
        self.write_ticket("32", deps='["31"]', touches=["file_*"])
        self.write_ticket("32-repair", deps='["31"]', touches=["file_32-*"], verify=self.narrow)
        self.commit_tickets()
        code, out, err = self.go("--only", "31,32-repair")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket", "ticket narrow"])
        self.assert_skipped("ticket-31 전체 검증 뒤 좁은 검증 티켓(32-repair)만 바뀜", self.merge_commit("32-repair"))

    def test_b_repair_id_inside_its_touches_skips(self):
        """접두 티켓(35)이 없는 35-repair의 좁은 검증 기록도 35-repair의 touches로 본다."""
        self.write_ticket("35-repair", deps='["31"]', touches=["file_35*"], verify=self.narrow)
        self.commit_tickets()
        code, out, err = self.go("--only", "31,35-repair")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket", "ticket narrow"])
        self.assert_skipped("ticket-31 전체 검증 뒤 좁은 검증 티켓(35-repair)만 바뀜", self.merge_commit("35-repair"))

    # (d) 전체 검증 기록 없음 → 검증
    def test_d_no_full_verify_record_verifies(self):
        code, out, err = self.go("--only", "32")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies")[:1], ["ticket narrow"])
        self.assert_verified()

    def test_d_records_without_tree_verify(self):
        """옛 state: 검증 기록에 tree_sha가 비었다. 트리로 잇지 못하니 검증한다."""
        real = metrics.validation

        def without_tree(*args, **kwargs):
            return real(*args, **{**kwargs, "tree_sha": ""})

        with mock.patch("gs.metrics.validation", side_effect=without_tree):
            code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        records = state.load(self.rundir, "demo").metrics["validations"]
        self.assertEqual([(x["label"], x["accepted"], x["tree_sha"]) for x in records if x["label"] == "ticket-31"],
                         [("ticket-31", True, "")])
        self.assert_verified()

    def test_dirty_integration_worktree_verifies(self):
        """마무리가 판정할 때 integration worktree가 깨끗하지 않으면 검증한다(그 검증은 지금처럼 트리 변경으로 떨어진다)."""
        def dirty(r):  # 마무리의 첫 일(_run 맨 앞)에 untracked 파일을 남긴다
            (r.iwt / "stray").write_text("x\n")

        with mock.patch("gs.finish.sync_issues", side_effect=dirty):
            code, out, err = self.go("--only", "31")
        self.assertEqual(code, 1, out + err)
        self.assert_verified(phase="not_merged")
        self.assertIn("검증 중 worktree가 바뀌었다", self.log())

    # (e) 전체 검증 뒤 기록과 맞지 않는 커밋(base 합치기)이 낌 → 검증
    def test_e_base_merge_after_full_verify_verifies(self):
        self.interrupt_finish("31")
        self.assertEqual(self.verifies(), [])  # 멈춘 마무리는 건너뛰었다
        self.someone("echo other > other.txt", "git add other.txt", "git commit -qm other")
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        head = self.finish()["verified_head"]
        self.assertEqual(sh(self.repo, "git", "log", "-1", "--format=%P", head).split()[0], self.merge_commit("31"))
        self.assertNotEqual(self.tree(head), self.tree(self.merge_commit("31")))  # base를 합친 커밋
        self.assert_verified()
        self.assertIn(f"HEAD: {head}\n", self.log())

    # (f) 받아들여진 전체 검증의 트리가 integration 이력에 없음(병합 취소) → 그 기록을 쓰지 않음
    def test_f_cancelled_merge_record_is_not_used(self):
        real = git.run

        def refuse_31(cwd, *args, **kwargs):  # 검증 통과 뒤 브랜치 옮기기가 실패해 31의 병합이 취소된다(go._merge_stage)
            if args[:3] == ("update-ref", "-m", "gs: merge 31"):
                return subprocess.CompletedProcess(["git", *args], 1, "", "moved")
            return real(cwd, *args, **kwargs)

        self.write_ticket("32", touches=["file_32"], verify=self.narrow)  # 31에 막히지 않는다
        sh(self.repo, "git", "commit", "-qam", "32 unblocked")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        with mock.patch("gs.git.run", side_effect=refuse_31):
            code, out, err = self.go("--only", "31,32")
        self.assertEqual(code, 1, out + err)
        st = state.load(self.rundir, "demo")
        self.assertEqual((st.tickets["31"].status, st.tickets["32"].status), (state.FAILED, state.MERGED))
        cancelled = {x["tree_sha"] for x in st.metrics["validations"] if x["label"] == "ticket-31" and x["accepted"]}
        self.assertTrue(cancelled)
        history = set(self.integration("log", "--first-parent", "--format=%T", "gs/demo/integration").split())
        self.assertFalse(cancelled & history)
        self.assert_verified()
        self.assertIn(f"HEAD: {self.merge_commit('32')}\n", self.log())

    # (g) 재개 → 같은 판정
    def test_g_resumed_finish_keeps_skip(self):
        """병합 대기에서 멈춘 마무리를 다음 gs go가 잇는다. 남긴 verified_head·근거로 base 검증까지 그대로 건너뛴다."""
        (self.bin / "gh.queue").write_text("")  # 병합 명령은 성공했지만 PR이 아직 열려 있다
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        self.assertEqual(self.verifies(), [])
        head = self.merge_commit("31")
        self.assertEqual((self.finish()["verified_head"], self.finish()["integration_skipped"]),
                         (head, "ticket-31 전체 검증과 같은 트리"))
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("verifies"), ["ticket"])
        self.assert_skipped("ticket-31 전체 검증과 같은 트리", head)

    def test_g_interrupted_after_report_commit_keeps_skip(self):
        """보고서 커밋 뒤 push에서 멈춘 마무리. integration 끝이 보고서 커밋이라 맞는 트리가 없지만, 다음 gs go는 남긴 근거로 그대로 건너뛴다."""
        reason = "ticket-31 전체 검증과 같은 트리"
        with mock.patch("gs.finish._push", side_effect=git.GitError("push 실패(시험)")):
            code, out, err = self.go("--only", "31")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual((self.finish()["phase"], self.finish()["integration_skipped"]), ("preparing", reason))
        self.assertEqual(self.verifies(), [])
        report_commit = self.integration("rev-parse", "gs/demo/integration")
        self.assertEqual(self.integration("log", "-1", "--format=%s", report_commit), "gs: demo 최종 보고서")
        self.assertEqual(self.integration("rev-parse", f"{report_commit}^"), self.merge_commit("31"))
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"■ integration: {reason}, 건너뜀", out)
        self.assertEqual(self.lines("verifies"), ["ticket"])
        self.assert_skipped(reason, report_commit)

    def test_g_interrupted_after_report_then_code_commit_verifies(self):
        """보고서 커밋 뒤 멈춘 마무리 위에 보고서 밖 커밋이 더해졌으면 남긴 근거를 쓰지 않고 검증한다."""
        with mock.patch("gs.finish._push", side_effect=git.GitError("push 실패(시험)")):
            code, out, err = self.go("--only", "31")
        self.assertNotEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "preparing")
        iwt = self.rundir / "wt/integration"
        (iwt / "file_extra").write_text("extra\n")
        sh(iwt, "git", "add", "file_extra")
        sh(iwt, "git", "commit", "-qm", "extra")
        extra = sh(iwt, "git", "rev-parse", "HEAD")
        code, out, err = self.go("--only", "31")
        self.assertEqual(code, 0, out + err)
        self.assert_verified()
        self.assertIn(f"HEAD: {extra}\n", self.log())

    def test_g_restarted_finish_judges_same(self):
        """보고서 커밋 전에 멈춘 마무리는 다음 gs go가 새로 시작해 같은 트리로 다시 판정한다."""
        out = self.interrupt_finish("31", "34")
        reason = "ticket-34 전체 검증과 같은 트리"
        self.assertIn(f"■ integration: {reason}, 건너뜀", out)
        code, out, err = self.go("--only", "31,34")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"■ integration: {reason}, 건너뜀", out)
        self.assertEqual(self.lines("verifies"), ["ticket", "ticket"])
        self.assert_skipped(reason, self.merge_commit("34"))


if __name__ == "__main__":
    unittest.main()
