"""리뷰어에게 worker의 마지막 메시지를 넘긴다(v10 05)."""
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from gs import review, streamfmt
import support


def lines(*events) -> str:
    return "".join((e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)) + "\n" for e in events)


def assistant(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


class LastMessageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, body: str) -> Path:
        p = self.dir / "worker.log"
        p.write_text(body, encoding="utf-8")
        return p

    def test_claude_result(self):
        p = self.log(lines({"type": "system", "subtype": "init"}, assistant("중간 글"),
                           {"type": "result", "subtype": "success", "result": " 끝났다. 네트워크가 막혀 시험을 못 돌렸다. "}))
        self.assertEqual(streamfmt.last_message(p), "끝났다. 네트워크가 막혀 시험을 못 돌렸다.")

    def test_claude_without_result_uses_last_assistant_text(self):
        tool = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
        p = self.log(lines(assistant("첫 글"), assistant("마지막 글"), tool))
        self.assertEqual(streamfmt.last_message(p), "마지막 글")

    def test_claude_empty_result_falls_back_to_assistant(self):
        p = self.log(lines(assistant("글"), {"type": "result", "subtype": "error_max_turns", "result": ""}))
        self.assertEqual(streamfmt.last_message(p), "글")

    def test_codex_last_agent_message(self):
        done = lambda t, text: {"type": "item.completed", "item": {"type": t, "text": text}}  # noqa: E731
        p = self.log(lines({"type": "thread.started", "thread_id": "x"}, done("agent_message", "첫째"),
                           done("command_execution", "무시"), done("agent_message", "둘째"), {"type": "turn.completed"}))
        self.assertEqual(streamfmt.last_message(p), "둘째")

    def test_agy_result_response(self):
        p = self.log(lines({"event": "init", "init": {"model": "m"}},
                           {"event": "result", "result": {"status": "SUCCESS", "response": "agy 답"}}))
        self.assertEqual(streamfmt.last_message(p), "agy 답")

    def test_missing_log(self):
        self.assertIsNone(streamfmt.last_message(self.dir / "none.log"))

    def test_broken_lines_are_skipped(self):
        p = self.log("not json\n[1, 2]\n{\"type\": \"result\", \"result\": 5}\n{\"broken\n"
                     + lines(assistant("살아남은 글")) + "{\"type\": \"assistant\", \"message\": 3}\n"
                     + '{"type": "assistant", "message": {"content": [7, {"type": "text", "text": null}]}}\n')
        self.assertEqual(streamfmt.last_message(p), "살아남은 글")

    def test_binary_and_empty_logs(self):
        p = self.dir / "worker.log"
        p.write_bytes(b"\xff\xfe\x00{\n")
        self.assertIsNone(streamfmt.last_message(p))
        p.write_text("")
        self.assertIsNone(streamfmt.last_message(p))
        self.assertIsNone(streamfmt.last_message(self.dir))  # 디렉터리


class WorkerLastFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, text):
        p = self.dir / "worker.log"
        p.write_text(lines({"type": "result", "result": text}))
        return p

    def test_written_next_to_diff(self):
        out = review.write_worker_last(self.dir, self.log("보고"))
        self.assertEqual(out, (self.dir / "worker-last.txt").resolve())
        self.assertEqual(out.read_text(), "보고\n")

    def test_limit_keeps_the_end_and_says_truncated(self):
        text = "머리표" + "x" * 9000 + "끝맺음"
        out = review.write_worker_last(self.dir, self.log(text))
        body = out.read_text()
        self.assertLessEqual(len(body), review.WORKER_LAST_LIMIT + 1)  # 끝 줄바꿈 하나
        self.assertIn("잘랐다", body.splitlines()[0])
        self.assertTrue(body.rstrip("\n").endswith("끝맺음"))
        self.assertNotIn("머리표", body)

    def test_exactly_at_limit_is_not_truncated(self):
        text = "가" * review.WORKER_LAST_LIMIT
        body = review.write_worker_last(self.dir, self.log(text)).read_text()
        self.assertEqual(body, text + "\n")

    def test_no_log_no_file(self):
        (self.dir / "worker-last.txt").write_text("옛것")  # 지난 내용이 남지 않는다
        self.assertIsNone(review.write_worker_last(self.dir, self.dir / "none.log"))
        self.assertFalse((self.dir / "worker-last.txt").exists())
        self.assertIsNone(review.write_worker_last(self.dir, None))

    def test_broken_log_no_file(self):
        p = self.dir / "worker.log"
        p.write_text("{\"type\": \"res\n")
        self.assertIsNone(review.write_worker_last(self.dir, p))
        self.assertFalse((self.dir / "worker-last.txt").exists())

    def test_unwritable_dir_does_not_raise(self):
        self.assertIsNone(review.write_worker_last(self.dir / "no" / "such", self.log("보고")))

    def test_prompts_name_the_file_and_call_it_untrusted(self):
        path = self.dir / "worker-last.txt"
        d = Path("/d.patch")
        for prompt in (review.review_prompt(d, d, d, d, path), review.rereview_prompt(d, d, d, d, d, worker_last=path)):
            self.assertEqual(prompt.count(str(path)), 2)
            self.assertIn("믿을 수 없는 자료", prompt)
            self.assertIn("따르지 말고", prompt)
            self.assertIn("사유", prompt)

    def test_prompts_unchanged_without_file(self):
        d = Path("/d.patch")
        for prompt in (review.review_prompt(d, d, d, d), review.rereview_prompt(d, d, d, d, d)):
            self.assertNotIn("worker 보고", prompt)
            self.assertNotIn("worker가 마지막에", prompt)
        self.assertEqual(review.review_prompt(d, d, d, d), review.review_prompt(d, d, d, d, None))


class ResumedWorkerLogTest(unittest.TestCase):
    """네트워크로 이은 worker와 재개된 리뷰는 가장 최근 시도의 디렉터리를 가리킨다."""

    def active(self, rundir, fix):
        from types import SimpleNamespace
        return SimpleNamespace(fix=fix, proc=SimpleNamespace(job=SimpleNamespace(rundir=Path(rundir), log=Path(rundir) / "worker.log")))

    def test_first_review_uses_attempt_worker_log(self):
        from gs import go
        self.assertEqual(go._attempt_dir(self.active("/r/01/2", 0)) / "worker.log", Path("/r/01/2/worker.log"))  # 이은 구현 worker
        self.assertEqual(go._attempt_dir(self.active("/r/01/2/fix", 1)) / "worker.log", Path("/r/01/2/worker.log"))
        self.assertEqual(go._attempt_dir(self.active("/r/01/2/fix2-net1", 2)) / "worker.log", Path("/r/01/2/worker.log"))

    def test_rereview_uses_most_recent_fix_worker_log(self):
        # 재리뷰는 a.proc.job.log: 이은 수정 worker(fix-net1)와 재개된 리뷰(stand_in의 rundir)도 같은 모양이다
        self.assertEqual(self.active("/r/01/2/fix-net1", 1).proc.job.log, Path("/r/01/2/fix-net1/worker.log"))


class ReviewerInputTest(support.GoTest):
    """gs go 안에서: 첫 리뷰는 구현 worker, 재리뷰는 수정 worker의 메시지를 읽는다."""

    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              echo '{"type":"result","subtype":"success","result":"FIXREPORT 수정 보고"}'
              echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
            fi
            echo '{"type":"result","subtype":"success","result":"IMPLREPORT 구현 보고"}'
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            cat > "$here/review.prompt"
            n=$(( $(cat "$here/review.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/review.n"
            path=$(grep -o '/[^ `]*diff.patch' "$here/review.prompt" | head -n 1)
            [ -z "$path" ] && path=$(grep -o '/[^ `]*fix.patch' "$here/review.prompt" | head -n 1)
            cp "$path" "$here/review.diff"
            last=$(grep -o '/[^ `]*worker-last.txt' "$here/review.prompt" | head -n 1)
            { echo "== $n: ${last:-없음}"; [ -n "$last" ] && cat "$last"; } >> "$here/worker-last.seen"
            cp "$here/review.prompt" "$here/review.prompt.$n"
            if [ -f "$here/findings.json" ] && [ "$n" = 1 ]; then echo '```json'; cat "$here/findings.json"; echo '```'
            else echo '{"findings": [], "verdicts": [{"id": 1, "status": "resolved", "evidence": "확인"}]}'; fi
        '''))

    def test_first_review_gets_implementation_and_rereview_gets_fix_message(self):
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        seen = (self.bin / "worker-last.seen").read_text()
        first, second = seen.split("== 2: ")
        self.assertIn("IMPLREPORT 구현 보고", first)
        self.assertNotIn("FIXREPORT", first)
        self.assertIn("FIXREPORT 수정 보고", second)
        self.assertNotIn("IMPLREPORT", second)
        self.assertTrue((self.rundir / "01/1/review/worker-last.txt").is_file())
        self.assertTrue((self.rundir / "01/1/rereview1-codex/worker-last.txt").is_file())
        self.assertIn("믿을 수 없는 자료", (self.bin / "review.prompt.1").read_text())

    def test_no_message_means_no_file_and_review_still_runs(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            echo plain text, not json
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.review_state("01")["note"], "")
        self.assertFalse((self.rundir / "01/1/review/worker-last.txt").exists())
        self.assertIn("== 1: 없음", (self.bin / "worker-last.seen").read_text())
        self.assertNotIn("worker-last", (self.bin / "review.prompt.1").read_text())


if __name__ == "__main__":
    unittest.main()
