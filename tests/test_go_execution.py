"""`gs go`의 실행·병렬 처리·격리·재개 시나리오."""
import json
import os
import re
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, herdr, state, worker
import support
from support import FAKE_HERDR, alive, git_clean, kill_quietly, sh, ticket


class GoExecutionTest(support.GoTest):
    # --- 병렬(04) ---
    def test_parallel_overlaps_and_respects_dependencies(self):
        for tid in ("11", "12", "13"):
            self.add_ticket(tid)
        vlog = self.bin / "verify.log"
        self.parallel(3, verify=f"echo s >> {vlog}; sleep 0.2; echo e >> {vlog}; test ! -f BROKEN")
        (self.bin / "barrier").write_text("3")
        code, out, err = self.go("--only", "01,04,11,12,13")  # 04는 01에 막혀 있다
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01", "04", "11", "12", "13"])
        ev = self.events()

        # 동시 실행: 첫 세 worker가 모두 시작한 뒤에야 누군가 끝난다(시작 시각이 겹친다)
        self.assertEqual(sorted(ev[:3]), ["start 01", "start 11", "start 12"], ev)
        running, peak = 0, 0
        for e in ev:
            running += 1 if e.startswith("start") else -1
            peak = max(peak, running)
        self.assertEqual(peak, 3, ev)  # max_workers를 넘지 않는다
        # 의존 순서: 04는 01이 끝난(병합된) 뒤에 시작하고, 01이 병합된 integration 위에서 일한다
        self.assertLess(ev.index("end 01"), ev.index("start 04"), ev)
        t04 = self.integration("log", "--format=%H", "--grep=^t04$", "gs/demo/integration")
        self.assertIn("file_01", self.integration("ls-tree", "--name-only", f"{t04}^").split())
        # brief의 base 줄: 04는 01이 병합된 base에서 시작하므로 줄에 01의 병합 커밋이 든다(같이 병합된 다른 티켓이 더 있을 수 있다).
        # 01은 아무것도 병합되기 전에 시작해 `없음`이다
        line = next(l for l in (self.rundir / "04/1/brief.md").read_text().splitlines() if l.startswith("- base에 이미 병합된 티켓: "))
        sha_01 = re.search(r"\b01\(([0-9a-f]+)\)", line)
        self.assertIsNotNone(sha_01, line)
        self.assertIn("gs-ticket: demo/01", self.integration("show", "-s", "--format=%B", sha_01[1]))
        self.assertIn("- base에 이미 병합된 티켓: 없음\n", (self.rundir / "01/1/brief.md").read_text())
        # 병합·검증은 한 번에 하나씩
        self.assertEqual(vlog.read_text().split(), ["s", "e"] * 7)  # 티켓 5 + integration 1 + main 1

    def test_parallel_conflict_retries_on_latest_integration(self):
        for tid in ("21", "22", "23"):
            self.add_ticket(tid)
        (self.repo / ".goldstack/work/demo/tickets/23-t.md").write_text(ticket("23", '["22"]'))
        sh(self.repo, "git", "commit", "-qam", "23 needs 22")
        self.parallel(3)
        (self.bin / "barrier").write_text("2")  # 21과 22가 같은 integration 끝에서 시작한다
        code, out, err = self.go("--only", "21,22,23")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo").tickets
        first, second = sorted(("21", "22"), key=lambda tid: st[tid].attempts)
        self.assertEqual((st[first].attempts, st[second].attempts), (1, 2), out)
        self.assertEqual((st[first].status, st[second].status, st["23"].status), ("merged", "merged", "merged"))
        self.assertIn(f"[{second}] 최신 integration(", out)
        self.assertIn("shared.txt", out)
        self.assertEqual(self.integration("show", "gs/demo/integration:shared.txt"), second)
        self.assertEqual(st[second].branch, f"gs/demo/{second}-retry-1")
        self.assertEqual(st[second].failed_worktrees, [str(self.rundir / "wt" / second)])
        retry_commit = self.integration("log", "--format=%H", f"--grep=^t{second}$", "gs/demo/integration")
        retry_parent = self.integration("rev-parse", f"{retry_commit}^")
        self.assertIn(f"gs-ticket: demo/{first}", self.integration("show", "-s", "--format=%B", retry_parent))
        failure_log = (self.rundir / second / "1/failure.log").read_text()
        self.assertIn("conflict", failure_log)
        self.assertIn("shared.txt", failure_log)
        brief = (self.rundir / second / "2/brief.md").read_text()
        self.assertIn("판단 모델의 실패 요약", brief)
        self.assertIn("conflict", brief)
        self.assertEqual(self.merged(), ["21", "22", "23"])
        wt = self.rundir / "wt" / second
        self.assertTrue(git_clean(wt))  # 합쳐 보다 만 병합은 취소했다
        self.assertNotEqual(subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=wt,
                                           capture_output=True).returncode, 0)

    def test_parallel_catches_up_with_integration(self):
        for tid in ("11", "12"):
            self.add_ticket(tid)
        self.parallel(3)
        (self.bin / "barrier").write_text("2")
        code, out, err = self.go("--only", "11,12")
        self.assertEqual(code, 0, out + err)
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_11", files)
        self.assertIn("file_12", files)

    def test_parallel_integration_tamper_is_undone(self):
        self.add_ticket("07")
        self.parallel(3)
        (self.bin / "barrier").write_text("2")
        code, out, err = self.go("--only", "01,07")
        self.assertEqual(code, 1, out + err)
        st = state.load(self.rundir, "demo").tickets
        self.assertEqual(st["01"].status, "merged", out)
        self.assertEqual(st["07"].status, "failed", out)
        self.assertNotIn("evil", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertNotIn("evil", sh(self.remote, "git", "ls-tree", "--name-only", "main").split())

    def test_herdr_panes_share_one_tab_per_feature(self):
        for tid in ("11", "12"):
            self.add_ticket(tid)
        self.parallel(3)
        (self.bin / "barrier").write_text("3")
        herdr_bin = self.bin / "herdr"
        herdr_bin.write_text("#!/bin/bash\n" + FAKE_HERDR)
        herdr_bin.chmod(0o755)
        env = {"GS_RUNNER": "herdr", "HERDR_BIN_PATH": str(herdr_bin), "HERDR_SESSION": "t",
               "HERDR_WORKSPACE_ID": "w1"}
        with mock.patch.dict(os.environ, env), mock.patch.object(worker, "POLL_SECONDS", 0.05):
            code, out, err = self.go("--only", "01,11,12,02")
        self.assertEqual(code, 1, out + err)  # 02는 가짜 worker가 실패시킨다
        cmds = (self.bin / "herdr.log").read_text().splitlines()
        self.assertEqual(sum(c.startswith("tab create") for c in cmds), 1, cmds)  # feature마다 탭 하나
        self.assertIn("--label gs:demo", next(c for c in cmds if c.startswith("tab create")))
        self.assertEqual(sum(c.startswith("pane split") for c in cmds), 4, cmds)  # 02 재시도도 새 pane
        closed = sorted(c.split()[2] for c in cmds if c.startswith("pane close"))
        panes = {tid: state.load(self.rundir, "demo").tickets[tid].pane.split()[-1] for tid in ("01", "02", "11", "12")}
        self.assertEqual(closed, sorted(panes[t] for t in ("01", "11", "12")))  # 성공한 pane만 닫는다
        self.assertEqual(self.merged(), ["01", "11", "12"])

    # --- codex 리뷰(03·04·05) 지적 재현 ---
    def test_rerun_stops_worker_left_by_killed_gs(self):  # 03 ①
        self.add_ticket("14")
        log = Path(self.tmp.name) / "first.log"
        with log.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "go", "demo",
                                     "--only", "14"], stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        old = None
        try:
            deadline = time.monotonic() + 30
            while not ((self.bin / "a14").exists() and (self.bin / "pid_14").exists()):
                self.assertIsNone(proc.poll(), log.read_text())
                self.assertLess(time.monotonic(), deadline, log.read_text())
                time.sleep(0.05)
            old = int((self.bin / "pid_14").read_text())
            first_log = state.load(self.rundir, "demo").tickets["14"].log
            os.kill(proc.pid, signal.SIGKILL)  # gs만 죽는다. worker는 살아 남는다
            proc.wait()
            self.assertTrue(alive(old))
            code, out, err = self.go("--only", "14")
            self.assertEqual(code, 0, out + err)  # 옛 시도의 종료 코드 1을 새 시도의 결과로 읽지 않는다
            self.assertIn("[14] 지난 실행의 worker가 아직 돌고 있어 끝냈다", out)
            self.assertFalse(alive(old))
            ts = state.load(self.rundir, "demo").tickets["14"]
            self.assertEqual((ts.status, ts.attempts), ("merged", 1))
            self.assertNotEqual(Path(ts.log).parent, Path(first_log).parent)  # 시도마다 실행 디렉터리가 따로다
        finally:
            if old:
                kill_quietly(old)

    def test_integration_change_during_verify_is_not_committed(self):  # 04 #1
        self.add_ticket("15")
        # 첫 검증은 15가 integration에 BROKEN을 만들 때까지 붙잡혀 있다가 통과한다(검증 도중에 바뀌었다). 실제 시간에 기대지 않는다
        seen, verifying = self.bin / "seen", self.bin / "verifying"
        self.parallel(3, verify=f"if [ ! -f {seen} ]; then touch {seen} {verifying}; test ! -f BROKEN || exit 1; "
                                f"for i in $(seq 1200); do [ -f BROKEN ] && break; sleep 0.05; done; exit 0; fi; test ! -f BROKEN")
        code, out, err = self.go("--only", "01,15")
        self.assertEqual(code, 0, out + err)
        st = state.load(self.rundir, "demo").tickets
        self.assertEqual(st["01"].status, "merged", out)  # 실패한 검증은 버리고 새 시도가 성공한다
        self.assertEqual(st["01"].attempts, 2)
        self.assertIn("검증하는 동안 integration이 바뀌었다", (self.rundir / "01/1/failure.log").read_text())
        self.assertEqual(st["15"].status, "merged", out)
        self.assertNotIn("BROKEN", self.integration("ls-tree", "-r", "--name-only", "gs/demo/integration").split())

    def test_one_worker_error_fails_only_that_ticket(self):  # 04 #2, 05 #2
        for tid in ("11", "12", "13"):
            self.add_ticket(tid)
        self.parallel(4)
        real_start = worker.SubprocessRunner.start

        def start(runner, job, label):
            if job.ticket.id == "12":
                raise herdr.HerdrError("timeout", "pane run 시간 초과")
            return real_start(runner, job, label)

        def prepare(adapter, inp):
            if "/13/" in str(inp.brief):
                raise FileExistsError(17, "File exists", ".agents")

        def outcome(adapter, code, inp):
            if "/11/" in str(inp.log):
                raise TypeError("'int' object is not iterable")
            return code, ""

        with mock.patch.object(worker.SubprocessRunner, "start", start), \
                mock.patch.object(adapters.Custom, "prepare", prepare, create=True), \
                mock.patch.object(adapters.Custom, "outcome", outcome, create=True):
            code, out, err = self.go("--only", "01,11,12,13")
        self.assertEqual(code, 1, out + err)
        st = state.load(self.rundir, "demo").tickets
        self.assertEqual({k: v.status for k, v in st.items()},
                         {"01": "merged", "11": "failed", "12": "failed", "13": "failed"}, out + err)
        self.assertIn("TypeError", st["11"].reason)
        self.assertIn("pane run 시간 초과", st["12"].reason)
        self.assertIn("FileExistsError", st["13"].reason)
        self.assertEqual(self.merged(), ["01"])

    def test_unexpected_error_stops_started_workers(self):  # 04 #2: 코디네이터가 죽어도 worker를 남기지 않는다
        self.add_ticket("11")
        self.parallel(3)
        (self.bin / "hang_11").touch()
        (self.bin / "barrier").write_text("2")  # 11이 시작한 뒤에 01이 끝난다
        try:
            with mock.patch("gs.go._verify", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    self.go("--only", "01,11")
            pid = int((self.bin / "pid_11").read_text())
            self.assertFalse(alive(pid))
        finally:
            if (self.bin / "pid_11").exists():
                kill_quietly(int((self.bin / "pid_11").read_text()))

    def test_worker_cannot_push(self):  # 구조적 push·gh 차단(hook·도구 차단과 별개)
        self.add_ticket("16")
        self.push_blocked([self.remote])
        self.assertIn("file_16", self.remote_files())  # gs push·병합은 된다(verified 뒤 원격 integration도 정리)

    def test_worker_cannot_push_with_pushurl(self):  # pushurl이 있으면 pushInsteadOf가 듣지 않는다
        self.add_ticket("16")
        mirror = Path(self.tmp.name) / "mirror.git"
        sh(Path(self.tmp.name), "git", "clone", "-q", "--bare", str(self.remote), str(mirror))
        sh(self.repo, "git", "config", "remote.origin.pushurl", str(mirror))
        self.push_blocked([self.remote, mirror], expected_code=1)
        self.assertIn("gs/demo/integration", sh(mirror, "git", "branch", "--list", "gs/demo/integration"))

    # --- codex 리뷰(02) 지적 재현 ---
    def test_worker_commit_to_integration_is_undone_and_not_pushed(self):  # 지적 2
        self.add_ticket("07", deps='["01"]')  # 01의 병합과 겹치면 누구 짓인지 가릴 수 없다
        code, out, _ = self.go("--only", "01,07")
        self.assertEqual(code, 1)
        self.assertIn("[07] 실패: worker가 integration worktree를 바꿨다", out)
        self.assertNotIn("evil", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertNotIn("evil", sh(self.remote, "git", "ls-tree", "--name-only", "main").split())

    def test_dirty_integration_is_cleaned_and_ticket_fails(self):  # 지적 3
        self.add_ticket("08", deps='["01"]')  # 01의 병합과 겹치면 누구 짓인지 가릴 수 없다
        code, out, _ = self.go("--only", "08,01")
        self.assertIn("[08] 실패: worker가 integration worktree를 바꿨다", out)
        self.assertIn("[01] 검증 통과", out)  # BROKEN이 지워져 01 검증은 깨끗한 트리에서 돈다
        self.assertFalse((self.repo / ".goldstack/work/demo/run/wt/integration/BROKEN").exists())

    def test_title_is_not_executed(self):  # 지적 4
        self.add_ticket("09", title='"`touch PWNED1` \\"q\\" $(touch PWNED2)"')
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        hits = list(Path(self.tmp.name).rglob("PWNED*"))
        self.assertEqual(hits, [])

    def test_interrupted_merge_is_discarded_and_ticket_rerun(self):  # 지적 1
        self.assertEqual(self.go("--only", "01")[0], 0)
        iwt = self.repo / ".goldstack/work/demo/run/wt/integration"
        from gs import git
        git.ensure_worktree(self.repo, iwt, "gs/demo/integration", state.load(self.rundir, "demo").finish["head"])
        sh(self.repo, "git", "branch", "gs/demo/04", "gs/demo/integration")
        (iwt / "half").write_text("x")
        sh(iwt, "git", "switch", "-q", "gs/demo/04")
        sh(iwt, "git", "add", "half")
        sh(iwt, "git", "commit", "-qm", "half")
        sh(iwt, "git", "switch", "-q", "gs/demo/integration")
        sh(iwt, "git", "merge", "--no-ff", "--no-commit", "gs/demo/04")  # 검증 도중 죽은 상태
        code, out, _ = self.go("--only", "01,04")
        self.assertEqual(code, 0, out)
        self.assertIn("남은 병합·변경을 버렸다", out)
        self.assertIn("[04] 검증 통과", out)  # 이미 병합으로 보지 않고 다시 했다
        self.assertEqual(self.merged(), ["01", "04"])
        self.assertNotIn("half", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_integration_starts_from_origin_main(self):  # 지적 5
        other = Path(self.tmp.name) / "other"
        sh(Path(self.tmp.name), "git", "clone", "-q", str(self.remote), str(other))
        (other / "upstream.txt").write_text("u")
        sh(other, "git", "add", "-A")
        sh(other, "git", "commit", "-qm", "upstream")
        sh(other, "git", "push", "-q", "origin", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("upstream.txt", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_unpushed_ticket_change_stops_before_launch(self):  # 지적 5
        self.add_ticket("10", push=False)
        code, out, err = self.go("--only", "10")
        self.assertEqual(code, 1)
        self.assertIn("origin/main와 다르다", err)
        self.assertNotIn("시작:", out)

    def test_scenario(self):
        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        self.assertIn("[03] 건너뜀: 02 실패", out)
        self.assertIn("[02] 실패: worker 종료 코드 1", out)
        self.assertIn("[05] 실패: 검증 실패", out)
        self.assertIn("[06] 실패: 커밋 없음", out)
        self.assertIn("■ PR: https://example.test/pr/1", out)
        # 순서는 리뷰가 끝나는 때에 달렸다. 05는 검증 실패라 시도마다 수리 worker도 돈다
        self.assertEqual(sorted(self.calls()), ["01", "02", "02", "04", "05", "05", "05", "05", "06", "06"])

        log = self.integration("log", "--format=%B", "gs/demo/integration")
        merged = sorted(line.split("/")[-1] for line in log.splitlines() if line.startswith("gs-ticket:"))
        self.assertEqual(merged, ["01", "04"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", files)
        self.assertNotIn("BROKEN", files)  # 검증 실패한 병합은 되돌렸다
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")  # GS_ROLE 전달

        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/demo/integration"), "")
        gh_log = (self.bin / "gh.log").read_text()
        self.assertIn("pr create --base main --head gs/demo/integration", gh_log)
        self.assertIn("pr merge https://example.test/pr/1 --merge --match-head-commit", gh_log)
        self.assertEqual(self.integration("show", "origin/main:file_01"), "01 worker")

        # 상태의 원천은 state.json 하나
        raw = json.loads((self.rundir / "state.json").read_text())
        t = raw["tickets"]
        self.assertEqual({k: v["status"] for k, v in t.items()},
                         {"01": "merged", "02": "failed", "03": "skipped", "04": "merged", "05": "failed",
                          "06": "failed"})
        self.assertEqual(t["02"]["reason"], "worker 종료 코드 1")
        self.assertEqual(t["03"]["reason"], "막힘: 02")
        self.assertEqual(t["03"]["attempts"], 0)
        self.assertEqual([(p["attempt"], p["phase"]) for p in t["02"]["phases"]],
                         [(1, "worker"), (2, "worker")])
        self.assertTrue(all(p["ended_at"] for p in t["02"]["phases"]))
        one = t["01"]
        self.assertEqual((one["attempts"], one["branch"]), (1, "gs/demo/01"))
        self.assertTrue(one["pane"].startswith("pid "), one["pane"])
        self.assertTrue(one["log"].endswith("run/01/1/worker.log") and Path(one["log"]).exists())
        self.assertTrue(one["started_at"] and one["ended_at"])
        self.assertTrue(raw["finished_at"])
        self.assertEqual(list(self.rundir.glob(".state.*")), [])  # 임시 파일이 남지 않는다

    def test_killed_gs_resumes_with_remaining_tickets_only(self):
        self.add_ticket("11", deps='["04"]')  # 04가 붙잡힌 동안 11은 대기다. 01이 리뷰 중일 때 먼저 시작하지 않게
        (self.bin / "hang_04").touch()
        log = Path(self.tmp.name) / "first.log"
        with log.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "go", "demo",
                                     "--only", "01,04,11"], stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while True:
                st = state.load(self.rundir, "demo")
                t = st.tickets.get("04")
                # 로그가 생겨야 '마지막 출력'이 찍힌다. 상태가 running이 된 직후에는 아직 없을 수 있다(경합)
                if t and t.status == "running" and t.pane and t.log and Path(t.log).exists():
                    break
                self.assertIsNone(proc.poll(), log.read_text())
                self.assertLess(time.monotonic(), deadline, log.read_text())
                time.sleep(0.05)

            # 도는 동안 gs status는 읽기만 하고 실행 중으로 보여 준다
            before = {p: p.stat().st_mtime_ns for p in self.rundir.rglob("*") if p.is_file()}
            code, out = self.status()
            self.assertEqual(code, 0)
            self.assertIn(f"demo: 실행 중(pid {proc.pid})", out)
            self.assertRegex(out, r"04\s+실행 중\s+1\s+\S+\s+\d\d:\d\d:\d\d")
            self.assertRegex(out, r"01\s+병합\s+1")
            self.assertRegex(out, r"11\s+대기\s+0")
            code, again = self.status("demo")
            self.assertIn(f"demo: 실행 중(pid {proc.pid})", again)
            after = {p: p.stat().st_mtime_ns for p in self.rundir.rglob("*") if p.is_file()
                     if not p.name.startswith(("worker.log", "exit"))}
            self.assertEqual({p: before.get(p) for p in after}, after)  # 만들거나 바꾼 파일이 없다
            code, _, err = self.go("--only", "11")  # 같은 feature 두 번째 gs go는 거부
            self.assertEqual(code, 1)
            self.assertIn(f"이미 다른 gs go가 돌고 있다(pid {proc.pid})", err)
        finally:
            os.killpg(proc.pid, signal.SIGKILL)  # gs와 worker를 함께 죽인다(터미널이 닫힌 것처럼)
            proc.wait()
        self.assertEqual(self.calls(), ["01", "04"])
        code, out = self.status("demo")
        self.assertIn("중단됨", out)
        self.assertIn("실행 중(중단)", out)
        self.assertIn("실행 중인 feature가 없다", self.status()[1])

        (self.bin / "hang_04").unlink()
        code, out, err = self.go("--only", "01,04,11")
        self.assertEqual(code, 0, out + err)
        self.assertIn("[04] 지난 실행이 중간에 끝나 running으로 남았다", out)
        self.assertIn("[01] 이미 병합됨", out)
        self.assertEqual(self.calls(), ["01", "04", "04", "11"])  # 두 번째 실행은 남은 티켓만
        self.assertEqual(self.merged(), ["01", "04", "11"])
        st = state.load(self.rundir, "demo")
        self.assertEqual({k: (v.status, v.attempts) for k, v in st.tickets.items()},
                         {"01": ("merged", 1), "04": ("merged", 1), "11": ("merged", 1)})  # 죽은 시도는 세지 않음
        # 표시상 attempts가 다시 1이어도 중단된 시도와 새 시도의 단계 시각은 따로 보존한다.
        phases = st.tickets["04"].phases
        self.assertEqual([(p["attempt"], p["phase"]) for p in phases if p["phase"] == "worker"],
                         [(1, "worker"), (2, "worker")])
        self.assertTrue(all(p["started_at"] and p["ended_at"] for p in phases))

    def test_second_go_is_refused_while_locked(self):
        with state.Lock(self.rundir):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1)
        self.assertIn(f"이미 다른 gs go가 돌고 있다(pid {os.getpid()})", err)
        self.assertNotIn("시작:", out)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.go("--only", "01")[0], 0)  # 풀린 뒤에는 돈다

    def test_lock_of_dead_process_is_reclaimed(self):
        dead = subprocess.Popen(["true"])
        dead.wait()
        self.rundir.mkdir(parents=True)
        (self.rundir / "lock").write_text(f"{dead.pid}\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual((self.rundir / "lock").read_text(), "")  # 정상 종료하면 비운다

    def test_rerun_skips_merged_and_retries_failed(self):
        code, out, _ = self.go("--only", "01,06")
        self.assertEqual(code, 1)
        code, out, _ = self.go("--only", "01,06")
        self.assertIn("[01] 이미 병합됨", out)
        self.assertIn("[06] 실패: 커밋 없음", out)
        self.assertEqual(self.calls(), ["01", "06", "06", "06", "06"])
        st = state.load(self.rundir, "demo")
        self.assertEqual((st.tickets["01"].attempts, st.tickets["06"].attempts), (1, 4))
        self.assertEqual(len(st.tickets["06"].failed_worktrees), 4)

    def test_status_without_runs(self):
        code, out = self.status()
        self.assertEqual(code, 0)
        self.assertIn("실행 중인 feature가 없다", out)
        code, out = self.status("demo")
        self.assertIn("실행 기록이 없다", out)
        self.assertFalse(self.rundir.exists())  # 읽기 전용: run/을 만들지 않는다
        self.assertEqual(self.status("nope")[0], 1)
        self.go("--only", "01")
        code, out = self.status()
        self.assertIn("지난 실행 기록: demo", out)
        code, out = self.status("demo")
        self.assertIn("demo: 끝남(", out)
        self.assertIn("범위 01", out)

    def test_only_then_resume_skips_merged(self):
        code, out, _ = self.go("--only", "01")
        self.assertEqual(code, 0, out)
        self.assertIn("■ 순서: 01\n", out)
        code, out, _ = self.go("--only", "01,04")
        self.assertEqual(code, 0, out)
        self.assertIn("[01] 이미 병합됨", out)
        self.assertIn("[04] 검증 통과", out)

    def test_uncommitted_ticket_change_stops_before_launch(self):
        (self.repo / ".goldstack/work" / "demo" / "tickets" / "01-t.md").write_text(ticket("01") + "more\n")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("origin/main와 다르다", err)
        self.assertNotIn("시작:", out)

    def test_check_error_stops_before_launch(self):
        (self.repo / ".goldstack/work" / "demo" / "tickets" / "07-t.md").write_text(ticket("07", '["99"]'))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "bad")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("아무것도 띄우지 않았다", err)
        self.assertNotIn("시작:", out)


if __name__ == "__main__":
    unittest.main()
