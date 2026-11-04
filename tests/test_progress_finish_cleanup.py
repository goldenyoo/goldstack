"""goldstack-v3 05: 진행 바 heartbeat, herdr 오류 경로의 요약·알림, 마무리 0분, 남긴 worktree 재확인·범위 밖 표시."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_go
import test_notify
from test_go import FAKE_WORKER, sh

from gs import git, herdr, report, state

START = datetime(2026, 11, 3, 9, tzinfo=timezone.utc)

# 01의 첫 시도만 커밋 안 된 파일을 남긴다(병합되지만 worktree는 남는다). 다른 티켓·재시도는 깨끗하다.
DIRTY_ONCE = FAKE_WORKER + '''
if [ "$GS_TICKET" = 01 ] && [ ! -f "$here/dirty_once" ]; then touch "$here/dirty_once"; echo unfinished > pending.txt; fi
'''


def clock(seconds):
    return (START + timedelta(seconds=seconds)).isoformat()


class GoCase(unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    G = test_go.GoTest
    setUp, tearDown, go = G.setUp, G.tearDown, G.go
    rundir, integration, final_report = G.rundir, G.integration, G.final_report


class HeartbeatTest(GoCase):
    def test_state_is_saved_while_worker_is_quiet(self):
        # worker가 출력·커밋 없이 2초 동안 있다. 상태 변화가 없어도 heartbeat 간격(시험은 0.2초)마다 쓴다.
        (self.bin / "worker.sh").write_text("sleep 2\n" + FAKE_WORKER)
        seen = []
        save = state.save

        def observe(rundir, st):
            save(rundir, st)
            path = state.path(rundir)
            seen.append((path.stat().st_mtime_ns, json.loads(path.read_text())))

        with mock.patch("gs.go.HEARTBEAT_SECONDS", 0.2), mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        quiet = [(m, s) for m, s in seen if [a["phase"] for a in s["progress"]["running"]] == ["worker"]]
        # 앞의 둘은 RUNNING·pane 기록이다. 그 뒤는 바뀐 것 없이 heartbeat만
        beats = quiet[2:]
        self.assertGreaterEqual(len(beats), 4, out)
        self.assertEqual(len({json.dumps(s["tickets"], sort_keys=True) for _, s in quiet[1:]}), 1)
        mtimes = [m for m, _ in quiet]
        self.assertEqual(mtimes, sorted(mtimes))
        self.assertGreater(mtimes[-1], mtimes[1])
        first, last = quiet[1][1], quiet[-1][1]
        self.assertGreater(last["progress"]["elapsed_s"], first["progress"]["elapsed_s"])
        self.assertGreater(last["updated_at"], first["updated_at"])

    def test_default_interval_is_sixty_seconds(self):
        from gs import go
        self.assertEqual(go.HEARTBEAT_SECONDS, 60)


class HerdrErrorTest(test_notify.FakeServerMixin, unittest.TestCase):
    BASE, REMOTE = "main", "origin"
    N = test_notify.GoNotifyTest
    tearDown, go, rundir, integration, enable = N.tearDown, N.go, N.rundir, N.integration, N.enable
    setUp = N.setUp

    def test_herdr_error_still_prints_summary_and_notifies(self):
        fake = self.serve()
        self.enable()
        with mock.patch("gs.worker.make_runner", side_effect=herdr.HerdrError("no_session", "herdr 세션 없음")):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertIn("gs go: herdr 오류: no_session: herdr 세션 없음", err)
        self.assertIn("■ 요약: 대기 1", out)
        self.assertTrue(out.strip().splitlines()[-1].startswith("■ PR:"), out)
        self.assertEqual(fake.texts(), ["❌ demo · 미완료 · 티켓 0/1 · 보고서 .goldstack/work/demo/report.md"])
        self.assertTrue(state.load(self.rundir, "demo").finished_at)


class FinishZeroMinutesTest(unittest.TestCase):
    def evidence(self, phases):
        st = state.State(feature="f", started_at=clock(0))
        ts = st.ticket("01")
        ts.status = state.MERGED
        for phase, start in phases:
            state.begin_phase(ts, phase, "claude", attempt=1, at=clock(start))
        state.end_phase(ts, clock(phases[-1][1] + 10))  # 마무리는 병합 커밋 10초
        r = SimpleNamespace(st=st, order=["01"], rundir=Path("/nonexistent-gs-run"),
                            feat=SimpleNamespace(tickets={"01": SimpleNamespace(title="t")},
                                                 spec=SimpleNamespace(verify="true")))
        return report.evidence(r)

    def test_zero_minute_phases_are_left_out(self):
        text = self.evidence([("worker", 0), ("review", 540), ("verify", 780), ("finish", 960)])
        self.assertIn("- 01 단계별 소요: worker 9분 · 리뷰 4분 · 검증 3분\n", text)
        self.assertNotIn("마무리", text.split("### 리뷰 지적")[0])

    def test_all_zero_minutes(self):
        text = self.evidence([("worker", 0), ("verify", 5), ("finish", 10)])
        self.assertIn("- 01 단계별 소요: 모두 1분 미만\n", text)
        self.assertNotIn("0분", text)


class KeptWorktreesTest(GoCase):
    def kept(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid].kept_worktrees

    def test_committed_old_kept_worktree_is_cleaned_when_ticket_goes_back_to_pending(self):
        init = sh(self.repo, "git", "rev-parse", "HEAD")
        (self.bin / "worker.sh").write_text(DIRTY_ONCE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = self.rundir / "wt/01"
        self.assertEqual(self.kept(), [str(wt)])
        # 사람이 남은 변경을 커밋했다. 그 사이 integration·base의 병합이 사라졌다(되돌린 PR 등): 01은 다시 대기로
        sh(wt, "git", "add", "-A")
        sh(wt, "git", "commit", "-qm", "사람이 마무리")
        user_commit = sh(wt, "git", "rev-parse", "HEAD")
        sh(self.remote, "git", "update-ref", "refs/heads/main", init)
        sh(self.remote, "git", "update-ref", "refs/heads/gs/demo/integration", init)
        git.ensure_worktree(self.repo, self.rundir / "wt/integration", "gs/demo/integration", init)
        sh(self.rundir / "wt/integration", "git", "reset", "-q", "--hard", init)
        code, out, err = self.go("--only", "01")
        self.assertIn("[01] state는 병합이라는데 integration에 표시가 없다", out)
        self.assertIn(f"[01] 남긴 worktree 정리: {wt}", out)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.kept(), [])
        self.assertFalse(wt.exists())
        self.assertNotIn("남긴 worktree", self.final_report())
        # 사람의 커밋은 integration에 없으니 브랜치는 남긴다
        self.assertEqual(sh(self.repo, "git", "rev-parse", "gs/demo/01"), user_commit)
        self.assertIn("브랜치 끝이 integration에 포함되지 않아 남긴다: gs/demo/01", out)

    def test_detached_head_kept_worktree_is_not_removed(self):
        init = sh(self.repo, "git", "rev-parse", "HEAD")
        (self.bin / "worker.sh").write_text(DIRTY_ONCE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = self.rundir / "wt/01"
        # 사람이 분리 HEAD에서 커밋했다: 그 커밋을 가리키는 것은 이 worktree의 HEAD뿐이다
        sh(wt, "git", "checkout", "-q", "--detach")
        sh(wt, "git", "add", "-A")
        sh(wt, "git", "commit", "-qm", "분리 HEAD에서 마무리")
        user_commit = sh(wt, "git", "rev-parse", "HEAD")
        sh(self.remote, "git", "update-ref", "refs/heads/main", init)
        sh(self.remote, "git", "update-ref", "refs/heads/gs/demo/integration", init)
        git.ensure_worktree(self.repo, self.rundir / "wt/integration", "gs/demo/integration", init)
        sh(self.rundir / "wt/integration", "git", "reset", "-q", "--hard", init)
        code, out, err = self.go("--only", "01")
        self.assertIn(f"[01] 경고: 남긴 worktree의 브랜치가 gs/demo/01가 아니라 정리하지 않는다: {wt}", out)
        self.assertNotIn(f"[01] 남긴 worktree 정리: {wt}", out)
        self.assertTrue(wt.exists())
        self.assertEqual(sh(wt, "git", "rev-parse", "HEAD"), user_commit)
        self.assertIn(str(wt), self.kept())

    def test_missing_or_still_dirty_old_paths(self):
        (self.bin / "worker.sh").write_text(DIRTY_ONCE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = str(self.rundir / "wt/01")
        gone = str(self.rundir / "wt/01-retry-7")
        st = state.load(self.rundir, "demo")
        ts = st.ticket("01")
        ts.kept_worktrees = [gone, wt]
        ts.worktree = str(self.rundir / "wt/01-retry-8")  # 지금 시도는 다른 경로: 둘 다 옛 경로
        state.save(self.rundir, st)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"[01] 남긴 worktree가 없어 목록에서 뺀다: {gone}", out)
        self.assertEqual(self.kept(), [wt])  # 아직 미커밋 변경이 있어 남긴다
        self.assertIn(f"남긴 worktree: {wt} (미커밋 변경)", self.final_report())

    def test_kept_worktree_outside_only_is_in_report(self):
        (self.bin / "worker.sh").write_text(DIRTY_ONCE)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = self.rundir / "wt/01"
        code, out, err = self.go("--only", "04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.kept(), [str(wt)])
        text = self.final_report()
        self.assertIn(f"범위 밖 티켓의 남긴 worktree:\n\n- 01: 남긴 worktree: {wt} (미커밋 변경)\n", text)
        # 이번 범위의 merged 티켓 줄에는 0분 단계가 없다
        self.assertIn("- 04 단계별 소요: ", text)
        self.assertNotIn("0분", text.split("### 리뷰 지적")[0])


if __name__ == "__main__":
    unittest.main()
