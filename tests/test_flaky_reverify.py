"""goldstack-v43 02: 판별에서 따로 통과한 파일만 판별 뒤 전체 실행에서 다시 실패하면 수리 대신 같은 트리를 한 번 다시 검증한다(go._flaky_files, go._verify_flaky).

가짜 verify는 n번째 전체 실행이 무엇을 할지 정한다(실패면 unittest 실패 줄을 찍는다). 판별 명령(config `[verify] rerun`)은 받은 값을 rerun.calls에 적고 통과한다.
`[verify]`는 main checkout의 config에만 적는다(실행 중인 config로 판별한다). 가짜 worker·리뷰어는 test_verify_repair.Base의 것이다. 시간에 기대지 않는다.
"""
import json
import unittest

import support
import test_verify_repair
from test_verify_repair import HANG, TERM_SELF

from gs import config, go, state

FAILED_FILE = r"^(?:FAIL|ERROR): \S+ \((test_\w+)\."
GOOD = 'echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"'
IN_DIFF = 'mkdir -p tests; echo x > tests/test_a.py; git add -A; git commit -qm "t$GS_TICKET"'  # 실패할 시험 파일을 티켓이 바꾼다
REPAIR = 'echo fixed > "repaired_$GS_TICKET"; git add -A; git commit -qm "repair $GS_TICKET"'
ONCE = "수리 없이 같은 트리로 한 번 다시 검증한다"


def fail(*modules):
    """unittest 실패 줄을 찍고 1로 끝나는 셸 조각."""
    return "".join(f"echo 'FAIL: test_x ({m}.Case.test_x)'; " for m in modules) + "exit 1"


class Base(test_verify_repair.Base):
    def setUp(self):
        super().setUp()
        with (self.repo / config.CONFIG_PATH).open("a") as f:
            f.write(f"\n[verify]\nfailed_file = '{FAILED_FILE}'\nrerun = \"echo {{file}} >> {self.bin}/rerun.calls\"\n")

    def verifies(self, *runs, retries=0):
        """n번째 티켓 전체 검증(미완 병합에서 돈다)은 runs[n-1]을 돌고, 넘어간 검증은 통과한다. 마무리 검증은 세지 않고 통과한다. 판별 실행도 세지 않는다(다른 명령이다)."""
        cases = "".join(f"  {n}) {run} ;;\n" for n, run in enumerate(runs, 1))
        (self.bin / "verify.sh").write_text(f'here="{self.bin}"\ngit rev-parse -q --verify MERGE_HEAD >/dev/null || exit 0\n'
                                            'n=$(( $(cat "$here/verifies" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/verifies"\n'
                                            f'case $n in\n{cases}esac\nexit 0\n')
        support.sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        spec = self.repo / ".goldstack/work/demo/spec.md"
        spec.write_text(f"---\nfeature: demo\nverify: bash {self.bin / 'verify.sh'}\nmax_workers: 1\nverify_retries: {retries}\n---\n")
        support.sh(self.repo, "git", "commit", "-qm", "verify", "--", str(spec))  # `[verify]`를 적은 config는 커밋하지 않는다
        support.sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def full_runs(self):
        return int((self.bin / "verifies").read_text())

    @property
    def log(self):
        return self.rundir / "01/1/verify.log"

    def flaky_line(self, files):
        return f"\nflaky: ticket-01 {files} {go.FLAKY_AGAIN}. 따로 돌려 통과, 전체 다시 통과\n"

    def assert_merged_as_flaky(self, files="test_a"):
        """수리 worker도 새 시도도 없이 flaky 다시 검증으로 병합했다. 로그·티켓 결과·보고서에 flaky가 남았다."""
        ts = self.ts()
        reason = f"{go.FLAKY_AGAIN}: {files}(로그 {self.log})"
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume, ts.repairs, ts.reason),
                         ("merged", 1, 0, {}, [], reason))
        self.assertEqual(self.calls(), ["01"])  # 수리 worker도 새 시도도 없다
        self.assertEqual(self.reviewers(), ["codex"])  # 수리 재리뷰도 없다
        self.assertFalse((self.rundir / "01/1/repair").exists())
        text = self.log.read_text()
        self.assertIn(self.flaky_line(files), text)
        self.assertIn(f"\n판별 통과 파일만 전체에서 다시 실패했다({files}). 같은 트리로 다시 돌린다\n$ bash", text)
        report = self.final_report()
        self.assertIn(f"- flaky: 01 티켓 검증 {files} {go.FLAKY_AGAIN}. (따로 돌려 통과, 전체 다시 통과)", report)  # 보고서 flaky 목록
        self.assertIn(f"| merged | {reason}", report)  # 티켓별 결과
        return ts

    def assert_repaired(self, out):
        """flaky 다시 검증 없이 수리 worker가 떠 수리 뒤 검증으로 병합했다."""
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("merged", 1, 0, {}))
        self.assertEqual(self.calls(), ["01", "01"])
        [rec] = ts.repairs
        self.assertEqual((rec["verify_log"], rec["reason"], rec["result"]), (str(self.log), f"검증 실패(로그 {self.log})", state.REPAIR_PASSED))
        self.assertNotIn(ONCE, out)
        self.assertNotIn(go.FLAKY_AGAIN, self.log.read_text())
        return ts


class FlakyReverifyTest(Base):
    def test_triaged_file_failing_again_is_verified_again_instead_of_repaired(self):
        # (a) v42 01 모양: 첫 전체 실패 → 판별 통과 → 전체 다시 같은 파일 실패 → 수리 없이 다시 검증 → 통과해 병합
        self.verifies(fail("test_a"), fail("test_a"))
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_merged_as_flaky()
        self.assertEqual((self.full_runs(), self.lines("rerun.calls")), (3, ["test_a"]))  # 다시 검증은 바로 통과해 판별하지 않았다
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed"), ("ticket-01", "failed"), ("ticket-01", "passed")])
        self.assertIn(f"[01] 판별 통과 파일만 전체에서 다시 실패(test_a, 로그 {self.log}) → {ONCE}", out)
        self.assertEqual(out.count(ONCE), 1)
        # 다시 검증은 같은 트리를 본다
        rows = [x for x in state.load(self.rundir, "demo").metrics["validations"] if x["label"] == "ticket-01"]
        self.assertEqual(len({(x["tree_sha"], x["ticket_head"]) for x in rows}), 1)
        # 첫 검증의 증거를 덮지 않고 이어 쓴다. 다시 검증의 종료 코드 뒤에 flaky 줄이 온다
        text = self.log.read_text()
        self.assertEqual(text.count("종료 코드: 1\n"), 2, text)
        self.assertTrue(text.endswith("\n종료 코드: 0\n" + self.flaky_line("test_a")), text)

    def test_failing_file_inside_the_ticket_diff_is_repaired(self):
        # (b) 실패 파일을 티켓이 바꿨다(tests/test_a.py): 코드 결함일 수 있으니 지금처럼 수리
        self.verifies(fail("test_a"), fail("test_a"))
        self.worker(IN_DIFF, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_repaired(out)
        self.assertEqual((self.full_runs(), self.lines("rerun.calls")), (3, ["test_a"]))

    def test_failing_file_not_triaged_is_repaired(self):
        # (c) 판별 뒤 전체 실행의 실패에 따로 통과하지 않은 파일(test_b)이 섞였다
        self.verifies(fail("test_a"), fail("test_a", "test_b"))
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_repaired(out)
        self.assertEqual(self.lines("rerun.calls"), ["test_a"])

    def test_no_failed_file_in_the_last_run_is_repaired(self):
        # 판별 뒤 전체 실행의 출력에서 실패 파일을 뽑지 못했다(import 오류 같은 모양)
        self.verifies(fail("test_a"), "echo boom; exit 1")
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_repaired(out)

    def test_failing_again_on_the_second_run_goes_to_repair_once(self):
        # (d) 다시 검증도 같은 모양으로 실패한다: flaky 다시 검증을 또 하지 않고 수리로 간다
        self.verifies(fail("test_a"), fail("test_a"), fail("test_a"), fail("test_a"))
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume, ts.reason), ("merged", 1, 0, {}, ""))
        self.assertEqual(self.calls(), ["01", "01"])  # 수리 worker가 떴다
        self.assertEqual(out.count(ONCE), 1)
        self.assertEqual((self.full_runs(), self.lines("rerun.calls")), (5, ["test_a", "test_a"]))  # 다시 검증도 판별했다
        [rec] = ts.repairs
        self.assertEqual((rec["verify_log"], rec["result"]), (str(self.log), state.REPAIR_PASSED))
        self.assertIn("같은 브랜치에서 수리한다", out)
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed")] * 4 + [("ticket-01-repair", "passed")])
        self.assertNotIn(go.FLAKY_AGAIN, self.log.read_text())  # 다시 검증이 통과하지 않았다


class LogBoundaryTest(Base):
    """(f) 판별 뒤 전체 실행의 출력만 읽는다. 같은 로그의 앞 실행·앞 재시도의 실패 파일을 합쳐 읽지 않는다.

    첫 시험(A·B → C)은 첫 실행만 읽거나 판별 파일과 겹치기만 보는 구현을 잡는다. 판별 파일 전체가 첫 실행의 실패라 모두 합쳐 읽어도 C 때문에 수리로 가서,
    합쳐 읽는 구현은 둘째 시험(앞 재시도의 test_a가 마지막 판별 밖)이 잡는다."""

    def test_last_run_failing_another_file_is_repaired(self):
        self.verifies(fail("test_a", "test_b"), fail("test_c"))
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_repaired(out)
        self.assertEqual(self.lines("rerun.calls"), ["test_a", "test_b"])

    def test_failures_of_an_earlier_retry_do_not_count(self):
        # 재시도 1: test_a 판별 통과, 전체 다시 test_b 실패 → 재시도 2: test_b 판별 통과, 전체 다시 test_b 실패.
        # 마지막 실행의 실패(test_b)는 마지막 판별이 따로 통과시킨 파일이다. 앞 재시도의 test_a를 합쳐 읽으면 수리로 간다
        self.verifies(fail("test_a"), fail("test_b"), fail("test_b"), fail("test_b"), retries=1)
        self.worker(GOOD, REPAIR)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_merged_as_flaky("test_b")
        self.assertEqual((self.full_runs(), self.lines("rerun.calls")), (5, ["test_a", "test_b"]))
        self.assertIn("\n검증 재시도 1\n", self.log.read_text())


class ResumeTest(Base):
    """(e) 다시 검증 도중 멈추면 다음 gs go가 다시 검증부터 잇고, 그 결과를 flaky 다시 검증의 규칙으로 처리한다."""

    def assert_resumed_as_flaky(self, out):
        self.assertIn("[01] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 판별 통과 파일만 다시 실패한 검증을 같은 worktree에서 다시 한다", out)
        self.assertIn("[01] 지난 검증은 판별 통과 파일만 다시 실패했다. 같은 worktree에서 다시 검증부터 잇는다", out)

    def test_gs_killed_during_the_second_run_continues_with_it(self):
        self.verifies(fail("test_a"), fail("test_a"), HANG)
        self.worker(GOOD, REPAIR)
        group = self.gs_killed_in_verify("01/1/verify.log")  # 다시 검증은 첫 검증의 로그에 이어 쓴다
        mark = self.ts().network_resume
        self.assertEqual((self.ts().status, mark["verify_again"], mark["flaky_files"], mark["done"]),
                         ("running", go.AGAIN_FLAKY, ["test_a"], True))
        code, out, err = self.go("--only", "01")
        self.assert_stale_ended(group, out)
        self.assertEqual(code, 0, out + err)
        self.assert_resumed_as_flaky(out)
        self.assert_merged_as_flaky()  # 구현·리뷰·수리를 다시 하지 않았다. 끊김의 다시 검증이었으면 이유가 `검증 끊김 뒤`다
        self.assertEqual(self.full_runs(), 4)
        self.assertEqual(self.log.read_text().count("같은 트리로 다시 돌린다\n"), 2)

    def test_interrupted_second_run_after_a_restart_gets_its_own_second_run(self):
        # 끊김의 다시 검증이었으면 또 끊긴 것이라 실패다. flaky 다시 검증의 끊김은 첫 끊김이다.
        # 끊김의 다시 검증으로 바뀌어도 flaky 판정의 파일을 들고 가서, 통과하면 flaky 줄이 남는다(수리를 건너뛴 병합이 보고서에 보인다)
        self.verifies(fail("test_a"), fail("test_a"), TERM_SELF)
        self.worker(GOOD, REPAIR)
        self.stop_at_verify()
        self.assertEqual(self.ts().network_resume["verify_again"], go.AGAIN_FLAKY)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_resumed_as_flaky(out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume, ts.repairs), ("merged", 1, 0, {}, []))
        self.assertEqual(self.calls(), ["01"])
        reason = f"{go.FLAKY_AGAIN}: test_a, 검증 끊김 뒤 다시 검증 통과(로그 {self.log})"
        self.assertEqual(ts.reason, reason)
        self.assertIn(f"검증 끊김(종료 코드 ", out)
        self.assertEqual(self.ticket_verifies(), [("ticket-01", "failed")] * 2 + [("ticket-01-끊김", "failed"), ("ticket-01", "passed")])
        text = self.log.read_text()
        self.assertIn("\n끊긴 검증을 같은 트리로 다시 돌린다\n", text)
        self.assertTrue(text.endswith("\n종료 코드: 0\n" + self.flaky_line("test_a")), text)
        report = self.final_report()
        self.assertIn(f"- flaky: 01 티켓 검증 test_a {go.FLAKY_AGAIN}. (따로 돌려 통과, 전체 다시 통과)", report)
        self.assertIn(f"| merged | {reason}", report)

    def test_ordinary_failure_after_a_restart_goes_to_repair(self):
        self.verifies(fail("test_a"), fail("test_a"), fail("test_a"), fail("test_a"))
        self.worker(GOOD, REPAIR)
        self.stop_at_verify()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_resumed_as_flaky(out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.network_resume), ("merged", 1, 0, {}))
        self.assertEqual(self.calls(), ["01", "01"])  # 수리 worker. flaky 다시 검증을 또 하지 않았다
        self.assertEqual(ts.repairs[0]["result"], state.REPAIR_PASSED)
        self.assertEqual(self.full_runs(), 5)
        self.assertNotIn(ONCE, out)  # 재개한 실행에서는 다시 검증을 새로 정하지 않았다


class OldMarkTest(Base):
    def test_old_true_mark_is_the_second_run_of_an_interruption(self):
        # (g) 옛 gs가 남긴 verify_again: true는 끊김의 다시 검증이다: 또 끊기면 그 시도는 실패다(flaky 다시 검증이었으면 한 번 더 돈다)
        self.verifies(TERM_SELF, TERM_SELF)
        self.worker(GOOD, REPAIR)
        self.stop_at_verify()
        path = state.path(self.rundir)
        raw = json.loads(path.read_text())
        mark = raw["tickets"]["01"]["network_resume"]
        self.assertEqual(mark["verify_again"], go.AGAIN_INTERRUPTED)
        mark["verify_again"] = True  # 옛 gs가 쓴 표시
        path.write_text(json.dumps(raw, ensure_ascii=False))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("[01] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 끊긴 검증을 같은 worktree에서 다시 한다", out)
        self.assertIn("[01] 지난 검증이 끊겼다. 같은 worktree에서 다시 검증부터 잇는다", out)
        ts = self.ts()
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.repairs), ("merged", 2, 1, []))
        self.assertIn("다시 검증도 끊겼다", (self.rundir / "01/1/failure.log").read_text())
        self.assertEqual(self.ticket_verifies(), [("ticket-01-끊김", "failed")] * 2 + [("ticket-01", "passed")])
        self.assertNotIn(go.FLAKY_AGAIN, self.log.read_text())


class InDiffTest(unittest.TestCase):
    """판별 값과 티켓 diff의 바뀐 경로 대조(go._in_diff). 넓게 맞으면 수리로 갈 뿐이라 놓치지 않는 쪽을 본다."""

    def test_matches(self):
        for name, paths in (("test_a", ["tests/test_a.py"]), ("test_a", ["test_a.py"]), ("test_a.py", ["tests/test_a.py"]),
                            ("pkg.test_a", ["tests/pkg/test_a.py"]), ("test_a.Case", ["tests/test_a.py"]),
                            ("test_a", ["src/x.py", "tests/sub/test_a.py", ""])):
            with self.subTest(name=name, paths=paths):
                self.assertTrue(go._in_diff(name, paths))

    def test_does_not_match(self):
        for name, paths in (("test_a", ["tests/test_ab.py"]), ("test_a", ["tests/my_test_a.py"]), ("test_a", ["test_a_dir/x.py"]),
                            ("test_a", []), ("test_a", [""])):
            with self.subTest(name=name, paths=paths):
                self.assertFalse(go._in_diff(name, paths))
