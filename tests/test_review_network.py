"""리뷰·판단 호출(v7 07): 끊기면 기다렸다 다시 부르고, 넘기면 중단하고, 끝날 때 프로세스 그룹을 남기지 않는다."""
import json
import os
import stat
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from support import alive

from gs import config, failure, go, report, review, state, transient, verify

CLAUDE_DOWN = ('{"type":"result","is_error":true,"api_error":"connection_failed","terminal_reason":"api_error",'
               '"result":"API Error: Connection refused (ECONNREFUSED)"}')
CLAUDE_AUTH = '{"type":"result","is_error":true,"result":"authentication failed: invalid api key"}'
CODEX_DOWN = '{"type":"error","message":"stream disconnected before completion: error sending request"}'
CODEX_AUTH = '{"type":"turn.failed","error":{"message":"401 Unauthorized"}}'
AGY_DOWN = "error: failed to connect: connection refused"
NO_FINDINGS = '{"findings": []}'
ONE_FINDING = '{"findings": [{"severity": "high", "location": "a", "claim": "FIX", "evidence": "e"}]}'


def claude_answer(text):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text}, ensure_ascii=False)


def models():
    return config.ModelsConfig(judge="judge-m", claude_review="review-m", agy="agy-m", codex="codex-m")


def make_cfg(limit=1, review_minutes=30, rereview_minutes=10, judge_minutes=10, summary_seconds=60):
    return SimpleNamespace(models=models(), timeouts=config.TimeoutsConfig(
        review_minutes=review_minutes, judge_minutes=judge_minutes, summary_seconds=summary_seconds,
        rereview_minutes=rereview_minutes, network_wait_minutes=limit))


class Base(unittest.TestCase):
    """가짜 CLI를 PATH에 둔다. 1분 = 0.01초(GS_NETWORK_MINUTE). 상한 1분이면 대기 1번(0.01초) 뒤 다시 끊겨 넘는다."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name).resolve()
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        patch = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                                             "GS_NETWORK_MINUTE": "0.01", "HERE": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("GS_REVIEWER_CMD", "GS_JUDGE", "GS_AGY"):
            os.environ.pop(name, None)
        self.rdir = self.dir / "r"
        self.rdir.mkdir()

    def script(self, name, body):
        """부를 때마다 회차 n을 세는 가짜 CLI. 인자·stdin은 시험이 볼 수 있게 남긴다."""
        path = self.bin / name
        path.write_text('#!/bin/bash\nhere="$HERE"\n'
                        f'n=$(( $(cat "$here/n_{name}" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/n_{name}"\n'
                        f'echo "$@" > "$here/args_{name}"\n' + textwrap.dedent(body))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def calls(self, name):
        path = self.bin / f"n_{name}"
        return int(path.read_text()) if path.exists() else 0

    def run_review(self, reviewer="claude", cfg=None, on_wait=None):
        with mock.patch.object(review, "write_diff", return_value=("base", False)), \
                mock.patch.object(review, "_env", return_value=dict(os.environ)):
            return review.run(repo=self.dir, worktree=self.dir, rdir=self.rdir, base="base", branch="t",
                              ticket=self.dir / "ticket", spec=self.dir / "spec",
                              model="agy" if reviewer != "agy" else "claude", reviewer=reviewer,
                              cfg=cfg or make_cfg(limit=5), on_wait=on_wait)

    def run_rereview(self, reviewer="claude", cfg=None, nth=1):
        found = [{"id": 1, "severity": "high", "location": "a", "claim": "c", "evidence": "e"}]
        with mock.patch.object(review.git, "run", return_value=SimpleNamespace(stdout="diff")), \
                mock.patch.object(review, "_env", return_value=dict(os.environ)):
            return review.rereview(repo=self.dir, worktree=self.dir, rdir=self.rdir, base="a", head="b", found=found,
                                   ticket=self.dir / "ticket", spec=self.dir / "spec", reviewer=reviewer,
                                   cfg=cfg or make_cfg(limit=5), nth=nth)


class CallTest(Base):
    def call(self, body, *, timeout=30, family="", prompt="p"):
        path = self.script("cli", body)
        return review._call([str(path)], prompt=prompt, cwd=self.dir, env=dict(os.environ), log=self.rdir / "cli.log",
                            timeout=timeout, family=family)

    def wait_dead(self, pid):
        for _ in range(100):
            if not alive(pid):
                return
            time.sleep(0.02)
        self.fail(f"{pid}가 살아 있다")

    def test_runs_in_new_process_group(self):
        out = self.call('ps -o pgid= -p $$ | tr -d " "; echo $$; cat', prompt="hello")
        pgid, pid, prompt = out.split("\n")[:3]
        self.assertEqual(pgid, pid)  # 자기가 그룹의 리더다
        self.assertNotEqual(int(pgid), os.getpgid(0))
        self.assertEqual(prompt, "hello")

    def test_timeout_leaves_no_child(self):
        with self.assertRaises(review.ReviewTimeout) as caught:
            self.call('sleep 300 & echo $! > "$here/child"; echo $$ > "$here/leader"; wait', timeout=1)
        self.assertIn("초 안에 끝나지 않았다", str(caught.exception))
        self.wait_dead(int((self.bin / "child").read_text()))
        self.assertFalse(alive(int((self.bin / "leader").read_text())))

    def test_timeout_kills_after_grace_when_sigterm_is_ignored(self):
        body = '''\
            trap '' TERM
            bash -c 'trap "" TERM; echo $$ > "$HERE/child"; while :; do sleep 0.05; done' &
            echo $$ > "$here/leader"
            while :; do sleep 0.05; done
        '''
        with mock.patch.object(verify, "GRACE", 0.3), self.assertRaises(review.ReviewTimeout):
            self.call(body, timeout=1)
        self.assertFalse(alive(int((self.bin / "leader").read_text())))
        self.wait_dead(int((self.bin / "child").read_text()))

    def test_child_holding_stdout_after_leader_exit_cannot_hang_past_timeout(self):
        start = time.monotonic()
        with self.assertRaises(review.ReviewTimeout):
            self.call('sleep 300 & echo $! > "$here/child"; exit 0', timeout=1)
        self.assertLess(time.monotonic() - start, 10)
        self.wait_dead(int((self.bin / "child").read_text()))

    def test_normal_end_leaves_no_background_child(self):
        out = self.call('sleep 300 >/dev/null 2>&1 & echo $! > "$here/child"; echo answer')
        self.assertEqual(out.strip(), "answer")
        self.wait_dead(int((self.bin / "child").read_text()))

    def test_interrupt_stops_the_group(self):
        path = self.script("cli", 'sleep 300 & echo $! > "$here/child"; wait')
        real = review.subprocess.Popen.communicate

        def interrupted(p, *a, **kw):
            with self.assertRaises(review.subprocess.TimeoutExpired):
                real(p, *a, **{**kw, "timeout": 1})
            raise KeyboardInterrupt

        with mock.patch.object(review.subprocess.Popen, "communicate", interrupted), self.assertRaises(KeyboardInterrupt):
            review._call([str(path)], prompt="p", cwd=self.dir, env=dict(os.environ), log=self.rdir / "cli.log", timeout=30)
        self.wait_dead(int((self.bin / "child").read_text()))

    def test_missing_program_is_review_error(self):
        with self.assertRaises(review.ReviewError) as caught:
            review._call([str(self.bin / "none")], prompt="p", cwd=self.dir, env={}, log=self.rdir / "x.log", timeout=1)
        self.assertNotIsInstance(caught.exception, (review.ReviewTransient, review.ReviewTimeout))

    def test_claude_result_is_unwrapped_and_plain_seam_stays(self):
        answer = json.dumps(claude_answer("답"), ensure_ascii=False)
        self.assertEqual(self.call(f"echo {answer}", family="claude"), "답")
        self.assertEqual(self.call(f"echo {NO_FINDINGS!r}", family="claude").strip(), NO_FINDINGS)

    def test_transient_is_read_from_stdout_and_stderr_per_family(self):
        for family, body in (("claude", f"echo '{CLAUDE_DOWN}'; exit 1"),
                             ("codex", f"echo '{CODEX_DOWN}'; exit 1"),
                             ("codex", f"echo '{CODEX_DOWN}' >&2; exit 1"),
                             ("agy", f"echo '{AGY_DOWN}' >&2; exit 1")):
            with self.subTest(family=family, body=body), self.assertRaises(review.ReviewTransient):
                self.call(body, family=family)
            self.assertIn("{" if family != "agy" else "error:", (self.rdir / "cli.log").read_text())  # 증거가 로그에 남는다

    def test_other_failures_are_not_transient(self):
        for family, body in (("claude", f"echo '{CLAUDE_AUTH}'; exit 1"),
                             ("claude", "echo 'connection refused'; exit 1"),  # 이벤트 밖 문자열은 근거가 아니다
                             ("codex", f"echo '{CODEX_AUTH}'; exit 1"),
                             ("codex", "echo boom >&2; exit 1"),
                             ("agy", "echo 'tests failed: connection refused' ; exit 1"),
                             ("", f"echo '{CLAUDE_DOWN}'; exit 1")):
            with self.subTest(family=family, body=body), self.assertRaises(review.ReviewError) as caught:
                self.call(body, family=family)
            self.assertNotIsInstance(caught.exception, review.ReviewTransient)

    def test_agy_json_answer_does_not_hide_stderr(self):
        answer = f"echo '{NO_FINDINGS}'"
        with self.assertRaises(review.ReviewTransient):
            self.call(f"echo '{AGY_DOWN}' >&2; {answer}; exit 1", family="agy")
        self.assertIn(NO_FINDINGS, (self.rdir / "cli.log").read_text())  # 답도 증거로 남는다
        for stderr in ("error: authentication failed: connection refused", "boom"):  # 인증·모르는 오류는 그대로 리뷰 실패다
            with self.subTest(stderr=stderr), self.assertRaises(review.ReviewError) as caught:
                self.call(f"echo '{stderr}' >&2; {answer}; exit 1", family="agy")
            self.assertNotIsInstance(caught.exception, review.ReviewTransient)

    def test_claude_error_result_with_exit_zero_is_not_an_answer(self):
        with self.assertRaises(review.ReviewTransient):
            self.call(f"echo '{CLAUDE_DOWN}'; exit 0", family="claude")
        with self.assertRaises(review.ReviewError) as caught:
            self.call(f"echo '{CLAUDE_AUTH}'; exit 0", family="claude")
        self.assertIn("오류 result", str(caught.exception))

    def test_deeply_nested_answer_is_not_a_crash(self):
        deep = "[" * 200000
        self.assertEqual(self.call(f'echo "{deep[:60000]}"; exit 0', family="claude").strip(), deep[:60000])


class WaitingTest(Base):
    def down_then(self, name, down, answer, times=1):
        return self.script(name, f'''\
            cat > /dev/null
            if [ $n -le {times} ]; then echo '{down}'; exit 1; fi
            echo '{answer}'
        ''')

    def test_schedule_is_the_shared_backoff(self):
        waits = []
        self.down_then("claude", CLAUDE_DOWN, NO_FINDINGS, times=5)
        rec = self.run_review(cfg=make_cfg(limit=60), on_wait=lambda why, n, s, family: waits.append((n, round(s, 3), family)))
        self.assertEqual(rec["findings"], [])
        self.assertEqual(rec["note"], "")
        self.assertEqual(waits, [(1, 0.01, "claude"), (2, 0.02, "claude"), (3, 0.05, "claude"), (4, 0.1, "claude"),
                                 (5, 0.1, "claude")])
        self.assertEqual(self.calls("claude"), 6)

    def test_claude_reviewer_real_argv_retries_and_reads_result(self):
        self.down_then("claude", CLAUDE_DOWN, claude_answer(NO_FINDINGS).replace("'", ""))
        rec = self.run_review("claude")
        self.assertEqual((rec["note"], rec["findings"]), ("", []))
        self.assertEqual(self.calls("claude"), 2)
        self.assertIn("--output-format json", (self.bin / "args_claude").read_text())
        self.assertEqual((self.rdir / "review.txt").read_text(), NO_FINDINGS)

    def test_codex_reviewer_real_argv_retries_with_events_on_stdout(self):
        self.script("codex", f'''\
            cat > /dev/null
            out="${{@: -2:1}}"
            if [ $n = 1 ]; then echo stale > "$out"; echo '{CODEX_DOWN}'; exit 1; fi
            echo '{{"type":"turn.completed"}}'
            echo '{NO_FINDINGS}' > "$out"
        ''')
        rec = self.run_review("codex")
        self.assertEqual((rec["note"], rec["findings"]), ("", []))
        self.assertEqual(self.calls("codex"), 2)
        self.assertIn("exec --json", (self.bin / "args_codex").read_text())

    def test_codex_answer_of_failed_attempt_is_not_read(self):
        """앞 시도가 쓴 답 파일을 다음 시도의 답으로 읽지 않는다."""
        self.script("codex", f'''\
            cat > /dev/null
            out="${{@: -2:1}}"
            if [ $n = 1 ]; then echo '{ONE_FINDING}' > "$out"; echo '{CODEX_DOWN}'; exit 1; fi
            echo '{{"type":"turn.completed"}}'
        ''')
        rec = self.run_review("codex")
        self.assertIn("리뷰 실패", rec["note"])
        self.assertEqual(rec["findings"], [])

    def test_agy_reviewer_real_argv_retries(self):
        self.script("agy", f'''\
            if [ $n = 1 ]; then echo '{AGY_DOWN}' >&2; exit 1; fi
            echo '{NO_FINDINGS}'
        ''')
        os.environ["GS_AGY"] = str(self.bin / "agy")
        rec = self.run_review("agy")
        self.assertEqual((rec["note"], rec["findings"]), ("", []))
        self.assertEqual(self.calls("agy"), 2)

    def test_agy_reviewer_retries_when_json_answer_comes_with_connection_error(self):
        self.script("agy", f'''\
            if [ $n = 1 ]; then echo '{AGY_DOWN}' >&2; echo '{ONE_FINDING}'; exit 1; fi
            echo '{NO_FINDINGS}'
        ''')
        os.environ["GS_AGY"] = str(self.bin / "agy")
        rec = self.run_review("agy")
        self.assertEqual((rec["note"], rec["findings"]), ("", []))
        self.assertEqual(self.calls("agy"), 2)

    def test_seam_reviewer_uses_ticket_family(self):
        path = self.down_then("seam", CODEX_DOWN, NO_FINDINGS)
        os.environ["GS_REVIEWER_CMD"] = f"bash {path}"
        rec = self.run_review("codex")
        self.assertEqual((rec["note"], rec["findings"]), ("", []))
        self.assertEqual(self.calls("seam"), 2)

    def test_reviewer_beyond_limit_raises_abort_not_failure(self):
        self.down_then("claude", CLAUDE_DOWN, NO_FINDINGS, times=99)
        with self.assertRaises(transient.NetworkAbort) as caught:
            self.run_review(cfg=make_cfg(limit=1))
        self.assertEqual(self.calls("claude"), 2)  # 처음 + 대기 1번 뒤
        self.assertIn("대기 합계가 상한 1분을 넘었다", str(caught.exception))
        self.assertIn("timeouts.network_wait_minutes", str(caught.exception))

    def test_timeouts_retry_and_abort_too(self):
        call = review._call

        def short(argv, **kw):
            return call(argv, **{**kw, "timeout": 1})

        self.script("claude", 'sleep 300 & echo $! > "$here/child$n"; wait')
        with mock.patch.object(review, "_call", side_effect=short), self.assertRaises(transient.NetworkAbort) as caught:
            self.run_review(cfg=make_cfg(limit=1))
        self.assertIn("초 안에 끝나지 않았다", str(caught.exception))
        self.assertEqual(self.calls("claude"), 2)
        for n in (1, 2):
            self.assertFalse(alive(int((self.bin / f"child{n}").read_text())))

    def test_retry_starts_after_previous_call_ended(self):
        call = review._call

        def short(argv, **kw):
            return call(argv, **{**kw, "timeout": 1})

        # 앞 회차의 프로세스가 살아 있으면 표시를 남긴다. 3회 부른다(대기 2번)
        self.script("claude", '''\
            for p in "$here"/pid_*; do
              [ -f "$p" ] && kill -0 "$(cat "$p")" 2>/dev/null && echo "$n $p" >> "$here/overlap"
            done
            echo $$ > "$here/pid_$n"
            sleep 300 & echo $! > "$here/pid_child_$n"
            wait
        ''')
        with mock.patch.object(review, "_call", side_effect=short), self.assertRaises(transient.NetworkAbort):
            self.run_review(cfg=make_cfg(limit=3))
        self.assertEqual(self.calls("claude"), 3)
        self.assertFalse((self.bin / "overlap").exists())

    def test_non_transient_review_failure_still_merges_with_note(self):
        for body in ("cat >/dev/null; echo boom >&2; exit 1", f"cat >/dev/null; echo '{CLAUDE_AUTH}'; exit 1",
                     "cat >/dev/null; echo not json"):
            with self.subTest(body=body):
                (self.bin / "n_claude").unlink(missing_ok=True)
                self.script("claude", body)
                rec = self.run_review()
                self.assertIn("리뷰 실패(리뷰 없음, verify만으로 병합한다)", rec["note"])
                self.assertEqual(self.calls("claude"), 1)  # 다시 부르지 않는다

    def test_classify_retries_then_applies(self):
        self.script("claude", f"cat >/dev/null; echo '{claude_answer(ONE_FINDING)}'")
        judge = self.down_then("judge", CLAUDE_DOWN, '{"decisions": [{"id": 1, "action": "fix", "why": "w"}]}')
        os.environ["GS_JUDGE"] = str(judge)
        rec = self.run_review()
        self.assertEqual(self.calls("judge"), 2)
        self.assertEqual((rec["note"], rec["findings"][0]["action"]), ("", review.FIX))
        self.assertIn("--output-format json", (self.bin / "args_judge").read_text())

    def test_classify_beyond_limit_raises_abort(self):
        self.script("claude", f"cat >/dev/null; echo '{claude_answer(ONE_FINDING)}'")
        os.environ["GS_JUDGE"] = str(self.down_then("judge", CLAUDE_DOWN, "", times=99))
        with self.assertRaises(transient.NetworkAbort):
            self.run_review(cfg=make_cfg(limit=1))

    def test_classify_other_failure_is_all_report(self):
        self.script("claude", f"cat >/dev/null; echo '{claude_answer(ONE_FINDING)}'")
        os.environ["GS_JUDGE"] = str(self.script("judge", "cat >/dev/null; echo boom >&2; exit 1"))
        rec = self.run_review()
        self.assertIn("판단 모델 호출 불가", rec["note"])
        self.assertEqual(rec["findings"][0]["action"], review.REPORT)

    def test_rereview_retries_then_reads_verdicts(self):
        answer = '{"verdicts": [{"id": 1, "status": "resolved", "evidence": "e"}], "findings": []}'
        self.down_then("claude", CLAUDE_DOWN, answer)
        res = self.run_rereview()
        self.assertEqual(res["failed"], "")
        self.assertEqual(res["verdicts"][1]["status"], "resolved")
        self.assertEqual(self.calls("claude"), 2)

    def test_rereview_beyond_limit_raises_abort(self):
        self.down_then("claude", CLAUDE_DOWN, "", times=99)
        with self.assertRaises(transient.NetworkAbort):
            self.run_rereview(cfg=make_cfg(limit=1))

    def test_rereview_timeout_beyond_limit_raises_abort(self):
        with mock.patch.object(review, "_call", side_effect=review.ReviewTimeout("x초 안에 끝나지 않았다")), \
                self.assertRaises(transient.NetworkAbort):
            self.run_rereview(cfg=make_cfg(limit=1))

    def test_rereview_other_failure_is_unchecked_reason(self):
        self.script("claude", "cat >/dev/null; echo boom >&2; exit 1")
        res = self.run_rereview()
        self.assertEqual(res["failed"], review.REASON_FAILED)
        self.assertEqual(self.calls("claude"), 1)

    def test_prompts_ask_for_narrow_reproduction_only(self):
        text = "전체 시험을 돌리지 말고 지적을 확인할 좁은 재현만 돌린다"
        p = Path("x")
        self.assertIn(text, review.review_prompt(p, p, p, p))
        self.assertIn(text, review.rereview_prompt(p, p, p, p, p))


class SummaryTest(Base):
    def report_run(self, limit):
        (self.dir / "iwt").mkdir()
        cfg = make_cfg(limit=limit)
        return SimpleNamespace(cfg=cfg, rundir=self.dir, iwt=self.dir / "iwt", base_ref="o/m",
                               feat=SimpleNamespace(spec=SimpleNamespace(path=self.dir / "spec")),
                               st=SimpleNamespace(finish={}))

    def summarize_report(self, limit, on_wait=None):
        r = self.report_run(limit)
        with mock.patch.object(report, "evidence", return_value="facts"), \
                mock.patch.object(report.git, "out", return_value="diff"), \
                mock.patch.object(review, "_env", return_value=dict(os.environ)):
            return report.summarize(r, on_wait)

    def summarize_failure(self, limit, on_wait=None):
        log = self.dir / "failure.log"
        log.write_text("x")
        return failure.summarize(self.dir, log, make_cfg(limit=limit), on_wait).read_text()

    def judge(self, body):
        os.environ["GS_JUDGE"] = str(self.script("judge", body))

    def test_report_summary_retries(self):
        self.judge(f"cat >/dev/null; if [ $n = 1 ]; then echo '{CLAUDE_DOWN}'; exit 1; fi; echo '{claude_answer('요약')}'")
        self.assertEqual(self.summarize_report(5), "요약")
        self.assertEqual(self.calls("judge"), 2)

    def test_report_summary_beyond_limit_uses_fallback_without_abort(self):
        self.judge(f"cat >/dev/null; echo '{CLAUDE_DOWN}'; exit 1")
        text = self.summarize_report(1)
        self.assertIn("보고서 판단 모델 호출 실패", text)
        self.assertIn("아래 gs 수집 증거를 확인하라", text)
        self.assertEqual(self.calls("judge"), 2)

    def test_report_summary_timeout_retries_then_fallback(self):
        with mock.patch.object(review, "_call", side_effect=review.ReviewTimeout("초과")) as call:
            text = self.summarize_report(1)
        self.assertEqual(call.call_count, 2)
        self.assertIn("보고서 판단 모델 호출 실패", text)

    def test_report_other_failure_uses_fallback_at_once(self):
        self.judge("cat >/dev/null; echo boom >&2; exit 1")
        self.assertIn("보고서 판단 모델 호출 실패", self.summarize_report(5))
        self.assertEqual(self.calls("judge"), 1)

    def test_failure_summary_retries(self):
        self.judge(f"cat >/dev/null; if [ $n = 1 ]; then echo '{CLAUDE_DOWN}'; exit 1; fi; echo '판단 요약'")
        text = self.summarize_failure(5)
        self.assertIn("판단 요약", text)
        self.assertEqual(self.calls("judge"), 2)

    def test_failure_summary_beyond_limit_uses_fallback_without_abort(self):
        self.judge(f"cat >/dev/null; echo '{CLAUDE_DOWN}'; exit 1")
        text = self.summarize_failure(1)
        self.assertIn("실패 요약 호출 불가", text)
        self.assertIn(str(self.dir / "failure.log"), text)
        self.assertEqual(self.calls("judge"), 2)

    def test_failure_summary_timeout_stops_children(self):
        self.judge('cat >/dev/null; sleep 300 & echo $! > "$here/child"; wait')
        log = self.dir / "failure.log"
        log.write_text("x")
        failure.summarize(self.dir, log, make_cfg(limit=1, summary_seconds=1))
        self.assertEqual(self.calls("judge"), 2)
        self.assertFalse(alive(int((self.bin / "child").read_text())))

    def test_failure_summary_empty_answer_uses_fallback(self):
        self.judge("cat >/dev/null")
        self.assertIn("실패 요약 호출 불가", self.summarize_failure(5))
        self.assertEqual(self.calls("judge"), 1)


class CallWaitTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "60"})
        patch.start()
        self.addCleanup(patch.stop)
        self.st = state.State(feature="demo")
        self.lines = []
        self.saves = []

    def waiter(self, tid="01"):
        return review.CallWait(self.st, lambda: self.saves.append(dict(self.st.network.get("wait") or {})), tid,
                               self.lines.append)

    def test_publishes_clears_and_counts(self):
        self.waiter()("`x` 일시 오류", 2, 0.05)
        self.assertEqual(self.saves[0]["count"], 2)
        self.assertEqual(self.st.network["wait"], {})
        self.assertEqual(self.st.network["errors"], 1)
        self.assertGreater(self.st.network["waited_seconds"], 0)
        ts = self.st.tickets["01"]
        self.assertEqual(ts.transient_errors, 1)
        self.assertGreater(ts.network_wait_seconds, 0)
        self.assertIn("[01] `x` 일시 오류. 네트워크 대기(2회, 1분 뒤)", self.lines[0])

    def test_progress_line_shows_network_wait(self):
        seen = []

        def save():
            progress = state.calculate_progress(self.st, [], 1)
            seen.append(progress["line"])

        review.CallWait(self.st, save, "", self.lines.append)("끊김", 1, 0.01)
        self.assertIn("네트워크 대기(1회", seen[0])
        self.assertNotIn("네트워크 대기", seen[-1])

    def test_saves_during_long_wait_so_progress_stays_fresh(self):
        with mock.patch.object(review, "WAIT_TICK", 0.02):
            self.waiter()("끊김", 1, 0.1)
        self.assertGreater(len(self.saves), 3)

    def test_without_ticket_counts_only_run(self):
        self.waiter("")("끊김", 1, 0.01)
        self.assertEqual(self.st.tickets, {})
        self.assertEqual(self.st.network["errors"], 1)
        self.assertTrue(self.lines[0].startswith("끊김."))

    def test_two_threads_stays_while_other_waits(self):
        w = self.waiter()
        threads = [threading.Thread(target=w, args=("끊김", 1, s)) for s in (0.05, 1.0)]
        for t in threads:
            t.start()
        time.sleep(0.4)  # 짧은 쪽이 끝났고 긴 쪽은 기다린다
        self.assertTrue(self.st.network["wait"])
        for t in threads:
            t.join()
        self.assertEqual(self.st.network["wait"], {})
        self.assertEqual(self.st.network["errors"], 2)

    def test_two_threads_count_wall_clock_once(self):
        w = self.waiter()
        threads = [threading.Thread(target=w, args=("끊김", 1, 0.5)) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertLess(self.st.network["waited_seconds"], 0.95)  # 합(1.0)이 아니라 벽시계다

    def test_restores_worker_outage_label(self):
        outage = {"count": 3, "due_at": "2099-01-01T00:00:00+09:00"}
        self.st.network["wait"] = dict(outage)
        self.waiter()("끊김", 1, 0.01)
        self.assertEqual(self.st.network["wait"], outage)

    def test_agy_retry_counts_as_call(self):
        w = self.waiter()
        w("끊김", 1, 0.01, "agy")
        w("끊김", 1, 0.01, "codex")
        self.assertEqual(self.st.agy_calls, 1)


class GoFlowTest(support.GoTest):
    """gs go 전체: 가짜 worker, GS_REVIEWER_CMD 리뷰어(티켓 reviewer = codex)."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"GS_NETWORK_MINUTE": "0.01"})
        patch.start()
        self.addCleanup(patch.stop)

    def limit(self, minutes):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("network_wait_minutes = 60", f"network_wait_minutes = {minutes}"))

    def reviewer(self, body):
        (self.bin / "reviewer.sh").write_text('here="$(dirname "$0")"\ncat > /dev/null\necho "$GS_REVIEWER" >> "$here/review.calls"\n'
                                              + textwrap.dedent(body))

    def ticket_state(self):
        return state.load(self.rundir, "demo").tickets["01"]

    def test_reviewer_down_aborts_without_merge_then_resumes_from_review(self):
        self.limit(1)
        self.reviewer(f'''\
            if [ ! -f "$here/up" ]; then echo '{CODEX_DOWN}'; exit 1; fi
            echo '{NO_FINDINGS}'
        ''')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertIn("■ 중단(네트워크): 다음 gs go가 이어 간다", out)
        self.assertIn("대기 합계가 상한 1분을 넘었다", out)
        self.assertNotIn("리뷰 실패", out)
        self.assertNotIn("gs-ticket: demo/01", self.integration("log", "--format=%B", "gs/demo/integration"))
        self.assertEqual(self.lines("review.calls"), ["codex", "codex"])
        ts = self.ticket_state()
        self.assertEqual((ts.status, ts.failures, ts.review), ("pending", 0, {}))
        self.assertTrue(ts.network_resume["done"])
        self.assertEqual(ts.transient_errors, 1)
        st = state.load(self.rundir, "demo")
        self.assertTrue(st.network["aborted"])
        self.assertEqual(st.network["wait"], {})
        self.assertEqual(st.finish, {})

        (self.bin / "up").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # worker를 다시 띄우지 않는다
        self.assertEqual(self.lines("review.calls"), ["codex", "codex", "codex"])
        ts = self.ticket_state()
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 1, 0))
        self.assertEqual(ts.review["note"], "")

    def test_reviewer_recovers_within_limit_and_progress_shows_wait(self):
        self.reviewer(f'''\
            n=$(wc -l < "$here/review.calls" | tr -d ' ')
            if [ "$n" -lt 3 ]; then echo '{CODEX_DOWN}'; exit 1; fi
            echo '{NO_FINDINGS}'
        ''')
        os.environ["GS_NETWORK_MINUTE"] = "0.1"  # 기다린 시간은 0.1초 단위로 적는다
        lines = []
        real = go.Run.save

        def save(run):
            real(run)
            lines.append(run.st.progress["line"])

        with mock.patch.object(go.Run, "save", save):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        waiting = [line for line in lines if "네트워크 대기" in line]
        self.assertTrue(any("네트워크 대기(1회" in line for line in waiting), lines)
        self.assertTrue(any("네트워크 대기(2회" in line for line in waiting), lines)
        self.assertTrue(all("01 리뷰 중(codex)" in line for line in waiting), waiting)
        self.assertNotIn("네트워크 대기", lines[-1])
        self.assertIn("[01] `bash` 일시 오류", out)
        ts = self.ticket_state()
        self.assertEqual((ts.status, ts.failures, ts.transient_errors), ("merged", 0, 2))
        self.assertEqual(ts.review["note"], "")
        self.assertGreater(ts.network_wait_seconds, 0)
        self.assertEqual(state.load(self.rundir, "demo").network["errors"], 2)

    def test_other_reviewer_failure_still_merges_as_review_failure(self):
        self.reviewer("echo 'tests failed' >&2; exit 1\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("review.calls"), ["codex"])
        ts = self.ticket_state()
        self.assertEqual(ts.status, "merged")
        self.assertIn("리뷰 실패(리뷰 없음, verify만으로 병합한다)", ts.review["note"])
        self.assertIn("리뷰 실패", self.final_report())

    def test_judge_down_during_classify_aborts_and_report_is_not_blocked_by_summary(self):
        self.limit(1)
        self.reviewer(f"echo '{ONE_FINDING}'\n")
        real = self.bin / "judge"
        good = real.read_text()
        real.write_text(f"#!/bin/bash\ncat > /dev/null\necho '{CLAUDE_DOWN}'\nexit 1\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("판단 모델 호출 불가", out)
        self.assertNotIn("gs-ticket: demo/01", self.integration("log", "--format=%B", "gs/demo/integration"))
        # 판단 모델이 돌아오면 리뷰부터 잇는다
        real.write_text(good)
        self.reviewer(f"echo '{NO_FINDINGS}'\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])

    def test_summary_judge_down_only_falls_back_and_finishes(self):
        """보고서 Summary는 넘겨도 중단하지 않는다: 실행은 마무리까지 간다."""
        self.limit(1)
        (self.bin / "judge").write_text(f"#!/bin/bash\ncat > /dev/null\necho '{CLAUDE_DOWN}'\nexit 1\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("■ 중단(네트워크)", out)
        self.assertIn("보고서 판단 모델 호출 실패", self.final_report())
        self.assertEqual(self.ticket_state().status, "merged")

    def test_failure_summary_judge_down_only_falls_back_and_retries_ticket(self):
        self.limit(1)
        (self.bin / "judge").write_text(f"#!/bin/bash\ncat > /dev/null\necho '{CLAUDE_DOWN}'\nexit 1\n")
        code, out, err = self.go("--only", "06")  # 06은 늘 실패하는 worker(support의 가짜)
        self.assertEqual(code, 1, out + err)
        self.assertNotIn("■ 중단(네트워크)", out)
        self.assertIn("실패 요약 호출 불가", (self.rundir / "06/2/brief.md").read_text())


if __name__ == "__main__":
    unittest.main()
