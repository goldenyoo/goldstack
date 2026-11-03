"""`gs go` 시나리오 시험(시험 seam): 임시 git 레포 + 로컬 bare 원격 + 가짜 worker + 가짜 gh."""
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, state

FAKE_WORKER = """\
echo "$GS_TICKET" >> "$(dirname "$0")/calls.log"
if [ -f "$(dirname "$0")/hang_$GS_TICKET" ]; then  # gs가 죽을 때까지 붙잡아 둔다(최대 20초)
  for i in $(seq 400); do sleep 0.05; done; exit 1
fi
case "$GS_TICKET" in
  02) echo "boom"; exit 1 ;;
  05) touch BROKEN; git add BROKEN; git commit -qm "t05 breaks verify" ;;
  06) echo "did nothing" ;;
  07) echo x > "$GS_WORKTREE/../integration/evil"; git -C "$GS_WORKTREE/../integration" add evil
      git -C "$GS_WORKTREE/../integration" commit -qm evil ;;
  08) touch "$GS_WORKTREE/../integration/BROKEN"; echo 8 > file_08; git add -A; git commit -qm t08 ;;
  *)  echo "$GS_TICKET $GS_ROLE" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET" ;;
esac
"""

FAKE_GH = """\
echo "$@" >> "$(dirname "$0")/gh.log"
case "$1 $2" in
  "pr list") exit 0 ;;
  "pr create") echo "https://example.test/pr/1" ;;
  "pr edit") exit 0 ;;
esac
"""

SPEC = """---
feature: demo
verify: test ! -f BROKEN
---
"""


def ticket(tid, deps="[]", title=None):
    title = title or f"t{tid}"
    return f'---\nid: "{tid}"\ntitle: {title}\nblocked_by: {deps}\nmodel: claude\nreviewer: codex\n---\n## 목표\n{tid}\n'


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class GoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        (self.bin / "worker.sh").write_text(FAKE_WORKER)
        (self.bin / "gh").write_text("#!/bin/bash\n" + FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.env = mock.patch.dict(os.environ, {
            "GS_RUNNER": "subprocess",
            "GS_WORKER_CMD": f"bash {self.bin / 'worker.sh'}",
            "GS_GH": str(self.bin / "gh"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        self.env.start()
        self.remote = root / "remote.git"
        sh(root, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / ".gitignore").write_text(".work/*/run/\n")
        fdir = self.repo / ".work" / "demo"
        (fdir / "tickets").mkdir(parents=True)
        (fdir / "spec.md").write_text(SPEC)
        for tid, deps in [("01", "[]"), ("02", "[]"), ("03", '["02"]'), ("04", '["01"]'), ("05", "[]"), ("06", "[]")]:
            (fdir / "tickets" / f"{tid}-t.md").write_text(ticket(tid, deps))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        sh(self.repo, "git", "remote", "add", "origin", str(self.remote))
        sh(self.repo, "git", "push", "-q", "-u", "origin", "main")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "go", "demo", *extra])
        return code, out.getvalue(), err.getvalue()

    def status(self, *feature):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--repo", str(self.repo), "status", *feature])
        return code, out.getvalue()

    @property
    def rundir(self):
        return self.repo / ".work" / "demo" / "run"

    def calls(self):
        p = self.bin / "calls.log"
        return p.read_text().split() if p.exists() else []

    def integration(self, *args):
        return sh(self.repo, "git", *args)

    def add_ticket(self, tid, title=None, push=True):
        (self.repo / ".work" / "demo" / "tickets" / f"{tid}-t.md").write_text(ticket(tid, title=title))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", f"ticket {tid}")
        if push:
            sh(self.repo, "git", "push", "-q", "origin", "main")

    def merged(self):
        log = self.integration("log", "--format=%B", "gs/demo/integration")
        return sorted(line.split("/")[-1] for line in log.splitlines() if line.startswith("gs-ticket:"))

    # --- codex 리뷰(02) 지적 재현 ---
    def test_worker_commit_to_integration_is_undone_and_not_pushed(self):  # 지적 2
        self.add_ticket("07")
        code, out, _ = self.go("--only", "01,07")
        self.assertEqual(code, 1)
        self.assertIn("[07] 실패: worker가 integration worktree를 바꿨다", out)
        self.assertNotIn("evil", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertNotIn("evil", sh(self.remote, "git", "ls-tree", "--name-only", "gs/demo/integration").split())

    def test_dirty_integration_is_cleaned_and_ticket_fails(self):  # 지적 3
        self.add_ticket("08")
        code, out, _ = self.go("--only", "08,01")
        self.assertIn("[08] 실패: worker가 integration worktree를 바꿨다", out)
        self.assertIn("[01] 검증 통과", out)  # BROKEN이 지워져 01 검증은 깨끗한 트리에서 돈다
        self.assertFalse((self.repo / ".work/demo/run/wt/integration/BROKEN").exists())

    def test_title_is_not_executed(self):  # 지적 4
        self.add_ticket("09", title='"`touch PWNED1` \\"q\\" $(touch PWNED2)"')
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        hits = list(Path(self.tmp.name).rglob("PWNED*"))
        self.assertEqual(hits, [])

    def test_interrupted_merge_is_discarded_and_ticket_rerun(self):  # 지적 1
        self.assertEqual(self.go("--only", "01")[0], 0)
        iwt = self.repo / ".work/demo/run/wt/integration"
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

        log = self.integration("log", "--format=%B", "gs/demo/integration")
        merged = sorted(line.split("/")[-1] for line in log.splitlines() if line.startswith("gs-ticket:"))
        self.assertEqual(merged, ["01", "04"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", files)
        self.assertNotIn("BROKEN", files)  # 검증 실패한 병합은 되돌렸다
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")  # GS_ROLE 전달

        self.assertEqual(sh(self.remote, "git", "rev-parse", "gs/demo/integration"),
                         self.integration("rev-parse", "gs/demo/integration"))
        gh_log = (self.bin / "gh.log").read_text()
        self.assertIn("pr create --base main --head gs/demo/integration", gh_log)
        self.assertNotIn("merge", gh_log)  # 08 전까지 병합하지 않는다
        self.assertEqual(self.integration("rev-parse", "main"), self.integration("rev-parse", "origin/main"))

        # 상태의 원천은 state.json 하나
        raw = json.loads((self.rundir / "state.json").read_text())
        t = raw["tickets"]
        self.assertEqual({k: v["status"] for k, v in t.items()},
                         {"01": "merged", "02": "failed", "03": "skipped", "04": "merged", "05": "failed",
                          "06": "failed"})
        self.assertEqual(t["02"]["reason"], "worker 종료 코드 1")
        self.assertEqual(t["03"]["reason"], "막힘: 02")
        self.assertEqual(t["03"]["attempts"], 0)
        one = t["01"]
        self.assertEqual((one["attempts"], one["branch"]), (1, "gs/demo/01"))
        self.assertTrue(one["pane"].startswith("pid "), one["pane"])
        self.assertTrue(one["log"].endswith("run/01/worker.log") and Path(one["log"]).exists())
        self.assertTrue(one["started_at"] and one["ended_at"])
        self.assertTrue(raw["finished_at"])
        self.assertEqual(list(self.rundir.glob(".state.*")), [])  # 임시 파일이 남지 않는다

    def test_killed_gs_resumes_with_remaining_tickets_only(self):
        self.add_ticket("11")
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
                if t and t.status == "running" and t.pane:
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
        self.assertEqual(self.calls(), ["01", "06", "06"])
        st = state.load(self.rundir, "demo")
        self.assertEqual((st.tickets["01"].attempts, st.tickets["06"].attempts), (1, 2))

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
        (self.repo / ".work" / "demo" / "tickets" / "01-t.md").write_text(ticket("01") + "more\n")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("origin/main와 다르다", err)
        self.assertNotIn("시작:", out)

    def test_check_error_stops_before_launch(self):
        (self.repo / ".work" / "demo" / "tickets" / "07-t.md").write_text(ticket("07", '["99"]'))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "bad")
        code, out, err = self.go()
        self.assertEqual(code, 1)
        self.assertIn("아무것도 띄우지 않았다", err)
        self.assertNotIn("시작:", out)


if __name__ == "__main__":
    unittest.main()
