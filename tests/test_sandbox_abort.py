"""실행 중 샌드박스 실패(goldstack-v32 04): codex·agy 샌드박스가 명령을 띄우지 못하면 재시도·병합하지 않고 `중단(샌드박스)`로 멈춘다.

가짜 CLI와 가짜 리뷰어(GS_REVIEWER_CMD)는 출력 파일을 그대로 내고 끝난다. 실제 시간(잠, 짧은 제한)에 기대지 않는다.
"""
import contextlib
import io
import json
import os
import textwrap
import unittest
from types import SimpleNamespace
from unittest import mock

import support
from support import sh

from gs import config, feedback, go, state, transient

BWRAP = "bwrap: Failed to make / slave: Permission denied"
AGY_DOWN = "Command failed to run: connecting to sandbox server: read unix @->@: recvmsg: connection reset by peer."
SANDBOX_LINE = "■ 중단(샌드박스): 머신의 샌드박스를 고치거나 GS_SANDBOX=landlock을 켠 뒤 gs go로 잇는다"
NETWORK_LINE = "■ 중단(네트워크): 다음 gs go가 이어 간다"
NO_FINDINGS = '```json\n{"findings": []}\n```'


def command(cmd, output, code):
    """codex `--json`의 끝난 command_execution 이벤트 한 줄."""
    return json.dumps({"type": "item.completed", "item": {
        "id": "item_1", "type": "command_execution", "command": cmd, "aggregated_output": output, "exit_code": code,
        "status": "completed" if code == 0 else "failed"}})


def agent_message(text):
    return json.dumps({"type": "item.completed", "item": {"id": "item_2", "type": "agent_message", "text": text}})


def agy_step(step_state, *, error="", output=""):
    """agy stream-json의 tool 단계 한 줄(streamfmt.py가 읽는 모양)."""
    info = {"parameters": {"CommandLine": "ls"}}
    if error:
        info["error"] = {"message": error}
    if output:
        info["output"] = output
    return json.dumps({"event": "step_update", "step_update": {
        "step_type": "tool", "state": step_state, "tool_name": "run_command", "tool_info": info}})


def agy_result(response):
    return json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": response}})


class SandboxFailureTest(unittest.TestCase):
    def test_codex_failed_command_whose_output_starts_with_bwrap(self):
        log = "\n".join([command("git status", "On branch x\n", 0), command("ls", BWRAP + "\nmore\n", 1)])
        self.assertEqual(transient.sandbox_failure("codex", log), BWRAP)

    def test_codex_requires_bubblewrap(self):
        line = "error: codex requires bubblewrap (bwrap) to run commands"
        self.assertEqual(transient.sandbox_failure("codex", command("ls", line + "\n", 127)), line)

    def test_codex_no_false_positive(self):
        cases = {
            "종료 0, 출력 중간의 bwrap": command("printf", "ok\nbwrap: in the middle\n", 0),
            "성공한 cat의 첫 줄이 bwrap": command("cat notes.txt", BWRAP + "\n", 0),
            "실패했지만 첫 줄이 아님": command("make", "error\nbwrap: later line\n", 2),
            "모델 답": agent_message(BWRAP),
            "이벤트가 아닌 줄": BWRAP,
            "끝나지 않은 명령": json.dumps({"type": "item.started", "item": {
                "type": "command_execution", "command": "ls", "aggregated_output": BWRAP, "exit_code": None}}),
        }
        for name, log in cases.items():
            with self.subTest(name):
                self.assertEqual(transient.sandbox_failure("codex", log), "")

    def test_agy_stream_json_error_tool_step(self):
        log = "\n".join([agy_step("DONE", output="ok"), agy_step("ERROR", error=AGY_DOWN + "\ndetail")])
        self.assertEqual(transient.sandbox_failure("agy", log), AGY_DOWN)

    def test_agy_text_line_start(self):
        self.assertEqual(transient.sandbox_failure("agy", "검토를 시작한다\n" + AGY_DOWN + "\n" + '{"findings": []}'), AGY_DOWN)

    def test_agy_no_false_positive(self):
        pretty = json.dumps({"findings": [{"severity": "low", "location": "a", "claim": AGY_DOWN, "evidence": AGY_DOWN}]},
                            ensure_ascii=False, indent=2)
        cases = {
            "DONE 도구 출력": agy_step("DONE", output=AGY_DOWN),
            "다른 오류의 메시지 중간": agy_step("ERROR", error="exit status 1: " + AGY_DOWN),
            "모델 답(result)": agy_result(AGY_DOWN),
            "리뷰 답 한 줄 JSON": json.dumps({"findings": [], "checked": [AGY_DOWN]}),
            "리뷰 답 여러 줄 JSON": pretty,
            "줄 중간의 문구": f"로그에 `{AGY_DOWN}`가 있다",
        }
        for name, log in cases.items():
            with self.subTest(name):
                self.assertEqual(transient.sandbox_failure("agy", log), "")

    def test_other_families_never(self):
        for family in ("claude", "custom", ""):
            with self.subTest(family):
                self.assertEqual(transient.sandbox_failure(family, command("ls", BWRAP, 1) + "\n" + AGY_DOWN), "")

    def test_sandbox_abort_is_network_abort_with_its_kind(self):
        self.assertTrue(issubclass(transient.SandboxAbort, transient.NetworkAbort))
        self.assertEqual((transient.NetworkAbort("x").kind, transient.SandboxAbort("x").kind), ("network", "sandbox"))


class EnvironmentalTest(unittest.TestCase):
    """결함 수집은 샌드박스 실패를 goldstack 결함이 아니라 환경 탓으로 본다."""

    def test_sandbox_phrases_are_environmental(self):
        for line in ("bwrap: Can't mount proc on /newroot/proc: Operation not permitted",
                     "error: codex requires bubblewrap (bwrap)",
                     "Command failed to run: connecting to sandbox server: dial unix /tmp/agy.sock: no such file or directory"):
            with self.subTest(line):
                self.assertTrue(feedback._environmental(line))

    def test_adapter_failure_with_sandbox_stderr_is_not_reported(self):
        log = "Command failed to run: connecting to sandbox server: dial unix /tmp/agy.sock: no such file or directory\n"
        self.assertIsNone(feedback.classify_adapter_failure("agy: result 이벤트가 없다", log))
        self.assertIsNotNone(feedback.classify_adapter_failure("agy: result 이벤트가 없다", "boom\n"))  # 문구 없이는 올린다


def run_like(network):
    return SimpleNamespace(st=state.State(feature="demo", network=dict(network)), order=[], prior=set(), name="demo")


class LabelTest(unittest.TestCase):
    """끝 안내 말고 사람에게 보이는 결과(_outcome)·요약·알림이 중단 종류를 따른다. kind가 없는 옛 state는 네트워크 중단이다."""

    def labels(self, network):
        r = run_like(network)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            go._only_summary(r)
        return go.abort_label(r.st), go._outcome(r), go._message(r, None, False), go._only_message(r, False), out.getvalue()

    def test_each_kind(self):
        for network, label in (({"aborted": "x", "kind": "sandbox"}, "중단(샌드박스)"),
                               ({"aborted": "x", "kind": "network"}, "중단(네트워크)"),
                               ({"aborted": "x"}, "중단(네트워크)")):  # 옛 state
            with self.subTest(network):
                shown, outcome, message, only_message, summary = self.labels(network)
                other = ({"중단(샌드박스)", "중단(네트워크)"} - {label}).pop()
                self.assertEqual((shown, outcome), (label, label))
                self.assertTrue(message.startswith(f"❌ demo · {label} · "), message)
                self.assertIn(f" · {label} · ", only_message)
                self.assertIn(f"■ 마무리: {label}", summary)
                for text in (message, only_message, summary):
                    self.assertNotIn(other, text)


def codex_ticket(tid, reviewer="claude"):
    return f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: []\nmodel: codex\nreviewer: {reviewer}\n---\n## 목표\n{tid}\n'


class SandboxAbortGoTest(support.GoTest):
    """gs go 전체. codex worker는 실제 어댑터로 가짜 `codex`를 띄우고, 리뷰어는 GS_REVIEWER_CMD 가짜다."""

    def fake_cli(self, name, body):
        """가짜 모델 CLI. 부를 때마다 `<이름>.calls`에 티켓을 남긴다."""
        path = self.bin / name
        path.write_text('#!/bin/bash\nhere="$(dirname "$0")"\n'
                        'if [ "$1" = plugin ]; then echo "[]"; exit 0; fi\n'
                        f'echo "$GS_TICKET" >> "$here/{name}.calls"\n' + textwrap.dedent(body))
        path.chmod(0o755)

    def codex_worker(self, events, commit=False):
        """codex worker: `codex.out`의 이벤트를 내고 종료 0. `up` 파일이 생기면 정상 worker(커밋)다."""
        os.environ.pop("GS_WORKER_CMD")
        (self.bin / "codex.out").write_text("\n".join(events) + "\n")
        self.fake_cli("codex", f'''\
            if [ -f "$here/up" ]; then echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"; exit 0; fi
            cat "$here/codex.out"
            {'echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"' if commit else ''}
            exit 0
        ''')

    def reviewer(self):
        """리뷰어: `review_<계열>.out`을 그대로 낸다(계열은 GS_REVIEWER)."""
        (self.bin / "reviewer.sh").write_text('here="$(dirname "$0")"\ncat > /dev/null\n'
                                              'echo "$GS_REVIEWER" >> "$here/review.calls"\n'
                                              'cat "$here/review_$GS_REVIEWER.out"\n')

    def review_out(self, family, *lines):
        (self.bin / f"review_{family}.out").write_text("\n".join(lines) + "\n")

    def tickets(self, **bodies):
        for tid, body in bodies.items():
            (self.repo / f".goldstack/work/demo/tickets/{tid}-t.md").write_text(body)
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "tickets")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def notify_on(self):
        """텔레그램 알림을 켜고 보낸 본문을 모은다(실제 전송 없음)."""
        cfg = self.repo / config.CONFIG_PATH
        cfg.write_text(cfg.read_text().replace("telegram = false", "telegram = true"))
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n.goldstack/local.env\n")
        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=t\nTG_CHAT_ID=1\n")
        sent = []
        patch = mock.patch("gs.notify.send", side_effect=lambda token, chat, text: (sent.append(text), (True, ""))[1])
        patch.start()
        self.addCleanup(patch.stop)
        return sent

    def ticket_state(self, tid):
        return state.load(self.rundir, "demo").tickets[tid]

    def assert_sandbox_abort(self, code, out, err, tid):
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 샌드박스 중단 이유: ", out)
        self.assertIn(SANDBOX_LINE, out)
        self.assertIn("■ 마무리: 중단(샌드박스)", out)
        self.assertNotIn("중단(네트워크)", out)
        self.assertNotIn("네트워크 중단 이유", out)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn(f"gs-ticket: demo/{tid}", self.integration("log", "--format=%B", "gs/demo/integration"))
        st = state.load(self.rundir, "demo")
        ts = st.tickets[tid]
        self.assertEqual((ts.status, ts.failures, ts.reason), ("pending", 0, "중단(샌드박스)"), out)
        self.assertEqual(st.network["kind"], "sandbox")
        self.assertEqual(st.finish, {})  # 마무리를 하지 않았다
        self.assertFalse((self.bin / "gh.log").exists())
        return st, ts

    def test_codex_worker_bwrap_stops_without_retry_then_next_go_continues(self):
        sent = self.notify_on()
        self.codex_worker([command("git status", BWRAP + "\n", 1), agent_message("명령이 돌지 않는다")])
        self.tickets(**{"11": codex_ticket("11")})
        code, out, err = self.go("--only", "11")
        st, ts = self.assert_sandbox_abort(code, out, err, "11")
        self.assertIn(f"■ 샌드박스 중단 이유: [11] worker(codex)의 명령이 샌드박스에서 돌지 못했다: {BWRAP}", out)
        self.assertEqual(self.lines("codex.calls"), ["11"])  # 재시도하지 않았다
        self.assertEqual(ts.attempts, 1)
        self.assertEqual(ts.network_resume["worktree"], str(self.rundir / "wt/11"))
        self.assertFalse(ts.network_resume["done"])
        self.assertIn(BWRAP, st.network["aborted"])
        self.assertEqual(sent, ["❌ demo · 중단(샌드박스) · 티켓 0/1 · 보고서 .goldstack/work/demo/report.md"])
        _, shown = self.status("demo")
        self.assertIn("중단(샌드박스)", shown.splitlines()[0])

        (self.bin / "up").touch()  # 샌드박스를 고쳤다
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("중단", out)
        self.assertEqual(self.lines("codex.calls"), ["11", "11"])
        st = state.load(self.rundir, "demo")
        ts = st.tickets["11"]
        self.assertEqual((ts.status, ts.failures, ts.branch), ("merged", 0, "gs/demo/11"), out)  # 같은 worktree에서 이었다
        self.assertNotIn("aborted", st.network)
        self.assertNotIn("kind", st.network)

    def test_codex_worker_bwrap_with_commit_is_not_merged(self):
        """종료 0에 커밋까지 남겨도 성공으로 판정하기 전에 멈춘다."""
        self.codex_worker([command("python -m unittest", BWRAP + "\n", 1)], commit=True)
        self.tickets(**{"11": codex_ticket("11")})
        code, out, err = self.go("--only", "11")
        self.assert_sandbox_abort(code, out, err, "11")
        self.assertEqual(self.lines("codex.calls"), ["11"])
        self.assertEqual(self.lines("review.calls"), [])  # 리뷰로도 가지 않았다

    def test_codex_reviewer_bwrap_discards_clean_answer_then_next_go_reviews_again(self):
        self.reviewer()
        self.review_out("codex", command("cat diff.patch", BWRAP + "\n", 1), agent_message("지적 없음"), NO_FINDINGS)
        code, out, err = self.go("--only", "01")
        _, ts = self.assert_sandbox_abort(code, out, err, "01")
        self.assertIn(BWRAP, out)
        self.assertEqual(self.lines("review.calls"), ["codex"])  # 같은 실패로 다시 부르지 않았다
        self.assertEqual(ts.review, {})  # 리뷰 실패로도, 지적 0건 리뷰로도 적지 않았다
        self.assertTrue(ts.network_resume["done"])

        self.review_out("codex", NO_FINDINGS)  # 샌드박스를 고쳤다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않고 리뷰부터 이었다
        self.assertEqual(self.lines("review.calls"), ["codex", "codex"])
        ts = self.ticket_state("01")
        self.assertEqual((ts.status, ts.attempts, ts.failures, ts.review["note"]), ("merged", 1, 0, ""))

    def test_agy_reviewer_sandbox_server_line_stops_and_old_state_reads_as_network(self):
        support.fake_clis(self, "agy")
        self.tickets(**{"01": support.ticket("01").replace("reviewer: codex", "reviewer: agy")})
        self.reviewer()
        self.review_out("agy", AGY_DOWN, '{"findings": []}')
        code, out, err = self.go("--only", "01")
        _, ts = self.assert_sandbox_abort(code, out, err, "01")
        self.assertIn(AGY_DOWN, out)
        self.assertEqual(self.lines("review.calls"), ["agy"])
        self.assertEqual(ts.review, {})
        self.assertTrue(ts.network_resume["done"])

        # kind가 없는 옛 state는 네트워크 중단으로 읽힌다
        path = state.path(self.rundir)
        raw = json.loads(path.read_text(encoding="utf-8"))
        del raw["network"]["kind"]
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        _, shown = self.status("demo")
        self.assertIn("중단(네트워크)", shown.splitlines()[0])
        self.assertEqual(go.abort_label(state.load(self.rundir, "demo")), "중단(네트워크)")

    def test_no_false_positive_runs_to_merge(self):
        support.fake_clis(self, "agy")
        self.codex_worker([command("printf ok", "ok\nbwrap: in the middle\n", 0),
                           command("cat notes.txt", BWRAP + "\n", 0),
                           command("make", "error\nbwrap: later line\n", 2),
                           agent_message(BWRAP)], commit=True)
        self.fake_cli("claude", 'echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"\n')
        self.tickets(**{"11": codex_ticket("11", reviewer="agy")})
        self.reviewer()
        self.review_out("codex", command("cat notes.txt", BWRAP + "\n", 0), command("make", "x\nbwrap: y\n", 2), NO_FINDINGS)
        answer = json.dumps({"findings": [], "checked": [AGY_DOWN]}, ensure_ascii=False, indent=2)
        self.review_out("agy", f"worker 로그의 `{AGY_DOWN}` 줄은 시험 데이터다.", answer)
        code, out, err = self.go("--only", "01,11")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("중단", out)
        self.assertEqual(sorted(self.lines("review.calls")), ["agy", "codex"])
        st = state.load(self.rundir, "demo")
        for tid in ("01", "11"):
            self.assertEqual((st.tickets[tid].status, st.tickets[tid].review["note"]), ("merged", ""), tid)

    def test_network_abort_keeps_network_wording(self):
        with mock.patch("gs.review.run", side_effect=transient.NetworkAbort("리뷰 끊김")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 네트워크 중단 이유: 리뷰 끊김", out)
        self.assertIn(NETWORK_LINE, out)
        self.assertIn("■ 마무리: 중단(네트워크)", out)
        self.assertNotIn("샌드박스", out)
        st = state.load(self.rundir, "demo")
        self.assertEqual((st.network["kind"], st.tickets["01"].reason), ("network", "중단(네트워크)"))
        _, shown = self.status("demo")
        self.assertIn("중단(네트워크)", shown.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
