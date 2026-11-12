"""보고서: 깨끗이 통과한 검증은 한 줄, 요약 입력의 티켓 병합 사실(git)."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from gs import git, report, state
import support

PASS = "$ check\nlots of passing output\nOK\n\n종료 코드: 0\n"
FAIL = "$ check\nFAILED one\n\n종료 코드: 1\n"
TAIL = "lots of passing output"


def call(label, *, code=0, ok=True, result="passed", changed=False, seconds=12.34, retry=1, **extra):
    return {"label": label, "command": "check", "retry": retry, "seconds": seconds, "code": code, "ok": ok,
            "timed_out": result == "timeout", "tree_changed": changed, "accepted": ok and not changed,
            "result": result, **extra}


class Base(unittest.TestCase):
    def setUp(self):
        support.isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        for key, value in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            self.git("config", key, value)
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        self.git("branch", "base")
        self.rundir = self.repo / ".goldstack/work/demo/run"
        (self.rundir / "finish").mkdir(parents=True)
        self.st = state.State(feature="demo", finish={"phase": "verified", "integration_ok": True, "main_ok": True})
        self.r = SimpleNamespace(st=self.st, name="demo", order=[], repo=self.repo, iwt=self.repo, rundir=self.rundir,
                                 base="main", base_ref="base", remote="origin",
                                 feat=SimpleNamespace(tickets={}, spec=SimpleNamespace(verify="check", path=self.repo / "spec.md")))

    def git(self, *args):
        return support.sh(self.repo, "git", *args)

    def add_ticket(self, tid):
        self.r.order.append(tid)
        self.st.ticket(tid).status = state.MERGED
        self.r.feat.tickets[tid] = SimpleNamespace(title=f"티켓 {tid}", touches=[])
        (self.rundir / tid / "1").mkdir(parents=True)
        return self.rundir / tid / "1" / "verify.log"

    def record(self, *rows):
        self.st.metrics.setdefault("validations", []).extend(rows)

    def verify_section(self):
        return report.evidence(self.r).split("### verify 출력")[1]


class PassedLineTest(Base):
    def test_clean_ticket_pass_is_one_line_without_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text(PASS)
        self.record(call("ticket-05"))
        text = self.verify_section()
        self.assertIn(f"- ticket-05: 통과 · 종료 코드 0 · 12.3초 · 로그 {log.resolve()}", text)
        self.assertNotIn(TAIL, text)
        self.assertNotIn("#### 05/1/verify.log", text)

    def test_clean_finish_pass_is_one_line_and_names_its_label(self):
        log = self.rundir / "finish/integration-verify.log"
        log.write_text(PASS)
        self.record(call("integration", seconds=3))
        text = self.verify_section()
        self.assertIn(f"- integration: 통과 · 종료 코드 0 · 3초 · 로그 {log.resolve()}", text)
        self.assertNotIn(TAIL, text)

    def test_output_format_is_not_read(self):
        log = self.add_ticket("05")
        log.write_text("$ check\n알 수 없는 도구의 출력\n\n종료 코드: 0\n")
        self.record(call("ticket-05"))
        self.assertIn("- ticket-05: 통과", self.verify_section())

    def assert_tail_kept(self, text_marker=TAIL):
        text = self.verify_section()
        self.assertNotIn("통과 · 종료 코드 0", text)
        self.assertIn("#### ", text)
        self.assertIn(text_marker, text)

    def test_failed_verify_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text(FAIL)
        self.record(call("ticket-05", code=1, ok=False, result="failed"))
        self.assert_tail_kept("FAILED one")

    def test_timeout_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text("$ check\nstuck here\n시간 초과: 1분\n\n종료 코드: -9\n")
        self.record(call("ticket-05", code=-9, ok=False, result="timeout"))
        self.assert_tail_kept("stuck here")

    def test_retried_pass_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text("$ check\nFAILED once\n\n종료 코드: 1\n\n검증 재시도 1\n" + PASS +
                       "\nflaky: ticket-05 재시도 1번 만에 통과\n")
        self.record(call("ticket-05", code=1, ok=False, result="failed"), call("ticket-05", retry=2))
        self.assert_tail_kept("FAILED once")

    def test_triaged_pass_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text("$ check\nFAILED a_test\n\n종료 코드: 1\n" + PASS)
        self.record(call("ticket-05", code=1, ok=False, result="failed", triage="passed", triage_files=["a_test"]),
                    call("ticket-05", retry=2, after_triage=True))
        self.assert_tail_kept("FAILED a_test")

    def test_exit_zero_but_tree_changed_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text(PASS)  # 로그만 봐서는 모른다: 측정 기록의 트리 변경이 가른다
        self.record(call("ticket-05", changed=True, result="tree_changed"))
        self.assert_tail_kept()

    def test_old_state_without_measurements_keeps_the_log_tail(self):
        log = self.add_ticket("05")
        log.write_text(PASS)
        self.assert_tail_kept()
        self.record({"label": "ticket-05", "command": "check", "sha": "a", "attempt": 1, "seconds": 3, "result": "passed"})
        self.assert_tail_kept()

    def test_a_log_without_exactly_one_clean_exit_line_keeps_its_tail(self):
        log = self.add_ticket("05")
        self.record(call("ticket-05"))
        for text in ("integration과 같은 코드, 건너뜀\n", PASS + "\n종료 코드: 0\n", "$ check\nlots of passing output\n"):
            with self.subTest(text=text):
                log.write_text(text)
                self.assertNotIn("통과 · 종료 코드 0", self.verify_section())

    def test_only_the_last_call_of_the_ticket_decides(self):
        log = self.add_ticket("05")
        log.write_text(FAIL)
        self.record(call("ticket-05"), call("ticket-05-repair", code=1, ok=False, result="failed"))
        self.assert_tail_kept("FAILED one")

    def test_mixed_logs_each_decide_alone(self):
        self.add_ticket("05").write_text(PASS)
        self.add_ticket("06").write_text(FAIL)
        self.record(call("ticket-05"), call("ticket-06", code=1, ok=False, result="failed"))
        text = self.verify_section()
        self.assertIn("- ticket-05: 통과", text)
        self.assertIn("#### 06/1/verify.log", text)
        self.assertIn("FAILED one", text)


class MergeFactsTest(Base):
    def merge(self, tid, *, from_ref="main"):
        """from_ref에서 갈라진 티켓 브랜치를 main에 --no-ff로 병합한다. 병합 뒤 브랜치는 지운다."""
        self.git("checkout", "-qb", "ticket", from_ref)
        self.git("commit", "-q", "--allow-empty", "-m", f"worker {tid}")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "ticket", "-m", f"Merge {tid}\n\ngs-ticket: demo/{tid}")
        self.git("branch", "-D", "ticket")
        return self.git("rev-parse", "--short", "HEAD").strip()

    def facts(self):
        return report.merge_facts(self.r)

    def test_merged_unmerged_and_embraced_tickets(self):
        self.r.order.extend(["01", "02", "03"])
        first = self.merge("01", from_ref="base")      # 01은 base에서 갈라져 아무것도 품지 않는다
        second = self.merge("02", from_ref="main")     # 02는 01이 병합된 main에서 갈라졌다
        text = self.facts()
        self.assertTrue(text.startswith("## 티켓 병합 사실(git)\n"))
        self.assertIn(f"- 01: 병합 커밋 {first} · 병합될 때 이미 품은 티켓: 없음", text)
        self.assertIn(f"- 02: 병합 커밋 {second} · 병합될 때 이미 품은 티켓: 01({first})", text)
        self.assertIn("- 03: 병합 안 됨", text)

    def test_ticket_that_did_not_hold_an_earlier_merge_is_not_listed(self):
        self.r.order.extend(["01", "02"])
        self.merge("01", from_ref="base")
        second = self.merge("02", from_ref="base")     # 02는 01 병합 전 base에서 갈라졌다
        self.assertIn(f"- 02: 병합 커밋 {second} · 병합될 때 이미 품은 티켓: 없음", self.facts())

    def test_reads_git_only_not_state(self):
        self.r.order.extend(["01", "02"])
        self.st.ticket("01").status = state.MERGED     # state는 병합이라 하지만 git에는 없다
        self.st.ticket("02").status = state.FAILED
        second = self.merge("02", from_ref="base")     # state는 실패라 하지만 git에는 병합이 있다
        text = self.facts()
        self.assertIn("- 01: 병합 안 됨", text)
        self.assertIn(f"- 02: 병합 커밋 {second}", text)

    def test_other_features_marks_and_worker_commits_do_not_count(self):
        self.r.order.append("01")
        self.git("commit", "-q", "--allow-empty", "-m", "worker\n\ngs-ticket: demo/01")
        self.git("checkout", "-qb", "other", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "x")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "other", "-m", "Merge 01\n\ngs-ticket: other/01")
        self.assertIn("- 01: 병합 안 됨", self.facts())

    def test_git_failure_is_reported_instead_of_raised(self):
        self.r.order.append("01")
        with mock.patch.object(git, "merged_tickets", side_effect=git.GitError("boom")):
            text = self.facts()
        self.assertIn("git에서 읽지 못함: boom", text)

    def test_summary_input_has_the_section_and_the_prompt_asks_to_check_it(self):
        self.add_ticket("01")
        first = self.merge("01", from_ref="base")
        self.r.cfg = SimpleNamespace(timeouts=SimpleNamespace(judge_minutes=1), agy=SimpleNamespace(max_calls_per_run=5))
        self.r.feat.spec.path.write_text("spec")
        seen = {}

        def fake_call(argv, *, prompt, **kw):
            seen["prompt"] = prompt

        with (mock.patch.object(report.review, "judge_argv", return_value=["x"]),
              mock.patch.object(report.review, "_env", return_value={}),
              mock.patch.object(report.review, "_call", side_effect=fake_call),
              mock.patch.object(report.review, "call_waiting", side_effect=lambda fn, cfg, on_wait: (fn(), "요약")[1])):
            report.summarize(self.r)
        facts = (self.rundir / "finish/report-input.md").read_text()
        self.assertIn("## 티켓 병합 사실(git)", facts)
        self.assertIn(f"- 01: 병합 커밋 {first}", facts)
        self.assertIn("병합 순서·병합 상태에 관한 주장은 `티켓 병합 사실(git)`과 대조해 맞는 것만 남은 위험으로 쓴다", seen["prompt"])


if __name__ == "__main__":
    unittest.main()
