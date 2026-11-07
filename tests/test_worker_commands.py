"""리뷰어에게 worker가 실행한 명령과 결과를 넘긴다(v24 01)."""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from gs import review, streamfmt
import support


def lines(*events) -> str:
    return "".join((e if isinstance(e, str) else json.dumps(e, ensure_ascii=False)) + "\n" for e in events)


def use(tid, command, name="Bash"):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "돌려 본다"}, {"type": "tool_use", "id": tid, "name": name, "input": {"command": command}}]}}


def got(tid, content, is_error=None):
    block = {"type": "tool_result", "tool_use_id": tid, "content": content}
    if is_error is not None:
        block["is_error"] = is_error
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def codex(command, exit_code, status="completed", kind="item.completed"):
    return {"type": kind, "item": {"id": "item_1", "type": "command_execution", "command": command,
                                   "aggregated_output": "", "exit_code": exit_code, "status": status}}


def agy(state, name="run_command", params=None, error=None):
    info = {"parameters": params if params is not None else {"CommandLine": "go test ./..."}}
    if error:
        info["error"] = error
    return {"event": "step_update", "step_update": {"conversation_id": "c", "step_index": 3, "state": state,
                                                    "step_type": "tool", "tool_name": name, "tool_info": info}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, body: str) -> Path:
        p = self.dir / "worker.log"
        p.write_text(body, encoding="utf-8")
        return p


class CommandsTest(Base):
    def test_claude_pairs_tool_use_with_tool_result(self):
        p = self.log(lines(
            {"type": "system", "subtype": "init"},
            use("t1", "ls tests"), got("t1", "a.py\nb.py"),
            use("t2", "uv run python -m unittest"),
            got("t2", "Exit code 2\nerror: failed to open file `/Users/x/.cache/uv`: Operation not permitted", is_error=True),
            use("t3", "git status", name="Read"),  # Bash가 아닌 도구는 명령이 아니다
            use("t4", "sleep 100")))  # 결과가 없다
        found, omitted = streamfmt.commands(p)
        self.assertEqual(omitted, 0)
        self.assertEqual([c["command"] for c in found], ["ls tests", "uv run python -m unittest", "sleep 100"])
        self.assertEqual([c["ok"] for c in found], [True, False, None])
        self.assertIn("종료 2", found[1]["detail"])
        self.assertIn("Operation not permitted", found[1]["detail"])
        self.assertEqual(found[2]["detail"], "결과 없음")

    def test_claude_error_without_exit_code_and_list_content(self):
        p = self.log(lines(use("t1", "gs hook"), got("t1", [{"type": "text", "text": "PreToolUse:Bash hook error: 막음"}], is_error=True)))
        found, _ = streamfmt.commands(p)
        self.assertFalse(found[0]["ok"])
        self.assertIn("hook error", found[0]["detail"])

    def test_codex_exit_codes(self):
        p = self.log(lines(
            {"type": "thread.started", "thread_id": "x"},
            codex("/bin/zsh -lc 'ls'", None, "in_progress", "item.started"),  # 시작 이벤트는 세지 않는다
            codex("/bin/zsh -lc 'ls'", 0),
            codex("/bin/zsh -lc 'python -m unittest'", 1),
            codex("/bin/zsh -lc 'sleep'", None, "failed"),
            {"type": "item.completed", "item": {"type": "agent_message", "text": "끝"}}))
        found, _ = streamfmt.commands(p)
        self.assertEqual([c["ok"] for c in found], [True, False, None])
        self.assertEqual(found[0]["detail"], "종료 0")
        self.assertEqual(found[1]["detail"], "종료 1")
        self.assertEqual(found[1]["command"], "/bin/zsh -lc 'python -m unittest'")

    def test_agy_done_and_error(self):
        p = self.log(lines(
            {"event": "init", "init": {"model": "m"}},
            agy("ACTIVE"),  # 끝나지 않은 단계는 세지 않는다
            agy("DONE"),
            agy("ERROR", params={"CommandLine": "git push"}, error={"type": "x", "message": "Matches user-configured deny rule."}),
            agy("DONE", name="view_file", params={"Path": "/a"}),  # 명령이 아닌 도구
            {"event": "result", "result": {"status": "SUCCESS", "response": "끝"}}))
        found, _ = streamfmt.commands(p)
        self.assertEqual([(c["command"], c["ok"]) for c in found], [("go test ./...", True), ("git push", False)])
        self.assertIn("deny rule", found[1]["detail"])

    def test_limit_keeps_the_last_ones_and_counts_omitted(self):
        body = lines(*[codex(f"cmd{i}", 0) for i in range(10)])
        found, omitted = streamfmt.commands(self.log(body), limit=3)
        self.assertEqual([c["command"] for c in found], ["cmd7", "cmd8", "cmd9"])
        self.assertEqual(omitted, 7)

    def test_long_command_is_cut_and_multiline_is_one_line(self):
        found, _ = streamfmt.commands(self.log(lines(codex("echo " + "x" * 2000 + "\nsecond", 0))))
        self.assertLessEqual(len(found[0]["command"]), streamfmt.COMMAND_CHARS + 1)
        self.assertNotIn("\n", found[0]["command"])

    def test_unreadable_logs_give_nothing(self):
        self.assertEqual(streamfmt.commands(self.dir / "none.log"), ([], 0))
        self.assertEqual(streamfmt.commands(self.log("plain text\n[1]\n\"s\"\n{broken\n")), ([], 0))
        self.assertEqual(streamfmt.commands(self.log(lines({"type": "assistant", "message": "x"}, {"type": "user", "message": {"content": 3}},
                                                           {"event": "step_update", "step_update": "x"},
                                                           {"type": "item.completed", "item": []}))), ([], 0))


class WriteTest(Base):
    def test_writes_one_line_per_command(self):
        out = review.write_worker_commands(self.dir, self.log(lines(use("t1", "pytest"), got("t1", "Exit code 1\nboom", is_error=True))))
        self.assertEqual(out, (self.dir / "worker-commands.txt").resolve())
        body = out.read_text()
        self.assertIn("1. [실패] pytest — 종료 1", body)

    def test_large_log_keeps_file_small(self):
        out = review.write_worker_commands(self.dir, self.log(lines(*[codex(f"cmd{i} " + "y" * 1000, 0) for i in range(500)])))
        body = out.read_text()
        self.assertLess(len(body), 60 * 400)
        self.assertEqual(len(body.splitlines()), streamfmt.COMMANDS_LIMIT + 1)
        self.assertIn("앞 440개는 뺐다", body.splitlines()[0])
        self.assertIn("500. [성공] cmd499", body)

    def test_no_commands_means_no_file(self):
        (self.dir / "worker-commands.txt").write_text("옛것")  # 지난 내용이 남지 않는다
        self.assertIsNone(review.write_worker_commands(self.dir, self.log(lines(use("t", "ls", name="Read")))))
        self.assertFalse((self.dir / "worker-commands.txt").exists())
        self.assertIsNone(review.write_worker_commands(self.dir, None))
        self.assertIsNone(review.write_worker_commands(self.dir, self.dir / "none.log"))

    def test_unwritable_dir_does_not_raise(self):
        self.assertIsNone(review.write_worker_commands(self.dir / "no" / "such", self.log(lines(codex("ls", 0)))))


class PromptTest(unittest.TestCase):
    d = Path("/d.patch")

    def prompts(self, path):
        d = self.d
        return (review.review_prompt(d, d, d, d, worker_commands=path),
                review.rereview_prompt(d, d, d, d, d, worker_commands=path),
                review.repair_review_prompt(d, "/v.log", d, d, d, worker_commands=path))

    def test_prompts_list_the_file_and_compare_reasons(self):
        path = Path("/r/worker-commands.txt")
        for prompt in self.prompts(path):
            self.assertEqual(prompt.count(str(path)), 2)
            self.assertIn("실행 기록", prompt)
            self.assertIn("대조", prompt)
            self.assertIn("기록과 다른 사유로 지적", prompt)

    def test_prompts_unchanged_without_file(self):
        for prompt in self.prompts(None):
            self.assertNotIn("worker-commands", prompt)
            self.assertNotIn("실행 기록", prompt)
        self.assertEqual(review.review_prompt(self.d, self.d, self.d, self.d),
                         review.review_prompt(self.d, self.d, self.d, self.d, None, "", None))

    def test_both_files_can_be_listed(self):
        prompt = review.review_prompt(self.d, self.d, self.d, self.d, Path("/r/worker-last.txt"), "", Path("/r/worker-commands.txt"))
        self.assertIn("/r/worker-last.txt", prompt)
        self.assertIn("/r/worker-commands.txt", prompt)


class ReviewerInputTest(support.GoTest):
    """gs go 안에서: 첫 리뷰와 재리뷰 프롬프트가 실행 기록 파일을 가리킨다."""

    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"u1","name":"Bash","input":{"command":"UNIQUECMD-'"$GS_TICKET"'"}}]}}'
            echo '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"u1","content":"Exit code 3\\nnope","is_error":true}]}}'
            echo '{"type":"result","subtype":"success","result":"보고"}'
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
            fi
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        (self.bin / "reviewer.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            cat > "$here/review.prompt"
            n=$(( $(cat "$here/review.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/review.n"
            cmds=$(grep -o '/[^ `]*worker-commands.txt' "$here/review.prompt" | head -n 1)
            { echo "== $n: ${cmds:-없음}"; [ -n "$cmds" ] && cat "$cmds"; } >> "$here/worker-commands.seen"
            cp "$here/review.prompt" "$here/review.prompt.$n"
            if [ -f "$here/findings.json" ] && [ "$n" = 1 ]; then echo '```json'; cat "$here/findings.json"; echo '```'
            else echo '{"findings": [], "verdicts": [{"id": 1, "status": "resolved", "evidence": "확인"}]}'; fi
        '''))

    def test_first_review_and_rereview_get_the_commands(self):
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        first, second = (self.bin / "worker-commands.seen").read_text().split("== 2: ")
        self.assertIn("UNIQUECMD-01", first)
        self.assertIn("[실패] UNIQUECMD-01 — 종료 3", first)
        self.assertIn("UNIQUECMD-01", second)
        self.assertTrue((self.rundir / "01/1/review/worker-commands.txt").is_file())
        self.assertTrue((self.rundir / "01/1/rereview1-codex/worker-commands.txt").is_file())
        self.assertIn("기록과 다른 사유로 지적", (self.bin / "review.prompt.1").read_text())
        self.assertIn("기록과 다른 사유로 지적", (self.bin / "review.prompt.2").read_text())

    def test_no_commands_means_no_file_and_review_still_runs(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            echo plain text, not json
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.review_state("01")["note"], "")
        self.assertFalse((self.rundir / "01/1/review/worker-commands.txt").exists())
        self.assertIn("== 1: 없음", (self.bin / "worker-commands.seen").read_text())
        self.assertNotIn("worker-commands", (self.bin / "review.prompt.1").read_text())


if __name__ == "__main__":
    unittest.main()
