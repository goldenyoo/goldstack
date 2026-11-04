"""gs 결함 수집: 내부 예외, 마무리 이상, 어댑터 실패 패턴. 대상 프로젝트의 실패는 올리지 않는다.

worker 환경(`GS_ROLE=worker`)에서는 수집이 꺼지므로 시험마다 그 표시를 뺀다. gs의 검증도 표시를 빼고 돈다.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
import test_adapters
import test_config
import test_feedback_send
from support import isolate_git_env, sh
from gs import adapters, cli, config, feedback, git, herdr, review, state, transient

FEATURE = "feat-one"
LOCK_REF = "fatal: cannot lock ref 'HEAD': unable to create directory for /home/someone/proj/.git/refs/heads/gs/feat/02"
STREAM_ERROR = json.dumps({"type": "error", "message": "stream disconnected before completion"})


class CollectTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        fake = self.repo / "gh"
        fake.write_text(f"#!{sys.executable}\n" + test_feedback_send.FAKE_GH)
        fake.chmod(0o755)
        env = mock.patch.dict(os.environ, {"GS_GH": str(fake), "FAKE_GH_ROOT": str(self.repo)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GS_ROLE", None)
        probe = mock.patch("gs.feedback.environment", return_value=test_feedback_send.ENV)
        probe.start()
        self.addCleanup(probe.stop)
        warn = mock.patch("gs.version.warn")  # 진짜 `claude plugin list`를 부르지 않는다
        warn.start()
        self.addCleanup(warn.stop)
        self.rundir = self.repo / ".goldstack" / "work" / FEATURE / "run"
        self.configure("draft")

    def configure(self, mode, detail="errors"):
        (self.repo / ".goldstack").mkdir(exist_ok=True)
        (self.repo / config.CONFIG_PATH).write_text(
            test_config.CONFIG + f'\n[feedback]\nmode = "{mode}"\ndetail = "{detail}"\nrepo = "owner/inbox"\n')
        self.cfg, _ = config.load(self.repo)

    def run_gs(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), *args])
        return code, out.getvalue(), err.getvalue()

    def go(self, effect=None, code=0, *names):
        """가짜 go()로 `gs go`를 돌린다. effect는 go() 안에서 하는 일(state, 실패 기록 쓰기)이다."""
        def fake(repo, name, only=None):
            if effect:
                effect()
            return code
        with mock.patch("gs.go.go", side_effect=fake), mock.patch("gs.cli.cmd_check", return_value=0):
            return self.run_gs("go", *(names or (FEATURE,)))

    def drafts(self):
        return [feedback.read_draft(p, self.cfg) for p in sorted((self.repo / feedback.FEEDBACK_DIR).glob("*.md"))]

    def kinds(self):
        return sorted(d.title.split(": ")[1].split(" ")[0] for d in self.drafts())

    def clear_drafts(self):
        for path in (self.repo / feedback.FEEDBACK_DIR).glob("*.md"):
            path.unlink()

    def calls(self):
        path = self.repo / "calls"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def write_state(self, finish, *, finish_ran=True, network=None):
        """state.json을 쓴다. finish_ran이면 `finish.run`이 한 번 더 돈 것처럼 측정을 남긴다."""
        st = state.load(self.rundir, FEATURE)
        st.finish, st.network = finish, network or {}
        if finish_ran:
            st.metrics.setdefault("finish_stages", []).append({"label": "total", "started_at": "", "seconds": 1})
        state.save(self.rundir, st)

    def failure(self, reason, worker="", tid="01", attempt="1"):
        """`_fail`이 남기는 것과 같은 모양의 시도 디렉터리."""
        directory = self.rundir / tid / attempt
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "worker.log").write_text(worker, encoding="utf-8")
        (directory / "failure.log").write_text(
            f"실패 이유: {reason}\n\n## {directory}/worker.log (마지막 65536 bytes)\n{worker}\n", encoding="utf-8")


class InternalExceptionTest(CollectTest):
    def crash(self, exc, mode=None):
        if mode:
            self.configure(mode)
        with mock.patch("gs.go.go", side_effect=exc), self.assertRaises(type(exc)):
            self.run_gs("go", FEATURE)

    def test_draft_with_gs_frames_only_and_the_original_error_is_raised(self):
        self.crash(KeyError("billing_secret"))
        draft, = self.drafts()
        self.assertEqual(draft.title, f"[field] go: KeyError (gs {test_feedback_send.ENV.gs_version})")
        frames = [line for line in draft.body.splitlines() if line.startswith("- gs/")]
        self.assertTrue(frames)
        self.assertTrue(all(line.startswith("- gs/cli.py:") for line in frames), frames)
        self.assertNotIn("test_feedback_collect", draft.body)
        self.assertNotIn("mock", draft.body)
        self.assertNotIn("billing_secret", draft.body)
        self.assertNotIn(str(self.repo), draft.body)

    def test_unknown_exception_type_is_not_named_and_mode_off_keeps_nothing(self):
        class BillingEngineError(Exception):
            pass
        self.crash(BillingEngineError("x"))
        self.assertIn("unknown", self.drafts()[0].title)
        self.clear_drafts()
        self.crash(KeyError("x"), mode="off")
        self.assertEqual(self.drafts(), [])

    def test_same_exception_counts_once_per_crash(self):
        self.crash(ValueError("x"))
        self.crash(ValueError("x"))
        draft, = self.drafts()
        self.assertEqual(draft.count, 2)

    def test_exception_of_go_is_sent_and_counted_in_the_same_summary(self):
        self.configure("auto")
        out = io.StringIO()
        with mock.patch("gs.go.go", side_effect=KeyError("boom")), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(KeyError):
            cli.main(["--repo", str(self.repo), "go", FEATURE])
        self.assertIn("■ goldstack 피드백: 보냄 1 · 대기 0\n", out.getvalue())
        draft, = self.drafts()
        self.assertEqual(draft.count, 1)  # main이 다시 수집하지 않는다
        self.assertIn(["issue", "create"], [call[:2] for call in self.calls()])

    def test_exception_of_cmd_go_before_go_is_collected_once(self):
        with mock.patch("gs.version.warn", side_effect=ValueError("boom")), self.assertRaises(ValueError):
            self.run_gs("go", FEATURE)
        draft, = self.drafts()
        self.assertEqual(draft.count, 1)

    def test_every_command_is_covered_and_the_phase_is_its_name(self):
        for args, target in ((["config", "git.base"], "gs.cli.cmd_config"),
                             (["self-update"], "gs.selfupdate.self_update"),
                             (["feedback", "list"], "gs.feedback.command"),
                             (["hook", "pretooluse"], "gs.hook.main")):
            with self.subTest(args=args), mock.patch(target, side_effect=ValueError("boom")), \
                    self.assertRaises(ValueError):
                self.run_gs(*args)
            draft, = self.drafts()
            self.assertEqual(draft.labels[2], args[0])
            self.clear_drafts()

    def test_command_outside_a_repo_raises_the_original_error_only(self):
        with mock.patch("gs.selfupdate.self_update", side_effect=KeyError("boom")), \
                mock.patch("gs.feature.find_repo_root", return_value=None), \
                mock.patch("gs.feedback.collect_exception") as collect, self.assertRaises(KeyError):
            cli.main(["self-update"])
        collect.assert_not_called()

    def test_exit_and_interrupt_are_not_gs_defects(self):
        for exc in (KeyboardInterrupt(), SystemExit(3)):
            with self.subTest(exc=exc), mock.patch("gs.go.go", side_effect=exc), self.assertRaises(type(exc)):
                self.run_gs("go", FEATURE)
        self.assertEqual(self.drafts(), [])

    def test_interrupt_does_not_send(self):
        self.configure("auto")
        feedback.record(self.repo, self.cfg, phase="verify", kind="GitError", frames=[], error_lines=["x"])
        with mock.patch("gs.go.go", side_effect=KeyboardInterrupt), \
                mock.patch("gs.feedback.send", return_value=0) as send, self.assertRaises(KeyboardInterrupt):
            self.run_gs("go", FEATURE)
        self.assertEqual(send.call_count, 1)  # 시작 때 한 번뿐이다

    def test_worker_role_collects_nothing(self):
        with mock.patch.dict(os.environ, {"GS_ROLE": "worker"}):
            self.crash(KeyError("x"))
        self.assertEqual(self.drafts(), [])

    def test_transient_or_environment_error_reaching_main_is_not_a_gs_defect(self):
        # 메시지가 외부 명령·OS의 출력인 예외 종류마다 하나씩
        for exc in (git.GitError("git fetch: fatal: unable to access: Connection refused"),
                    git.GitError("git fetch: fatal: Could not resolve host: github.com"),
                    herdr.HerdrError("unknown", "gh pr view: HTTP 503 service unavailable"),
                    adapters.AdapterError("`claude plugin list --json` 종료 1: gh: authentication failed"),
                    review.ReviewTransient("`codex` 일시 오류: connection refused(로그 x)"),
                    transient.NetworkAbort("대기 합계가 상한 60분을 넘었다"),
                    PermissionError(13, "Permission denied"), BrokenPipeError()):
            with self.subTest(exc=exc):
                self.crash(exc)
                self.assertEqual(self.drafts(), [])

    def test_a_gs_defect_stays_one_even_if_its_message_has_environment_words(self):
        # 환경 낱말은 외부 출력을 담는 예외에서만 뜻이 있다. 나머지는 메시지와 상관없이 gs 코드의 결함이다
        for exc in (KeyError("authentication"), TypeError("HTTP 403"), ValueError("not logged in"),
                    RuntimeError("gh: authentication failed"), AttributeError("Connection refused")):
            with self.subTest(exc=exc):
                before = sum(draft.count for draft in self.drafts())
                self.crash(exc)
                self.assertEqual(sum(draft.count for draft in self.drafts()), before + 1)

    def test_an_external_error_that_is_not_about_the_environment_is_still_collected(self):
        self.crash(git.GitError("git rev-parse: fatal: bad revision"))
        self.assertEqual(self.kinds(), ["GitError"])

    def test_failing_collector_does_not_replace_the_error(self):
        with mock.patch("gs.feedback.collect_exception", side_effect=RuntimeError("collector bug")), \
                mock.patch("gs.go.go", side_effect=KeyError("original")), self.assertRaises(KeyError):
            self.run_gs("go", FEATURE)

    def test_a_feedback_module_that_cannot_load_changes_nothing(self):
        # 재설치 직후 등. 수집 쪽 import 실패도 종료 코드와 원래 예외를 바꾸지 않는다
        with mock.patch.dict(sys.modules, {"gs.feedback": None}):
            with mock.patch("gs.go.go", return_value=7):
                self.assertEqual(self.run_gs("go", FEATURE)[0], 7)
            with mock.patch("gs.go.go", side_effect=KeyError("original")), self.assertRaises(KeyError):
                self.run_gs("go", FEATURE)
            with mock.patch("gs.selfupdate.self_update", side_effect=KeyError("original")), self.assertRaises(KeyError):
                self.run_gs("self-update")


class VersionProbeTest(CollectTest):
    def test_probe_runs_outside_the_directory_gs_was_started_in(self):
        fake = self.repo / "fake-agy"
        fake.write_text("#!/bin/sh\necho stray > stray\necho 1.2.3\n")
        fake.chmod(0o755)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)
        with mock.patch.dict(os.environ, GS_AGY="./fake-agy"):  # 상대 경로도 시작한 디렉터리 기준으로 찾는다
            self.assertEqual(feedback._cli_version("agy"), "1.2.3")
        self.assertFalse((self.repo / "stray").exists())


class FinishAnomalyTest(CollectTest):
    def run_finish(self, before, after, **kw):
        state.path(self.rundir).unlink(missing_ok=True)
        if before is not None:
            self.write_state(before)
        return self.go(lambda: self.write_state(after, **kw))

    def test_stuck_in_a_resume_phase(self):
        for phase in ("merge_requested", "merged", "main_failed"):
            with self.subTest(phase=phase):
                self.clear_drafts()
                self.run_finish({"phase": phase}, {"phase": phase})
                draft, = self.drafts()
                self.assertEqual(draft.title.split()[:3], ["[field]", "finish:", "stuck-phase"])
                self.assertEqual(draft.labels[2], "finish")
                self.assertIn("stuck in resume phase: ", draft.body)

    def test_phases_that_wait_on_people_or_ci_or_that_moved_are_not_stuck(self):
        for phase in ("checks_pending", "checks_failed", "checks_timeout", "merge_pending", "revert_pending",
                      "report_pending", "base_unverified"):
            self.run_finish({"phase": phase}, {"phase": phase})
        self.run_finish({"phase": "merged"}, {"phase": "verified"})
        self.run_finish({"phase": "merge_requested"}, {"phase": "merged"})
        self.run_finish(None, {"phase": "merged"})
        self.assertEqual(self.drafts(), [])

    def test_resume_that_did_not_reach_finish_is_not_stuck(self):
        # 검사 오류·잠금 실패·준비 실패: go()가 돌았어도 `finish.run`은 돌지 않았다
        self.run_finish({"phase": "merged"}, {"phase": "merged"}, finish_ran=False)
        self.assertEqual(self.drafts(), [])

    def test_network_abort_is_not_an_anomaly(self):
        self.run_finish({"phase": "merged"}, {"phase": "merged"}, network={"aborted": "상한"})
        self.assertEqual(self.drafts(), [])

    def test_unexpected_revert_but_not_the_designed_one(self):
        self.run_finish({"phase": "merged"}, {"phase": "reverted", "integration_ok": True, "main_ok": False})
        self.assertEqual(self.drafts(), [])  # base 검증 실패 → revert는 설계된 동작이자 시험 실패다
        self.run_finish({"phase": "merged"}, {"phase": "reverted", "integration_ok": True, "main_ok": None})
        self.assertEqual(self.kinds(), ["unexpected-revert"])
        self.assertIn("unexpected revert: ", self.drafts()[0].body)
        self.clear_drafts()
        self.run_finish({"phase": "merged"}, {"phase": "reverted", "integration_ok": False, "main_ok": False})
        self.assertEqual(self.kinds(), ["unexpected-revert"])  # 통과하지 못한 integration이 병합됐다
        self.clear_drafts()
        self.run_finish({"phase": "reverted"}, {"phase": "reverted", "main_ok": None})  # 지난 실행의 revert
        self.assertEqual(self.drafts(), [])

    def test_finish_error_is_new_and_is_one_draft(self):
        failed = {"phase": "merged", "outcome": "마무리 실패: fatal: bad object", "error": "fatal: bad object\nsecond"}
        self.run_finish({"phase": "merged"}, failed)
        draft, = self.drafts()  # 같은 원인을 갇힘으로 또 올리지 않는다
        self.assertEqual(draft.title.split()[:3], ["[field]", "finish:", "finish-error"])
        self.clear_drafts()
        self.run_finish({"phase": "merged", "error": failed["error"]}, failed)
        self.assertEqual(self.kinds(), ["stuck-phase"])  # 같은 오류가 남은 채 다시 멈췄다

    def test_environment_and_transient_errors_are_neither_finish_error_nor_stuck(self):
        for error in ("gh pr merge: HTTP 403 forbidden", "gh: authentication failed", "protected branch update failed",
                      "gh pr view: HTTP 503 service unavailable", "error sending request",
                      "git fetch: fatal: Could not resolve host: github.com"):
            with self.subTest(error=error):
                self.run_finish({"phase": "merged"}, {"phase": "merged", "outcome": f"마무리 실패: {error}", "error": error})
                self.assertEqual(self.drafts(), [])

    def test_refused_merge_and_changed_push_settings_are_not_defects(self):
        self.run_finish({"phase": "merge_requested"},
                        {"phase": "merge_pending", "outcome": "사람 승인 필요: url", "error": "denied"})
        error = "push 설정이 실행 시작 때와 달라 push하지 않았다(원격 `origin`). worker나 검증 명령이 바꿨을 수 있다."
        self.run_finish({"phase": "merged"}, {"phase": "merged", "outcome": error, "error": error})
        self.assertEqual(self.drafts(), [])

    def test_exception_in_go_skips_finish_check_but_keeps_adapter_failures(self):
        self.write_state({"phase": "merged"})

        def fake(repo, name, only=None):
            self.write_state({"phase": "merged"})
            self.failure("worker 실행기가 사라졌다")
            raise RuntimeError("go broke")
        with mock.patch("gs.go.go", side_effect=fake), self.assertRaises(RuntimeError):
            self.run_gs("go", FEATURE)
        self.assertEqual(self.kinds(), ["RuntimeError", "worker-runner-lost"])


class AdapterFailureTest(CollectTest):
    def collect(self, reason, worker="", **kw):
        self.clear_drafts()
        self.go(lambda: self.failure(reason, worker, **kw))
        return self.kinds()

    def test_pattern_table_starts_with_the_three_names(self):
        self.assertEqual([p.name for p in feedback.ADAPTER_PATTERNS],
                         ["codex-cannot-lock-ref", "agy-no-result", "worker-runner-lost"])
        for pattern in feedback.ADAPTER_PATTERNS:
            self.assertEqual(feedback._clean_kind(pattern.name), pattern.name)

    def test_named_patterns(self):
        for reason, worker, kind in (
                ("커밋 없음", LOCK_REF, "codex-cannot-lock-ref"),
                ("worker 종료 코드 1", LOCK_REF, "codex-cannot-lock-ref"),
                ("worker 종료 코드 1 (agy: result 이벤트가 없다)", "", "agy-no-result"),
                ("worker 실행기가 사라졌다", "", "worker-runner-lost")):
            with self.subTest(kind=kind):
                self.assertEqual(self.collect(reason, worker), [kind])
        draft, = self.drafts()
        self.assertEqual(draft.labels[2], "worker")

    def test_lock_ref_draft_keeps_the_diagnosis_but_no_path(self):
        self.collect("커밋 없음", "앞 줄 token=ghp_SUPERSECRET\n" + LOCK_REF + "\n뒷 줄")
        draft, = self.drafts()
        self.assertIn("cannot lock ref", draft.body)
        for name in ("someone", "proj", "SUPERSECRET", "앞 줄"):
            self.assertNotIn(name, draft.body)

    def test_unknown_adapter_error_follows_detail_and_counts(self):
        reason = "agy: result status ERROR_BILLING_ENGINE"
        self.assertEqual(self.collect(reason), ["unknown"])
        self.assertIn("```text", self.drafts()[0].body)
        self.go(lambda: self.failure(reason, tid="02"))
        draft, = self.drafts()
        self.assertEqual(draft.count, 2)
        self.configure("draft", detail="minimal")
        self.assertEqual(self.collect("codex: worktree의 git 디렉터리를 찾지 못했다: x"), ["unknown"])
        self.assertNotIn("```text", self.drafts()[0].body)
        self.assertNotIn(feedback.ERRORS_HEADING, self.drafts()[0].body)

    def test_other_unknown_shapes(self):
        for reason in ("worker 종료 코드 1 (agy: 마지막 result 이벤트의 result가 객체가 아니다)",
                       "model `zzz` 어댑터가 없다(claude|codex|agy)",
                       "worker를 띄우지 못했다: OSError: boom", "worker를 다시 띄우지 못했다: OSError: boom"):
            with self.subTest(reason=reason):
                self.assertEqual(self.collect(reason), ["unknown"])

    def test_target_project_failures_are_not_reported(self):
        for reason, worker in (
                ("커밋 없음", "nothing special"),  # 패턴에 안 걸린 커밋 없음
                ("커밋 없음", "error: cannot lock ref 'refs/heads/other': is at abc but expected def"),
                ("worker 종료 코드 1", "pytest: 3 failed"),
                ("검증 실패(로그 /x/verify.log)", ""),
                ("검증 시간 초과(30분, 로그 /x/verify.log)", ""),
                ("검증 중 worktree가 바뀌었다(로그 /x/verify.log)", ""),
                ("integration 병합 충돌", ""),
                ("준비 실패", ""),
                ("worker가 integration worktree를 바꿨다(되돌림)", ""),
                ("agy 한도: 이번 실행의 agy 호출이 상한 3에 닿아 worker를 띄우지 않았다", ""),
                ("agy 차단 장치가 없다: x. agy는 구현 worker로 띄우지 않는다(리뷰 전용)", ""),  # 띄우기 전의 의도된 거부
                ("리뷰 지적 2개가 남았다", "agy: result 이벤트가 없다"),
                ("worker 종료 코드 1 (agy: authentication failed)", ""),  # 대상 환경
                ("agy: usage limit reached", "")):
            with self.subTest(reason=reason):
                self.assertEqual(self.collect(reason, worker), [])

    def test_transient_errors_are_not_reported(self):
        for reason in ("worker 종료 코드 1 (agy: result 이벤트가 없다)", "worker 실행기가 사라졌다", "커밋 없음"):
            with self.subTest(reason=reason):
                self.assertEqual(self.collect(reason, LOCK_REF + "\n" + STREAM_ERROR + "\n"), [])

    def test_environment_errors_the_cli_reports_in_the_log_are_not_reported(self):
        no_result = "worker 종료 코드 1 (agy: result 이벤트가 없다)"
        step = json.dumps({"event": "step_update", "step_update": {"state": "RUNNING"}})
        for reason, worker in (
                (no_result, "error: authentication failed\n"),  # 시작 실패: 이벤트 없이 stderr만
                (no_result, "error: usage limit reached\n"),
                (no_result, "usage limit reached\n"),
                (no_result, "permission_denied\n"),
                (no_result, "error: not logged in\n"),
                (no_result, f"{step}\nerror: you have reached your limit\nwarning: x\n"),  # 도중에 죽음
                (no_result, f"{step}\n" + json.dumps({"event": "error", "message": "authentication failed"}) + "\n"),
                (no_result, json.dumps({"event": "error", "status": 401}) + "\n"),
                ("worker 종료 코드 1 (agy: result status ERROR)",
                 json.dumps({"event": "result", "result": {"status": "ERROR", "error": "quota exceeded"}}) + "\n"),
                ("worker 실행기가 사라졌다", "error: authentication failed\n"),
                ("커밋 없음", LOCK_REF + "\n" + json.dumps({"type": "turn.failed", "error": {"message": "401 Unauthorized"}})),
                ("커밋 없음", LOCK_REF + "\n" + json.dumps({"type": "error", "message": "x", "status": 403})),
                ("커밋 없음", LOCK_REF + "\n" + json.dumps({"type": "result", "is_error": True, "result": "Invalid API key"}))):
            with self.subTest(reason=reason, worker=worker):
                self.assertEqual(self.collect(reason, worker), [])

    def test_real_agy_outcome_for_an_environment_error_is_not_classified(self):
        log = self.repo / "agy.log"
        inp = adapters.WorkerInput(brief=self.repo / "brief.md", worktree=self.repo, log=log)
        for text in ("error: authentication failed\n", "error: usage limit reached\n", "permission_denied\n"):
            with self.subTest(text=text):
                log.write_text(text)
                code, note = adapters.Agy(self.cfg.models).outcome(1, inp)
                self.assertIn("agy: result 이벤트가 없다", note)
                self.assertIsNone(feedback.classify_adapter_failure(f"worker 종료 코드 {code} ({note})", text))

    def test_a_missing_model_in_the_agy_log_is_not_reported(self):
        fake = self.repo / "fake-agy"
        fake.write_text("#!/bin/sh\necho other-model\n")
        fake.chmod(0o755)
        with mock.patch.dict(os.environ, GS_AGY=str(fake)):
            self.assertEqual(self.collect("worker 종료 코드 1 (agy: result 이벤트가 없다)",
                                          "error: invalid model selection --model 'x'\n"), [])

    def test_environment_words_outside_cli_errors_do_not_hide_a_pattern(self):
        no_result = "worker 종료 코드 1 (agy: result 이벤트가 없다)"
        step = json.dumps({"event": "step_update", "step_update": {"output": "error: authentication failed 401"}})
        tool = json.dumps({"type": "item.completed", "item": {"aggregated_output": "permission denied: usage limit"}})
        answer = json.dumps({"type": "result", "is_error": False, "result": "authentication failed를 고쳤다"})
        recovered = json.dumps({"event": "error", "message": "authentication failed"})
        success = json.dumps({"event": "result", "result": {"status": "SUCCESS"}})
        for reason, worker, kind in (
                (no_result, step + "\n", "agy-no-result"),  # worker가 읽은 내용
                (no_result, "warning: permission denied for a tool\n", "agy-no-result"),
                (no_result, f"error: authentication failed\n{step}\n", "agy-no-result"),  # 다시 띄운 worker가 넘어섰다
                ("커밋 없음", f"{LOCK_REF}\n{tool}\n", "codex-cannot-lock-ref"),
                ("커밋 없음", f"{LOCK_REF}\n{answer}\n", "codex-cannot-lock-ref"),
                ("worker 실행기가 사라졌다", f"{recovered}\n{success}\n", "worker-runner-lost")):
            with self.subTest(reason=reason, worker=worker):
                self.assertEqual(self.collect(reason, worker), [kind])

    def test_only_logs_written_during_this_run_count(self):
        self.failure("worker 실행기가 사라졌다")
        self.go()
        self.assertEqual(self.drafts(), [])
        self.go(lambda: self.failure("worker 실행기가 사라졌다", tid="02"))
        self.assertEqual(self.kinds(), ["worker-runner-lost"])
        self.assertEqual(self.drafts()[0].count, 1)

    def test_a_log_rewritten_during_this_run_counts(self):
        self.failure("커밋 없음")
        log = self.rundir / "01/1/failure.log"
        os.utime(log, (1, 1))
        self.go(lambda: self.failure("worker 실행기가 사라졌다"))
        self.assertEqual(self.kinds(), ["worker-runner-lost"])

    def test_a_file_named_like_the_log_inside_a_worktree_is_not_read(self):
        def effect():
            path = self.rundir / "wt/01/failure.log"
            path.parent.mkdir(parents=True)
            path.write_text("실패 이유: worker 실행기가 사라졌다\n")
        self.go(effect)
        self.assertEqual(self.drafts(), [])

    def test_probing_agy_models_stays_out_of_the_current_directory(self):
        fake = self.repo / "fake-agy"
        fake.write_text("#!/bin/sh\necho stray > stray\necho other-model\n")
        fake.chmod(0o755)
        checkout = self.repo / "checkout"
        checkout.mkdir()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(checkout)
        with mock.patch.dict(os.environ, GS_AGY=str(fake)):
            feedback.classify_adapter_failure("커밋 없음", "error: invalid model selection --model 'x'\n")
        self.assertFalse((checkout / "stray").exists())
        self.assertFalse((self.repo / "stray").exists())


class SessionTest(CollectTest):
    def test_summary_line_counts_sent_and_pending(self):
        self.configure("auto")
        code, out, _ = self.go(lambda: self.failure("worker 실행기가 사라졌다"))
        self.assertEqual(code, 0)
        self.assertIn("■ goldstack 피드백: 보냄 1 · 대기 0\n", out)
        self.configure("draft")
        code, out, _ = self.go(lambda: self.failure("agy: x", tid="02"))
        self.assertIn("■ goldstack 피드백: 보냄 0 · 대기 1\n", out)

    def test_pending_when_send_fails_and_it_is_sent_on_the_next_go(self):
        self.configure("auto")
        with mock.patch.dict(os.environ, {"FAKE_FAIL": "create"}):
            code, out, err = self.go(lambda: self.failure("worker 실행기가 사라졌다"), 1)
        self.assertEqual(code, 1)
        self.assertIn("■ goldstack 피드백: 보냄 0 · 대기 1\n", out)
        self.assertIn("다음 실행 때 다시 보냅니다", err)
        code, out, _ = self.go()
        self.assertIn("■ goldstack 피드백: 보냄 1 · 대기 0\n", out)

    def test_no_line_when_off_or_nothing(self):
        self.assertNotIn("피드백", self.go()[1])
        self.configure("off")
        self.assertNotIn("피드백", self.go(lambda: self.failure("worker 실행기가 사라졌다"))[1])
        self.assertEqual(self.drafts(), [])
        self.assertEqual(self.calls(), [])

    def test_off_does_not_send_or_report_drafts_already_piled_up(self):
        feedback.record(self.repo, self.cfg, phase="verify", kind="GitError", frames=[], error_lines=["x"])
        self.configure("off")
        self.assertNotIn("피드백", self.go()[1])
        self.assertEqual(self.calls(), [])

    def test_start_resends_piled_up_drafts_before_go_runs(self):
        self.configure("auto")
        feedback.record(self.repo, self.cfg, phase="verify", kind="GitError", frames=[], error_lines=["fatal: x"])
        seen = []
        code, out, _ = self.go(lambda: seen.append([call[:2] for call in self.calls()]))
        self.assertIn(["issue", "create"], seen[0])  # go()가 돌기 전에 이미 나갔다
        self.assertIn("보냄 1 · 대기 0", out)

    def test_draft_mode_keeps_but_does_not_send(self):
        code, out, _ = self.go(lambda: self.failure("worker 실행기가 사라졌다"))
        self.assertEqual(len(self.drafts()), 1)
        self.assertIn("■ goldstack 피드백: 보냄 0 · 대기 1\n", out)
        self.assertEqual(self.calls(), [])

    def test_exit_code_and_output_do_not_change_when_feedback_fails(self):
        self.configure("auto")
        for name in ("start", "before", "after", "report"):
            for code in (0, 1, 7):
                with self.subTest(name=name, code=code), mock.patch.object(feedback.Session, name,
                                                                          side_effect=RuntimeError("bug")):
                    got = self.go(lambda: self.failure("worker 실행기가 사라졌다"), code)
                    self.assertEqual(got[0], code)
                    self.assertIn("피드백 처리를 건너뛰었다", got[2])
                    self.assertNotIn("Traceback", got[2])
        for target in ("adapter_failures", "finish_anomaly", "record", "send", "pending_count", "failure_logs"):
            for code in (0, 1, 7):
                with self.subTest(target=target, code=code), mock.patch(f"gs.feedback.{target}",
                                                                       side_effect=OSError("disk")):
                    self.write_state({"phase": "merged"})
                    got = self.go(lambda: (self.write_state({"phase": "merged"}),
                                           self.failure("worker 실행기가 사라졌다")), code)
                    self.assertEqual(got[0], code)
        with mock.patch("gs.feedback.Session", side_effect=RuntimeError("init")):
            self.assertEqual(self.go(None, 7)[0], 7)

    def test_a_broken_stderr_does_not_change_the_exit_code_either(self):
        class Broken(io.StringIO):
            def write(self, text):
                raise OSError("closed")
        with mock.patch("gs.go.go", return_value=7), mock.patch.object(feedback.Session, "report", side_effect=OSError("x")), \
                contextlib.redirect_stderr(Broken()):
            self.assertEqual(cli.cmd_go(self.repo, [FEATURE], None), 7)

    def test_unreadable_state_does_not_change_the_exit_code(self):
        self.rundir.mkdir(parents=True)
        state.path(self.rundir).write_text("{ broken", encoding="utf-8")
        self.assertEqual(self.go(None, 7)[0], 7)

    def test_several_features_collect_each_and_stop_rules_stay(self):
        other = self.repo / ".goldstack/work/other/run/01/1"
        other.mkdir(parents=True)

        def effect():
            self.failure("worker 실행기가 사라졌다")
            (other / "failure.log").write_text("실패 이유: agy: x\n", encoding="utf-8")
            for name in (FEATURE, "other"):
                run = self.repo / ".goldstack/work" / name / "run"
                state.save(run, state.State(feature=name, finish={"phase": "verified"}))
        code, out, _ = self.go(effect, 0, FEATURE, "other")
        self.assertEqual(code, 0)
        self.assertEqual(self.kinds(), ["unknown", "worker-runner-lost"])
        self.assertIn(f"■ {FEATURE}: verified → other 시작", out)
        with mock.patch("gs.go.go", return_value=1) as go, mock.patch("gs.cli.cmd_check", return_value=0):
            code, out, _ = self.run_gs("go", FEATURE, "other")
        self.assertEqual(code, 1)
        self.assertEqual(go.call_count, 1)
        self.assertIn("여기서 멈춤", out)


class RealFinishTest(support.GoTest):
    """진짜 `go()`와 `finish.run`으로 판정을 본다. `go.py`를 가짜로 두면 어떤 실행이 마무리에 닿는지 알 수 없다."""

    def setUp(self):
        super().setUp()
        os.environ.pop("GS_ROLE", None)  # self.env가 끝에 되돌린다
        warn = mock.patch("gs.version.warn")
        warn.start()
        self.addCleanup(warn.stop)
        probe = mock.patch("gs.feedback.environment", return_value=test_feedback_send.ENV)
        probe.start()
        self.addCleanup(probe.stop)

    def titles(self):
        cfg, _ = config.load(self.repo)
        return sorted(feedback.read_draft(p, cfg).title.split()[2]
                      for p in (self.repo / feedback.FEEDBACK_DIR).glob("*.md"))

    def set_finish(self, **fields):
        st = state.load(self.rundir, "demo")
        st.finish.update(fields)
        state.save(self.rundir, st)

    def pending_merge(self):
        """병합 대기(merge_pending)까지 간 실행 하나."""
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        return sh(self.repo, "git", "rev-parse", "gs/demo/integration")

    def test_passing_run_leaves_nothing(self):
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.titles(), [])
        self.assertNotIn("goldstack 피드백", out)

    def test_project_setup_failure_keeps_the_resume_phase_without_a_draft(self):
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('setup = ""', 'setup = "exit 8"'))
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.set_finish(phase="merged", merge_sha="0" * 40)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")
        self.assertEqual(self.titles(), [])

    def test_check_error_and_held_lock_are_not_stuck(self):
        self.pending_merge()
        self.set_finish(phase="merged", merge_sha="0" * 40)
        self.assertEqual(self.go("--only", "99")[0], 1)  # 검사 오류
        lock = state.Lock(self.rundir)
        lock.acquire()
        self.addCleanup(lock.release)
        self.assertEqual(self.go("--only", "01")[0], 1)  # 다른 gs go가 돌고 있다
        self.assertEqual(self.titles(), [])

    def test_finish_error_then_stuck_on_the_next_resume(self):
        head = self.pending_merge()
        self.set_finish(phase="merged", merge_sha=head)  # base에 없는 커밋: 재개하면 `_postmerge`가 오류를 낸다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.titles(), ["finish-error"])
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")
        self.assertEqual(self.titles(), ["finish-error", "stuck-phase"])
        self.assertIn("■ goldstack 피드백: 보냄 0 · 대기 2\n", out)

    def test_designed_revert_is_not_reported(self):
        spec = self.repo / ".goldstack/work/demo/spec.md"
        # 병합 커밋이 base 끝에 있을 때만 실패한다. integration 검증은 통과하고 base 검증만 실패한다.
        spec.write_text(spec.read_text().replace(
            "test ! -f BROKEN", 'test "$(git rev-parse --abbrev-ref HEAD)" != HEAD'))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "base 검증은 detached HEAD에서 실패한다")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        finish = state.load(self.rundir, "demo").finish
        self.assertEqual((finish["phase"], finish["integration_ok"], finish["main_ok"]), ("reverted", True, False))
        self.assertEqual(self.titles(), [])

    def test_failed_ticket_is_not_reported(self):
        (self.bin / "worker.sh").write_text('echo nothing\n')  # 커밋 없음
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.titles(), [])
        self.assertNotIn("goldstack 피드백", out)


class RealAdapterTest(test_adapters.AgyGoAndCheckTest):
    """진짜 `go()`를 gs의 검증과 같은 조건에서 돌린다: worker 표시가 없고, cwd는 다른 checkout이다.

    이 가짜 agy는 `--version`에도 cwd에 파일을 만들고 커밋한다. 버전 확인이 cwd에서 돌면 검증 중인 worktree가 바뀐다.
    물려받은 시험도 이 조건으로 한 번 더 돈다.
    """

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GS_ROLE", None)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        sh(self.checkout, "git", "init", "-q", "-b", "main")
        sh(self.checkout, "git", "commit", "-q", "--allow-empty", "-m", "base")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.checkout)

    def drafts(self):
        cfg, _ = config.load(self.repo)
        return [feedback.read_draft(p, cfg) for p in sorted((self.repo / feedback.FEEDBACK_DIR).glob("*.md"))]

    def assert_checkout_untouched(self):
        self.assertEqual(subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.checkout,
                                        capture_output=True, text=True, check=True).stdout, "")
        self.assertEqual(sh(self.checkout, "git", "rev-list", "--count", "HEAD"), "1")

    def test_guard_refusal_leaves_no_draft_and_never_calls_agy(self):
        self.fake_agy("nohook")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.drafts(), [])
        self.assertFalse((self.bin / "agy.args").exists())
        self.assertNotIn("goldstack 피드백", out)

    def test_unknown_adapter_error_is_collected_without_touching_the_checkout(self):
        self.fake_agy("error")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 1, out + err)
        draft, = self.drafts()
        self.assertEqual(draft.title.split()[:3], ["[field]", "worker:", "unknown"])
        self.assertIn("■ goldstack 피드백: 보냄 0 · 대기 1\n", out)
        self.assert_checkout_untouched()

    def test_passing_run_collects_nothing(self):
        self.fake_agy("ok")
        code, out, err = self.cli("go", "demo", "--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.drafts(), [])
        self.assertNotIn("goldstack 피드백", out)
        self.assert_checkout_untouched()


if __name__ == "__main__":
    unittest.main()
