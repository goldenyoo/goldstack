"""`gs retro-log`: 내용, 크기 상한, 실패한 시도 우선, 줄임 표시 시험. agy는 부르지 않는다."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from gs import retrolog, review, state
from gs.cli import main

FEATURE = "feat"


def claude_text(text):
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}, ensure_ascii=False)


def claude_tool(name, command):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": {"command": command}}]}})


def tool_result(text):
    return json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": text}]}})


class RetroLogTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.rundir = self.repo / ".goldstack/work" / FEATURE / "run"
        self.rundir.mkdir(parents=True)
        self.st = state.State(feature=FEATURE)

    def attempt(self, tid, n, lines=(), *, exit_code=None, files=None):
        d = self.rundir / tid / str(n)
        d.mkdir(parents=True, exist_ok=True)
        (d / "worker.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if exit_code is not None:
            (d / "exit").write_text(f"{exit_code}\n")
        for rel, text in (files or {}).items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return d

    def ticket(self, tid, status="merged", phases=(), reason=""):
        ts = self.st.ticket(tid)
        ts.status, ts.reason = status, reason
        ts.phases = list(phases)
        ts.attempts = len(ts.phases)
        return ts

    def save(self):
        state.save(self.rundir, self.st)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--repo", str(self.repo), "retro-log", *args])
        return code, out.getvalue(), err.getvalue()

    def build(self, limit=retrolog.LIMIT_CHARS):
        self.save()
        return retrolog.build(self.repo, FEATURE, state.load(self.rundir, FEATURE), limit)

    # --- CLI

    def test_writes_one_file_and_prints_its_path(self):
        self.ticket("01")
        self.attempt("01", 1, [claude_text("안녕")], exit_code=0)
        self.save()
        code, out, err = self.run_cli(FEATURE)
        target = self.rundir / "retro-log.md"
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(Path(out.strip()), target)
        self.assertIn("안녕", target.read_text(encoding="utf-8"))
        self.assertEqual(sorted(p.name for p in self.rundir.glob("retro-log*")), ["retro-log.md"])

    def test_missing_run_dir_says_so_and_exits_nonzero(self):
        code, out, err = self.run_cli("other")
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIn("run", err)
        self.assertIn("other", err)
        (self.repo / ".goldstack/work/other").mkdir()
        code, out, err = self.run_cli("other")
        self.assertNotEqual(code, 0)
        self.assertIn("run", err)
        self.assertFalse((self.repo / ".goldstack/work/other/run").exists())

    # --- 내용

    def test_content_per_ticket_and_attempt(self):
        self.ticket("01", phases=[
            {"attempt": 1, "phase": "worker", "model": "claude", "started_at": "2026-11-04T09:00:00+09:00",
             "ended_at": "2026-11-04T09:10:00+09:00"},
            {"attempt": 1, "phase": "review", "model": "codex", "started_at": "2026-11-04T09:10:00+09:00",
             "ended_at": "2026-11-04T09:20:00+09:00"}])
        self.attempt("01", 1, [json.dumps({"type": "system", "subtype": "init", "model": "m", "cwd": "/x"}),
                               claude_text("구현을 시작한다"), claude_tool("Bash", "ls src"),
                               tool_result("TOOL-OUTPUT-DROPPED")], exit_code=0,
                     files={"review/review.txt": "지적: 위치 a.py:3\n# 제목처럼 보이는 줄",
                            "fix/worker.log": claude_text("지적을 고친다") + "\n",
                            "rereview1-codex/review.txt": "재리뷰 해결됨"})
        self.ticket("02")
        self.attempt("02", 1, [claude_text("두번째 티켓")], exit_code=0)
        text = self.build()
        self.assertIn("## 티켓 01", text)
        self.assertIn("## 티켓 02", text)
        self.assertIn("### 시도 1 (통과)", text)
        self.assertIn("구현을 시작한다", text)
        self.assertIn("→ Bash ls src", text)
        self.assertNotIn("TOOL-OUTPUT-DROPPED", text)  # render를 거쳤다
        self.assertNotIn('"type":', text)  # 원본 JSON이 아니다
        self.assertIn("지적: 위치 a.py:3", text)
        self.assertIn("지적을 고친다", text)
        self.assertIn("재리뷰 해결됨", text)
        self.assertIn("2026-11-04T09:00:00+09:00 → 2026-11-04T09:10:00+09:00", text)
        self.assertIn("review (codex)", text)
        self.assertIn(".goldstack/work/feat/run/01/1/worker.log", text)  # Claude가 원본을 열 경로
        self.assertNotIn("\n# 제목처럼 보이는 줄", text)  # 본문의 # 줄이 제목으로 읽히지 않는다
        self.assertLess(text.index("## 티켓 01"), text.index("## 티켓 02"))
        self.assertLess(text.index("지적: 위치"), text.index("재리뷰 해결됨"))

    def test_failed_attempt_gets_error_lines_with_source_line_numbers(self):
        self.ticket("01", status="failed", reason="worker 종료 코드 1")
        lines = [claude_text("시작"), claude_tool("Bash", "pytest"),
                 tool_result("FAIL: test_alpha\nAssertionError: 1 != 2\nok line"),
                 claude_text("고치는 중")]
        self.attempt("01", 1, lines, exit_code=1,
                     files={"failure.log": "실패 이유: worker 종료 코드 1\n\n## 로그 끝\n...",
                            "verify.log": "\n".join(f"v{i}" for i in range(200)) + "\nFAILED (errors=2)"})
        text = self.build()
        self.assertIn("### 시도 1 (실패)", text)
        self.assertIn("3: FAIL: test_alpha", text)  # 원본 3번째 줄
        self.assertIn("3: AssertionError: 1 != 2", text)
        self.assertNotIn("ok line", text)
        self.assertIn("종료 코드 1", text)
        self.assertIn("실패 이유: worker 종료 코드 1", text)
        self.assertIn("FAILED (errors=2)", text)
        self.assertNotIn("v10\n", text)  # verify.log는 끝부분만

    def test_passing_attempt_has_no_error_section(self):
        self.ticket("01")
        self.attempt("01", 1, [tool_result("error: x")], exit_code=0)
        self.assertNotIn("오류 줄", self.build())

    def test_error_lines_are_length_and_count_limited(self):
        self.ticket("01", status="failed")
        lines = [tool_result("error " + "x" * 5000)]
        lines += [tool_result(f"Traceback number {i}") for i in range(100)]
        self.attempt("01", 1, lines, exit_code=2)
        text = self.build()
        section = text.split("#### 오류 줄", 1)[1]
        rows = [ln for ln in section.splitlines() if ln[:1].isdigit()]
        self.assertEqual(len(rows), retrolog.ERROR_LINES)
        self.assertIn("101: Traceback number 99", rows[-1])  # 마지막 것을 남긴다
        self.assertTrue(all(len(r) < retrolog.ERROR_LINE_CAP + 20 for r in rows))
        # 마지막 시도가 실패한 티켓은 exit 파일이 없어도 실패로 본다
        self.ticket("02", status="failed")
        self.attempt("02", 1, [tool_result("error y")])
        self.assertIn("### 시도 1 (실패)", self.build().split("## 티켓 02", 1)[1])

    # --- 크기 상한과 우선순위

    def test_small_feature_is_kept_whole_without_notice(self):
        self.ticket("01")
        self.attempt("01", 1, [claude_text("짧다")], exit_code=0)
        text = self.build()
        self.assertNotIn("줄임", text)

    def big_feature(self, passing=3, size=400):
        for i in range(passing):
            tid = f"1{i}"
            self.ticket(tid)
            self.attempt(tid, 1, [claude_text(f"PASS-{tid}-{j} " + "p" * 80) for j in range(size)], exit_code=0,
                         files={"review/review.txt": "\n".join(f"REVIEW-{tid}-{j} " + "r" * 80 for j in range(size))})
        self.ticket("99", status="failed", reason="worker 종료 코드 1")
        self.attempt("99", 1, [claude_text(f"FAIL-{j} " + "f" * 80) for j in range(size)]
                     + [tool_result("Traceback KEEP-ME-ERROR")], exit_code=1)

    def test_size_limit_holds_and_failed_attempt_survives_first(self):
        self.big_feature()
        limit = 50_000
        full = self.build(10**9)
        self.assertGreater(len(full), limit * 2)
        text = self.build(limit)
        self.assertLessEqual(len(text), limit)
        failed_part = text.split("## 티켓 99", 1)[1]
        # 실패한 시도는 원문 그대로 남는다
        self.assertIn("FAIL-0 ", failed_part)
        self.assertIn(f"FAIL-{399} ", failed_part)
        self.assertIn("KEEP-ME-ERROR", failed_part)
        self.assertNotIn("[줄임:", failed_part)
        # 나머지가 줄었다
        for tid in ("10", "11", "12"):
            part = text.split(f"## 티켓 {tid}", 1)[1].split("\n## 티켓", 1)[0]
            self.assertIn("[줄임:", part)
            self.assertLess(len(part), len(full) // 4)

    def test_every_section_keeps_its_header_under_a_tight_limit(self):
        self.big_feature(passing=1)
        text = self.build(45_000)
        self.assertLessEqual(len(text), 45_000)
        # 모든 구역이 머리 줄은 남는다
        self.assertIn("#### worker 로그", text)
        self.assertIn("리뷰 답", text)
        self.assertIn("### 시도 1 (통과)", text)

    def test_trimming_is_announced_at_top_and_in_place(self):
        self.big_feature()
        text = self.build(50_000)
        head = text.split("## 티켓", 1)[0]
        self.assertIn("줄임", head)
        self.assertIn("티켓 10 시도 1 worker 로그", head)
        self.assertNotIn("티켓 99 시도 1 worker 로그", head)  # 줄이지 않은 것은 적지 않는다
        self.assertRegex(text, r"\[줄임: 원문 [\d,]+줄 중 [\d,]+줄 생략\]")

    def test_failed_attempt_alone_larger_than_limit_is_trimmed_to_limit(self):
        self.ticket("01", status="failed")
        self.attempt("01", 1, [claude_text(f"L{j} " + "x" * 90) for j in range(3000)], exit_code=1)
        text = self.build(30_000)
        self.assertLessEqual(len(text), 30_000)
        self.assertIn("[줄임:", text)
        self.assertIn("L0 ", text)  # 앞과 뒤를 남긴다
        self.assertIn("L2999 ", text)

    def test_default_limit_is_about_80k_tokens(self):
        self.assertEqual(retrolog.LIMIT_CHARS, 210_000)
        self.ticket("01")
        self.attempt("01", 1, [claude_text("x" * 1000) for _ in range(1000)], exit_code=0)
        self.assertLessEqual(len(self.build()), retrolog.LIMIT_CHARS)

    def test_huge_single_line_is_capped_and_marked_in_place(self):
        self.ticket("01")
        self.attempt("01", 1, [claude_text("y" * 100_000)], exit_code=0)
        text = self.build()
        self.assertLess(len(text), 10_000)
        self.assertIn("[줄임: 한 줄 100,000자]", text)

    def test_file_under_the_limit_is_not_trimmed(self):
        self.big_feature(passing=1, size=100)
        full = self.build(10**9)
        self.assertNotIn("[줄임:", full)
        self.assertEqual(self.build(len(full)), full)  # 딱 한도여도 그대로다
        one_less = self.build(len(full) - 1)
        self.assertLessEqual(len(one_less), len(full) - 1)
        self.assertIn("[줄임:", one_less)

    def test_budget_is_used_up_when_trimming(self):
        """줄여야 할 때 한도를 거의 다 쓴다. 표시 자리를 너무 잡아 통과한 로그를 지나치게 깎지 않는다."""
        self.big_feature(passing=4)
        limit = 60_000
        self.assertGreater(len(self.build(limit)), limit - retrolog._NOTICE_RESERVE * 2)

    def test_review_answer_is_not_line_capped_when_file_is_small(self):
        self.ticket("01")
        claims = [f"CLAIM-{j} " + "c" * 900 for j in range(8)]
        self.attempt("01", 1, [claude_text("ok")], exit_code=0,
                     files={"review/review.txt": json.dumps({"findings": claims})})
        text = self.build()
        for j in range(8):
            self.assertIn(f"CLAIM-{j} ", text)
        self.assertNotIn("[줄임:", text)

    def test_one_line_review_answer_is_trimmed_by_budget_and_announced(self):
        self.ticket("01")
        review = json.dumps({"findings": [f"CLAIM-{j} " + "c" * 900 for j in range(40)]})
        self.attempt("01", 1, [claude_text("ok")], exit_code=0, files={"review/review.txt": review})
        text = self.build(12_000)
        self.assertLessEqual(len(text), 12_000)
        self.assertIn("CLAIM-0 ", text)  # 한 줄이어도 앞과 뒤를 남긴다
        self.assertIn("CLAIM-39 ", text)
        self.assertRegex(text, r"\[줄임: 한 줄 [\d,]+자 중 [\d,]+자 생략\]")
        self.assertIn("01 시도 1 review 리뷰 답", text.split("## 티켓", 1)[0])

    def test_failure_under_fix_dir_marks_the_attempt_failed(self):
        self.ticket("01")  # 재시도 뒤 merged라도 앞선 시도는 실패다
        self.attempt("01", 1, [claude_text("impl")], exit_code=0, files={
            "review/review.txt": "REVIEW-KEEP",
            "fix/worker.log": claude_text("fixing") + "\n",
            "fix/failure.log": "실패 이유: 검증 실패(x)\n\n본문\n"})
        text = self.build()
        self.assertIn("### 시도 1 (실패)", text)
        self.assertIn("#### 수정 worker fix (실패)", text)

    def test_attempt_with_failed_fix_is_kept_first_under_limit(self):
        self.ticket("01")
        self.attempt("01", 1, [claude_text(f"IMPL-{j} " + "i" * 90) for j in range(300)], exit_code=0,
                     files={"fix/failure.log": "실패 이유: 검증 실패\n"})
        self.ticket("02")
        self.attempt("02", 1, [claude_text(f"OTHER-{j} " + "o" * 90) for j in range(300)], exit_code=0)
        text = self.build(40_000)
        self.assertLessEqual(len(text), 40_000)
        part = text.split("## 티켓 01", 1)[1].split("\n## 티켓", 1)[0]
        self.assertIn("IMPL-0 ", part)
        self.assertIn("IMPL-299 ", part)
        self.assertNotIn("[줄임:", part)

    def test_every_run_of_a_failed_attempt_is_kept_first(self):
        """fix가 통과하고 fix2가 실패해도 그 시도의 fix 로그는 1순위다. 오류 줄은 실패한 실행에만 붙는다."""
        self.ticket("01")
        self.attempt("01", 1, [claude_text("impl")], exit_code=0, files={
            "fix/worker.log": "\n".join(claude_text(f"FIX-{j} " + "a" * 90) for j in range(300)) + "\n",
            "fix/exit": "0\n",
            "fix2/worker.log": tool_result("error FIX2-ERROR") + "\n",
            "fix2/failure.log": "실패 이유: 검증 실패\n"})
        self.ticket("02")
        self.attempt("02", 1, [claude_text(f"OTHER-{j} " + "o" * 90) for j in range(300)], exit_code=0)
        text = self.build(40_000)
        part = text.split("## 티켓 01", 1)[1].split("\n## 티켓", 1)[0]
        self.assertIn("FIX-0 ", part)
        self.assertIn("FIX-299 ", part)
        self.assertNotIn("[줄임:", part)
        self.assertIn("#### 수정 worker fix (통과)", part)
        self.assertIn("#### 수정 worker fix2 (실패)", part)
        self.assertIn("1: error FIX2-ERROR", part)
        self.assertEqual(part.count("#### 오류 줄"), 1)

    def discard(self, tid, n, nth, reason, key="review"):
        """go._end_fix가 남기는 기록: 종료 코드 0으로 끝난 수정 worker의 실패는 리뷰 기록의 지적에만 있다."""
        setattr(self.st.ticket(tid), key, {"reviewer": "codex", "dir": str(self.rundir / tid / str(n) / "review"), "findings": [
            {"id": 1, "action": "fix", "fix_attempt": review.ATTEMPTED, "fix_round": max(nth - 1, 1)},
            {"id": 2, "action": "fix", "fix_attempt": review.DISCARDED, "fix_round": nth, "fix_reason": reason}]})

    def test_discarded_fix_with_exit_zero_is_a_failed_attempt(self):
        for tid, why in (("01", "커밋 없음"), ("02", "이전 커밋을 지웠다")):
            self.ticket(tid)
            self.attempt(tid, 1, [claude_text("impl")], exit_code=0, files={
                "fix/worker.log": tool_result("error FIX-OUTPUT") + "\n", "fix/exit": "0\n"})
            self.discard(tid, 1, 1, f"수정 worker 실패: {why}")
        text = self.build()
        first, second = text.split("## 티켓 02", 1)
        for part, why in ((first, "커밋 없음"), (second, "이전 커밋을 지웠다")):
            self.assertIn("### 시도 1 (실패)", part)
            self.assertIn("#### 수정 worker fix (실패)", part)
            self.assertIn(f"- 종료 코드 0 · 수정 worker 실패: {why}", part)
            self.assertIn("1: error FIX-OUTPUT", part)
            self.assertNotIn("(통과)", part)

    def test_discarded_fix_is_kept_first_under_limit(self):
        self.ticket("01")
        self.attempt("01", 1, [claude_text(f"IMPL-{j} " + "i" * 90) for j in range(300)], exit_code=0, files={
            "review/review.txt": "\n".join(f"REVIEW-{j} " + "r" * 90 for j in range(300)),
            "fix/worker.log": "\n".join(claude_text(f"FIX-{j} " + "a" * 90) for j in range(300)) + "\n",
            "fix/exit": "0\n"})
        self.discard("01", 1, 1, "수정 worker 실패: 커밋 없음")
        self.ticket("02")
        self.attempt("02", 1, [claude_text(f"OTHER-{j} " + "o" * 90) for j in range(900)], exit_code=0)
        text = self.build(110_000)
        self.assertLessEqual(len(text), 110_000)
        part = text.split("## 티켓 01", 1)[1].split("\n## 티켓", 1)[0]
        for word in ("IMPL-299 ", "REVIEW-299 ", "FIX-299 ", "수정 worker 실패: 커밋 없음"):
            self.assertIn(word, part)
        self.assertNotIn("[줄임:", part)
        self.assertIn("[줄임:", text.split("## 티켓 02", 1)[1])

    def test_discard_marks_only_its_round_and_attempt(self):
        """1차 수정이 통과하고 2차가 버려졌으면 2차만 실패다. 끊겨 다시 띄운 2차(-net1)도 같은 회차다. 지적은 기록의 dir로 시도를 찾는다."""
        self.ticket("01", status="running")
        self.attempt("01", 1, [claude_text("impl")], exit_code=0, files={
            "fix/worker.log": claude_text("first") + "\n", "fix/exit": "0\n",
            "fix2/worker.log": claude_text("second") + "\n",
            "fix2-net1/worker.log": claude_text("second again") + "\n", "fix2-net1/exit": "0\n"})
        self.attempt("01", 2, [claude_text("next")])
        self.discard("01", 1, 2, "수정 worker 실패: 커밋 없음", key="second_review")
        text = self.build()
        self.assertIn("### 시도 1 (실패)", text)
        self.assertIn("#### 수정 worker fix (통과)", text)
        self.assertIn("#### 수정 worker fix2 (실패)", text)
        self.assertIn("#### 수정 worker fix2-net1 (실패)", text)
        self.assertIn("### 시도 2 (끝 기록 없음)", text)

    def test_attempted_fix_is_not_a_failure(self):
        self.ticket("01").review = {"reviewer": "codex", "dir": str(self.rundir / "01/1/review"), "findings": [
            {"id": 1, "action": "fix", "fix_attempt": review.ATTEMPTED, "fix_round": 1},
            {"id": 2, "action": "fix", "fix_reason": "한도"}]}  # 띄우지 못한 수정은 돈 worker가 없다
        self.attempt("01", 1, [claude_text("impl")], exit_code=0, files={"fix/worker.log": "", "fix/exit": "0\n"})
        text = self.build()
        self.assertIn("### 시도 1 (통과)", text)
        self.assertIn("#### 수정 worker fix (통과)", text)

    def test_attempt_labels_do_not_call_unfinished_runs_passed(self):
        self.ticket("01", status="running")
        self.attempt("01", 1, [claude_text("끊긴 시도")], exit_code=0)  # 실패 기록 없이 다음 시도가 이어졌다
        self.attempt("01", 2, [claude_text("도는 시도")])  # exit가 없다
        text = self.build()
        self.assertIn("### 시도 1 (중단)", text)
        self.assertIn("### 시도 2 (끝 기록 없음)", text)
        self.assertNotIn("(통과)", text)

    # --- 오류 줄의 내용

    def test_verify_failure_outside_the_tail_is_kept(self):
        """병렬 시험은 FAIL 줄이 끝에 오지 않는다. 시험 이름이 파일에 남아야 한다."""
        self.ticket("01", status="failed")
        noise = [f"Ran {i} tests" for i in range(retrolog.VERIFY_TAIL_LINES * 2)]
        self.attempt("01", 1, [claude_text("x")], exit_code=0, files={
            "failure.log": "실패 이유: 검증 실패\n",
            "verify.log": "\n".join(["...", "FAIL: test_mid (test_x.T.test_mid)", *noise]) + "\n"})
        text = self.build()
        self.assertIn("#### verify.log 오류 줄", text)
        self.assertIn("2: FAIL: test_mid (test_x.T.test_mid)", text)
        self.assertIn(".goldstack/work/feat/run/01/1/verify.log", text)

    def test_repeated_error_keeps_its_last_position(self):
        """앞에 나온 줄과 같아도 마지막 오류가 밀려나지 않는다."""
        self.ticket("01", status="failed")
        lines = [tool_result("FAILED (failures=1)")]
        lines += [tool_result(f"error noise {i}") for i in range(retrolog.ERROR_LINES)]
        lines += [tool_result("FAILED (failures=1)")]
        self.attempt("01", 1, lines, exit_code=1)
        section = self.build().split("#### 오류 줄", 1)[1]
        self.assertIn(f"{len(lines)}: FAILED (failures=1)", section)
        self.assertEqual(section.count("FAILED (failures=1)"), 1)

    def test_error_lines_skip_text_that_render_already_keeps(self):
        self.ticket("01", status="failed")
        lines = [claude_text("error in assistant ASSISTANT-WORD"),
                 json.dumps({"type": "result", "subtype": "error", "result": "실패 요약 RESULT-WORD"}, ensure_ascii=False),
                 json.dumps({"type": "tool_progress", "tool_name": "Bash", "note": "failed PROGRESS-WORD"}),
                 json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "error CODEX-TALK"}}),
                 json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "grep error CODEX-CMD",
                                                                "aggregated_output": "ok\nFAIL: codex_test", "exit_code": 1}}),
                 json.dumps({"type": "error", "message": "Reconnecting... (Connection failed: RECONNECT-WORD)"}),
                 "shell: error RAW-WORD"]
        self.attempt("01", 1, lines, exit_code=1)
        section = self.build().split("#### 오류 줄", 1)[1]
        for word in ("ASSISTANT-WORD", "RESULT-WORD", "PROGRESS-WORD", "CODEX-TALK", "CODEX-CMD"):
            self.assertNotIn(word, section)
        self.assertIn("5: FAIL: codex_test", section)
        self.assertIn("6: Reconnecting... (Connection failed: RECONNECT-WORD)", section)
        self.assertIn("7: shell: error RAW-WORD", section)
        self.assertNotRegex(section, r"(?m)^\d+: error$")  # 이벤트 종류 낱말은 오류 줄이 아니다

    def test_error_line_numbers_match_the_source_file_with_carriage_returns(self):
        """줄 번호는 grep·sed와 같다. \\r만 있는 줄바꿈(진행 표시)은 줄을 나누지 않는다."""
        self.ticket("01", status="failed")
        self.attempt("01", 1, ["progress 1\rprogress 2\rdone", "error HERE"], exit_code=1)
        self.assertIn("2: error HERE", self.build())

    def test_unreadable_state_says_so_and_exits_nonzero(self):
        self.attempt("01", 1, [claude_text("x")], exit_code=0)
        (self.rundir / "state.json").write_text("{깨진 json", encoding="utf-8")
        code, out, err = self.run_cli(FEATURE)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("state.json", err)
        self.assertFalse((self.rundir / "retro-log.md").exists())

    def test_retro_skill_gives_agy_only_the_merged_file(self):
        body = (Path(__file__).resolve().parents[1] / "skills/retro/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("gs retro-log $ARGUMENTS", body)
        self.assertIn("하나만", body)
        self.assertIn("그 파일의 줄 번호", body)
        self.assertNotIn("경로 목록", body)

    def test_water_level(self):
        self.assertEqual(retrolog._water_level([10, 20], 100), 20)
        self.assertEqual(retrolog._water_level([10, 100, 100], 110), 50)
        self.assertEqual(retrolog._water_level([100, 100], 0), 0)


if __name__ == "__main__":
    unittest.main()
