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

from gs import adapters, cli, config, herdr, review, state, worker
from support import isolate_git_env


def git_clean(wt):
    return subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout == ""


def alive(pid):
    """좀비는 죽은 것으로 본다."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def kill_quietly(pid):
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


FAKE_WORKER = """\
here="$(dirname "$0")"
echo "$GS_TICKET" >> "$here/calls.log"
echo $$ > "$here/pid_$GS_TICKET"
echo "start $GS_TICKET" >> "$here/events.log"
trap 'echo "end $GS_TICKET" >> "$here/events.log"' EXIT
if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then  # 리뷰 뒤 수정 worker(06)
  echo "fix $GS_TICKET" >> "$here/fix.log"
  if [ -f "$here/fixfail" ]; then echo bad > "badfix_$GS_TICKET"; git add -A; git commit -qm "bad fix"; exit 3; fi
  echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
fi
if [ -f "$here/barrier" ]; then  # 시작한 worker가 barrier개가 될 때까지 기다린다(최대 10초): 동시 실행의 증거
  for i in $(seq 200); do [ "$(grep -c '^start' "$here/events.log")" -ge "$(cat "$here/barrier")" ] && break; sleep 0.05; done
fi
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
  2[12]) echo "$GS_TICKET" > shared.txt; git add -A; git commit -qm "t$GS_TICKET" ;;  # 같은 파일을 다르게
  14) if [ ! -f "$here/a14" ]; then touch "$here/a14"  # 첫 시도: release14가 생길 때까지 붙잡혀 있다가 실패로 끝난다
        for i in $(seq 400); do [ -f "$here/release14" ] && break; sleep 0.05; done; exit 1
      fi
      touch "$here/release14"; sleep 1  # 새 시도: 옛 시도를 풀어 준 뒤 천천히 끝낸다
      echo 14 > file_14; git add -A; git commit -qm t14 ;;
  15) for i in $(seq 200); do [ -f "$here/verifying" ] && break; sleep 0.05; done  # 다른 티켓의 검증 도중에
      touch "$GS_WORKTREE/../integration/BROKEN"; git -C "$GS_WORKTREE/../integration" add BROKEN
      echo 15 > file_15; git add -A; git commit -qm t15 ;;
  16) git fetch -q origin && echo ok > "$here/fetch_16"
      if git push -q origin HEAD:refs/heads/leak 2>"$here/push_16"; then echo pushed >> "$here/push_16"; fi
      echo "$GH_TOKEN" > "$here/gh_16"
      echo 16 > file_16; git add -A; git commit -qm t16 ;;
  *)  echo "$GS_TICKET $GS_ROLE" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET" ;;
esac
"""

FAKE_HERDR = """\
# 가짜 herdr: 부른 명령을 적고, pane run은 백그라운드로 실제 실행한다. 상태는 이 스크립트 옆 파일에.
here="$(dirname "$0")"
shift 2  # --session <name>
echo "$@" >> "$here/herdr.log"
next() { n=$(( $(cat "$here/herdr.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/herdr.n"; echo "w1:p$n"; }
case "$1 $2" in
  "tab create") p=$(next); echo '{"result":{"tab":{"tab_id":"w1:t1"},"root_pane":{"pane_id":"'$p'"}}}' ;;
  "pane split") [ -f "$here/closed_$3" ] && { echo '{"error":{"code":"not_found","message":"no pane"}}' >&2; exit 1; }
                p=$(next); echo '{"result":{"pane":{"pane_id":"'$p'"}}}' ;;
  "pane run") nohup bash -c "$4" >/dev/null 2>&1 & ;;
  "pane get") [ -f "$here/closed_$3" ] && { echo '{"error":{"code":"not_found","message":"no pane"}}' >&2; exit 1; }
              echo '{"result":{"pane":{"pane_id":"'$3'"}}}' ;;
  "pane close") touch "$here/closed_$3" ;;
  *) echo '{"error":{"code":"unknown","message":"fake herdr"}}' >&2; exit 1 ;;
esac
"""

FAKE_GH = """\
here="$(dirname "$0")"
B="${GS_FAKE_BASE:-main}"; R="${GS_FAKE_REMOTE:-origin}"  # 시험 레포의 git.base·git.remote
echo "$@" >> "$here/gh.log"
[[ "${@: -2:1}" = --repo && -n "${@: -1}" ]] || { echo 'missing --repo' >&2; exit 2; }
body() { while [ "$#" -gt 0 ]; do
  if [ "$1" = --body-file ]; then cp "$2" "$here/pr-body.md"; break; fi
  shift
done; }
case "$1 $2" in
  "pr list") [ -f "$here/gh.open" ] && echo "https://example.test/pr/1"; exit 0 ;;
  "pr create") body "$@"; touch "$here/gh.open"; rm -f "$here/gh.merged" "$here/gh.closed"
    echo "https://example.test/pr/1" ;;
  "pr edit") body "$@" ;;
  "pr view")
    if [ -f "$here/gh.closed" ]; then echo '{"state":"CLOSED","baseRefName":"'$B'"}'
    elif [ -f "$here/gh.merged" ]; then cat "$here/gh.merged"
    else echo '{"state":"OPEN"}'; fi ;;
  "pr merge")
    [ -f "$here/gh.closed" ] && { echo 'Pull request is closed' >&2; exit 1; }
    [ -f "$here/gh.queue" ] && exit 0
    [ -f "$here/gh.reject" ] && { echo 'merge refused' >&2; exit 1; }
    set -e
    head=$(git rev-parse gs/demo/integration)
    [ "$6" = "$head" ] || { echo 'head mismatch' >&2; exit 1; }
    remote=$(git remote get-url --push "$R")
    if [ ! -d "$here/merge" ]; then git clone -q "$remote" "$here/merge"; fi
    git -C "$here/merge" fetch -q origin
    git -C "$here/merge" reset -q --hard "origin/$B"
    git -C "$here/merge" merge -q --no-ff origin/gs/demo/integration -m 'Merge feature'
    git -C "$here/merge" push -q origin "HEAD:refs/heads/$B"
    sha=$(git -C "$here/merge" rev-parse HEAD)
    echo '{"state":"MERGED","mergeCommit":{"oid":"'$sha'"},"headRefOid":"'$head'","baseRefName":"'$B'"}' > "$here/gh.merged"
    rm -f "$here/gh.open"
    [ -f "$here/gh.badexit" ] && exit 1; exit 0 ;;
esac
"""

FAKE_REVIEWER = """\
# 가짜 reviewer: 프롬프트와 diff를 남기고, findings.json이 있으면 그것을(설명과 코드 블록으로 감싸) 답한다.
here="$(dirname "$0")"
echo "$GS_REVIEWER" >> "$here/review.calls"
cat > "$here/review.prompt"
cp "$(grep -o '/[^ `]*diff.patch' "$here/review.prompt" | head -n 1)" "$here/review.diff"
if [ -f "$here/findings.json" ]; then echo '리뷰 결과:'; echo '```json'; cat "$here/findings.json"; echo '```'
else echo '{"findings": []}'; fi
"""

# 가짜 판단 모델(리뷰 분류): claim에 FIX가 있으면 fix, 아니면 report. 프롬프트에서 findings.json 경로만 읽는다.
FAKE_REVIEW_JUDGE = """\
here="$(dirname "$0")"
echo "$@" >> "$here/judge.calls"
cat > "$here/judge.input"
if grep -q report-input.md "$here/judge.input"; then echo '남은 리뷰 지적과 검증 출력을 확인했다.'; exit 0; fi
"$PY" - "$(grep -o '/[^ `]*findings.json' "$here/judge.input" | head -n 1)" <<'PYEOF'
import json, sys
fs = json.load(open(sys.argv[1]))["findings"]
print(json.dumps({"decisions": [{"id": f["id"], "action": "fix" if "FIX" in f["claim"] else "report", "why": "가짜"}
                                for f in fs]}))
PYEOF
"""

FAKE_JUDGE = """\
here="$(dirname "$0")"
echo "$@" >> "$here/judge.calls"
cat > "$here/judge.input"
if grep -q report-input.md "$here/judge.input"; then echo '티켓의 변경을 integration에서 모아 검증했다.'; exit 0; fi
cp "$here/judge.input" "$here/failure-judge.input"
log=$(tail -n 1 "$here/judge.input")
echo '판단 모델의 실패 요약'
head -n 4 "$log"
"""

SPEC = """---
feature: demo
verify: test ! -f BROKEN
max_workers: 1
---
"""  # 02부터의 시험은 순차(max_workers 1)로 돈다. 병렬 시험은 ParallelTest


def ticket(tid, deps="[]", title=None):
    title = title or f"t{tid}"
    return f'---\nid: "{tid}"\ntitle: {title}\nblocked_by: {deps}\nmodel: claude\nreviewer: codex\n---\n## 목표\n{tid}\n'


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class GoTest(unittest.TestCase):
    BASE, REMOTE = "main", "origin"  # .goldstack/config.toml [git]. TrunkUpstreamTest가 바꾼다

    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.bin = root / "bin"
        self.bin.mkdir()
        for name in ("claude", "codex"):
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 1\n")
            path.chmod(0o755)
        (self.bin / "worker.sh").write_text(FAKE_WORKER)
        (self.bin / "gh").write_text("#!/bin/bash\n" + FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        (self.bin / "judge").write_text("#!/bin/bash\n" + FAKE_JUDGE)
        (self.bin / "judge").chmod(0o755)
        (self.bin / "reviewer.sh").write_text(FAKE_REVIEWER)
        self.env = mock.patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "GS_REVIEWER_CMD": f"bash {self.bin / 'reviewer.sh'}",
            "GS_RUNNER": "subprocess",
            "GS_WORKER_CMD": f"bash {self.bin / 'worker.sh'}",
            "GS_GH": str(self.bin / "gh"),
            "GS_JUDGE": str(self.bin / "judge"),
            "GS_FAKE_BASE": self.BASE, "GS_FAKE_REMOTE": self.REMOTE,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        self.env.start()
        self.remote = root / "remote.git"
        sh(root, "git", "init", "-q", "--bare", "-b", self.BASE, str(self.remote))
        self.repo = root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", self.BASE)
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base=f'"{self.BASE}"')
                                                     .replace('remote = "origin"', f'remote = "{self.REMOTE}"'))
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n")
        fdir = self.repo / ".goldstack/work" / "demo"
        (fdir / "tickets").mkdir(parents=True)
        (fdir / "spec.md").write_text(SPEC)
        for tid, deps in [("01", "[]"), ("02", "[]"), ("03", '["02"]'), ("04", '["01"]'), ("05", "[]"), ("06", "[]")]:
            (fdir / "tickets" / f"{tid}-t.md").write_text(ticket(tid, deps))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        url = f"https://github.com/test/{self.REMOTE}.git"
        sh(self.repo, "git", "remote", "add", self.REMOTE, url)
        sh(self.repo, "git", "config", f"url.{self.remote}.insteadOf", url)
        sh(self.repo, "git", "push", "-q", "-u", self.REMOTE, self.BASE)

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
        return self.repo / ".goldstack/work" / "demo" / "run"

    def calls(self):
        p = self.bin / "calls.log"
        return p.read_text().split() if p.exists() else []

    def integration(self, *args):
        # verified 뒤 브랜치는 정리된다. 커밋 내용 검사는 state에 남긴 마지막 integration head를 본다.
        if args and args[0] in ("log", "show", "ls-tree", "rev-parse", "rev-list") and any(
                "gs/demo/integration" in arg for arg in args[1:]):
            if not sh(self.repo, "git", "branch", "--list", "gs/demo/integration"):
                head = state.load(self.rundir, "demo").finish["head"]
                args = tuple(arg.replace("gs/demo/integration", head) for arg in args)
        return sh(self.repo, "git", *args)

    def add_ticket(self, tid, title=None, push=True):
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        (self.repo / ".goldstack/work" / "demo" / "tickets" / f"{tid}-t.md").write_text(ticket(tid, title=title))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", f"ticket {tid}")
        if push:
            sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def merged(self):
        log = self.integration("log", "--format=%B", "gs/demo/integration")
        return sorted(line.split("/")[-1] for line in log.splitlines() if line.startswith("gs-ticket:"))

    def parallel(self, n=3, verify="test ! -f BROKEN"):
        """spec을 max_workers n으로 바꿔 커밋·push한다."""
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text(
            f"---\nfeature: demo\nverify: {verify}\nmax_workers: {n}\n---\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", f"max_workers {n}")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def events(self):
        return (self.bin / "events.log").read_text().split("\n")[:-1]

    # --- 마무리(08): 로컬 bare 원격도 실제로 병합·revert한다 ---
    def final_report(self):
        return self.integration("show", "gs/demo/integration:.goldstack/work/demo/report.md")

    def under_report(self):
        """마무리가 verified·reverted면 원격 base 끝은 gs의 최종 보고서 커밋(goldstack-v3 02)이다. 그 아래 끝."""
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", self.BASE), "gs: demo 최종 보고서(병합 후)")
        return sh(self.remote, "git", "rev-parse", f"{self.BASE}^")

    def test_progress_is_saved_during_each_phase(self):
        snapshots = []
        save = state.save

        def observe(rundir, st):
            save(rundir, st)
            # 메모리 객체가 아닌 실제 독자가 보는 중간 state.json을 읽는다.
            snapshots.append(json.loads(state.path(rundir).read_text()))

        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다",
                                "evidence": "값이 틀림"}]), mock.patch.object(state, "save", side_effect=observe):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        phases = []
        for snapshot in snapshots:
            p = snapshot["progress"]
            self.assertEqual(p["total"], 1)
            self.assertIn(p["done"], (0, 1))
            for active in p["running"]:
                if not phases or phases[-1] != active["phase"]:
                    phases.append(active["phase"])
                if active["phase"] == "review":
                    self.assertEqual((active["id"], active["model"]), ("01", "codex"))
            if snapshot["phase"] == "finish":
                self.assertEqual(p["running"], [{"id": "", "phase": "finish", "model": "claude"}])
        self.assertEqual(phases, ["worker", "review", "fix", "rereview", "verify", "finish"])
        last = snapshots[-1]
        self.assertTrue(last["finished_at"])
        self.assertEqual((last["progress"]["done"], last["progress"]["running"]), (1, []))
        self.assertEqual([p["phase"] for p in last["tickets"]["01"]["phases"]], phases)
        self.assertTrue(all(p["started_at"] and p["ended_at"] for p in last["tickets"]["01"]["phases"]))
        self.assertIn("단계별 소요:", self.final_report())
        self.assertEqual(self.status("demo")[1].splitlines()[-1], last["progress"]["line"])

    # --- 병합한 티켓 worktree·브랜치 정리(v1 02) ---
    def assert_ticket_cleaned(self, tid, suffix=""):
        wt = self.rundir / "wt" / (tid + suffix)
        self.assertFalse(wt.exists())
        self.assertNotIn(str(wt), self.integration("worktree", "list", "--porcelain"))
        self.assertEqual(self.integration("branch", "--list", f"gs/demo/{tid}{suffix}"), "")

    def test_merged_ticket_is_cleaned_before_next_worker(self):
        (self.bin / "worker.sh").write_text(FAKE_WORKER + '''
if [ "$GS_TICKET" = 04 ]; then
  test ! -d "$GS_WORKTREE/../01" || exit 9
  test -z "$(git branch --list gs/demo/01)" || exit 10
fi
''')
        code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        for tid in ("01", "04"):
            self.assert_ticket_cleaned(tid)
            self.assertIn(f"[{tid}] worktree 정리: {self.rundir / 'wt' / tid}", out)
        self.assertFalse((self.rundir / "wt/integration").exists())
        self.assertEqual(self.integration("branch", "--list", "gs/demo/integration"), "")
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/demo/integration"), "")

    def test_dirty_merged_ticket_is_kept_and_reported_until_clean(self):
        (self.bin / "worker.sh").write_text(FAKE_WORKER + '\necho unfinished > pending.txt\n')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        wt = self.rundir / "wt/01"
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.kept_worktrees), ("merged", [str(wt)]))
        self.assertTrue((wt / "pending.txt").exists())
        self.assertIn("gs/demo/01", self.integration("branch", "--list", "gs/demo/01"))
        self.assertIn(f"남긴 worktree: {wt} (미커밋 변경)", self.final_report())
        self.assertEqual(self.go("--only", "01")[0], 0)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [str(wt)])
        self.assertEqual(self.calls(), ["01"])
        (wt / "pending.txt").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].kept_worktrees, [])

    def test_resume_cleans_after_merge_before_cleanup(self):
        with mock.patch("gs.go._cleanup_merged", side_effect=RuntimeError("gs interrupted")):
            with self.assertRaisesRegex(RuntimeError, "gs interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertTrue((self.rundir / "wt/01").exists())
        # 이번 --only 범위 밖에 있는 merged 티켓도 시작할 때 회수한다.
        self.add_ticket("11")
        code, out, err = self.go("--only", "11")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertIn("[01] worktree 정리:", out)
        self.assertEqual(self.calls(), ["01", "11"])

    def test_resume_cleans_merge_not_yet_saved_in_state(self):
        from gs.go import _set as real_set

        def interrupted(r, tid, **fields):
            if fields.get("status") == state.MERGED:
                raise RuntimeError("gs interrupted before state save")
            return real_set(r, tid, **fields)

        with mock.patch("gs.go._set", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "running")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertEqual(self.calls(), ["01"])

    def test_cleanup_keeps_branch_with_unmerged_tip(self):
        with mock.patch("gs.go._cleanup_merged"):
            self.assertEqual(self.go("--only", "01")[0], 0)
        wt = self.rundir / "wt/01"
        (wt / "extra").write_text("unmerged")
        sh(wt, "git", "add", "extra")
        sh(wt, "git", "commit", "-qm", "unmerged tip")
        tip = sh(wt, "git", "rev-parse", "HEAD")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("브랜치 끝이 integration에 포함되지 않아 남긴다: gs/demo/01", out)
        self.assertFalse(wt.exists())
        self.assertEqual(self.integration("rev-parse", "gs/demo/01"), tip)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")

    def cleanup_failure(self, operation):
        from gs import git
        real_run = git.run
        wt = self.rundir / "wt/01"

        def fail_remove(repo, *args, **kwargs):
            if args == ("worktree", "remove", str(wt)) and operation == "worktree":
                raise git.GitError("cannot remove worktree")
            if args == ("branch", "-D", "gs/demo/01") and operation == "branch":
                raise OSError("cannot remove branch")
            return real_run(repo, *args, **kwargs)

        with mock.patch("gs.git.run", side_effect=fail_remove):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertIn("경고: worktree·브랜치 정리 실패:", out)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertEqual(wt.exists(), operation == "worktree")
        self.assertIn("gs/demo/01", self.integration("branch", "--list", "gs/demo/01"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assert_ticket_cleaned("01")
        self.assertEqual(self.calls(), ["01"])

    def test_worktree_cleanup_failure_only_warns_and_resumes(self):
        self.cleanup_failure("worktree")

    def test_branch_cleanup_failure_only_warns_and_resumes(self):
        self.cleanup_failure("branch")

    def test_finish_merges_and_verifies_main_in_temporary_worktree(self):
        initial = self.integration("rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertTrue(f["integration_ok"] and f["main_ok"])
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(self.integration("rev-parse", "main"), initial)  # 호출 worktree는 움직이지 않는다
        self.assertEqual(len(self.integration("rev-list", "--parents", "-n", "1", f["merge_sha"]).split()), 3)
        self.assertEqual(self.integration("show", "origin/main:file_01"), "01 worker")
        report = self.final_report()
        for text in ("## Summary", "## Evidence", "## Merge Danger", "| 01 | t01 | merged |",
                     "main-verify.log", "종료 코드: 0", 'git -C "$dir" revert', "mktemp -d", f["merge_sha"]):
            self.assertIn(text, report)
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), report)
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])
        self.assertNotIn("gs-main-", self.integration("worktree", "list"))
        self.assertEqual(len(out.strip().splitlines()[-4:]), 4)
        self.assertTrue(out.strip().splitlines()[-4].startswith("■ 요약:"))
        self.assertIn("-p --model opus", (self.bin / "judge.calls").read_text())
        self.assertIn("report-input.md", (self.bin / "judge.input").read_text())
        self.assertNotIn("01 worker", (self.bin / "judge.input").read_text())
        merges = self.lines("gh.log").count(next(x for x in self.lines("gh.log") if x.startswith("pr merge ")))
        self.assertEqual(self.go("--only", "01")[0], 0)  # 결과 보고서만 새 PR로 병합하지 않는다
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), merges)

    def test_finish_main_failure_pushes_revert_and_records_it(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertTrue(f["integration_ok"])
        self.assertFalse(f["main_ok"])
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        self.assertIn(f["revert_sha"], self.final_report())
        self.assertIn("종료 코드: 1", self.final_report())
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())
        self.assertIn("revert", out)
        self.assertEqual(self.go("--only", "01")[0], 1)  # 같은 병합을 두 번 revert하지 않는다
        self.assertEqual(self.under_report(), f["revert_sha"])

    def test_finish_no_merged_ticket_keeps_report_pr_without_merging(self):
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "02,03")
        self.assertEqual(code, 1, out + err)
        self.assertFalse(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        self.assertIn("merged 티켓 없음", self.final_report())
        self.assertIn("| 02 | t02 | failed | worker 종료 코드 1 |", self.final_report())
        self.assertIn("| 03 | t03 | skipped | 막힘: 02 |", self.final_report())
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())

    def test_finish_skips_verify_when_only_report_changed(self):
        self.parallel(1, verify='test ! -f .goldstack/work/demo/report.md || test "${PWD##*/}" = base')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertTrue(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertIn("integration-final: 보고서만 바뀜, 건너뜀", self.final_report())
        self.assertIn("integration-final-verify.log", self.final_report())

    def test_finish_merge_queue_is_not_success_and_resume_rechecks_pr(self):
        (self.bin / "gh.queue").touch()
        initial = sh(self.remote, "git", "rev-parse", "main")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        log = self.lines("gh.log")
        ix = next(i for i, line in enumerate(log) if line.startswith("pr merge "))
        self.assertTrue(log[ix + 1].startswith("pr view "))
        self.assertFalse((self.rundir / "finish/main-verify.log").exists())
        (self.bin / "gh.queue").unlink()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])

    def test_finish_resumes_after_merge_before_main_verify(self):
        with mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)
        self.assertEqual(self.calls(), ["01"])

    def test_finish_checks_actual_merge_even_if_command_returns_error(self):
        (self.bin / "gh.badexit").touch()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertTrue((self.rundir / "finish/main-verify.log").exists())

    def test_finish_resumes_revert_push_without_another_revert(self):
        from gs import git
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        real_run = git.run

        def run(cwd, *args, **kw):
            if args == ("push", "origin", "HEAD:refs/heads/main"):
                raise git.GitError("push interrupted")
            return real_run(cwd, *args, **kw)

        with mock.patch("gs.git.run", side_effect=run):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "main_failed")
        revert = f["revert_sha"]
        self.assertNotEqual(sh(self.remote, "git", "rev-parse", "main"), revert)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.under_report(), revert)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "reverted")

    def test_finish_updates_existing_open_pr(self):
        for _ in range(2):
            code, out, err = self.go("--only", "06")
            self.assertEqual(code, 1, out + err)
        self.assertEqual(sum(x.startswith("pr create ") for x in self.lines("gh.log")), 1)
        self.assertEqual((self.bin / "pr-body.md").read_text().strip(), self.final_report())

    # --- 08 리뷰(claude) 반영 ---
    def break_main(self, advance=False):
        """main 검증(분리 HEAD)에서 file_01이 있으면 실패하는 verify. advance면 첫 main 검증 도중 다른 사람이 main에 push한다."""
        (self.bin / "advance.sh").write_text(textwrap.dedent(f"""\
            here="$(dirname "$0")"
            [ -f "$here/advanced" ] && exit 0
            touch "$here/advanced"
            git clone -q {self.remote} "$here/other" && cd "$here/other" && echo other > other.txt \\
              && git add other.txt && git commit -qm "someone else" && git push -q origin main
            """))
        (self.bin / "verify.sh").write_text(textwrap.dedent(f"""\
            git symbolic-ref -q HEAD >/dev/null && exit 0  # integration(브랜치)은 통과
            test -f file_01 || exit 0
            {'bash "$(dirname "$0")/advance.sh"' if advance else ':'}
            exit 1
            """))
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")

    def someone(self, *script):
        """다른 사람이 원격 main에서 한 일."""
        other = self.bin / "human"
        if not other.exists():
            sh(self.bin, "git", "clone", "-q", str(self.remote), str(other))
        sh(other, "git", "pull", "-q", "--ff-only", "origin", "main")
        sh(other, "bash", "-c", "; ".join(script) + "; git push -q origin main")
        return sh(other, "git", "rev-parse", "HEAD")

    def remote_files(self):
        return sh(self.remote, "git", "ls-tree", "--name-only", "main").split()

    def test_finish_rebuilds_rejected_revert_on_latest_main(self):  # high: 거부된 revert push가 영구히 막힘
        self.break_main(advance=True)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "main_failed")
        stale, moved = f["revert_sha"], sh(self.remote, "git", "rev-parse", "main")
        self.assertEqual(sh(self.remote, "git", "log", "-1", "--format=%s", "main"), "someone else")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", f)
        self.assertNotEqual(f["revert_sha"], stale)
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), moved)  # force 없이 최신 main 위에
        self.assertNotIn("file_01", self.remote_files())
        self.assertIn("other.txt", self.remote_files())
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), 1)

    def test_finish_records_revert_already_done_by_someone(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = state.load(self.rundir, "demo").finish
        theirs = self.someone(f"git revert --no-edit -m 1 {f['merge_sha']}")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", f)
        self.assertEqual(f["revert_sha"], theirs)
        self.assertEqual(self.under_report(), theirs)  # gs는 다시 revert하지 않는다(보고서 커밋만 위에)
        self.assertIn("이미", f["outcome"])

    def test_finish_moves_on_when_someone_fixed_main(self):
        self.break_main(advance=True)
        self.assertEqual(self.go("--only", "01")[0], 1)
        fixed = self.someone("git rm -q file_01", "git commit -qm 'fix main'")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified", f)
        self.assertTrue(f["main_ok"])
        self.assertNotIn("revert_sha", f)
        self.assertEqual(self.under_report(), fixed)

    def test_finish_revert_keeps_feature_code_in_integration(self):  # medium: revert 뒤 integration에서 코드가 사라짐
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        self.assertEqual(self.go("--only", "01")[0], 1)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        [again] = f["reintroduced"]
        self.assertEqual(again["revert"], f["revert_sha"])
        self.assertIn(f"This reverts commit {f['revert_sha']}",
                      self.integration("log", "-1", "--format=%B", again["commit"]))
        self.assertIn(again["commit"], self.final_report())
        self.assertEqual(self.go("--only", "01")[0], 1)  # 다시 돌아도 코드가 남고 revert의 revert를 또 만들지 않는다
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        self.assertEqual(len(state.load(self.rundir, "demo").finish["reintroduced"]), 1)

    def test_prepare_keeps_feature_code_after_main_reverted(self):  # medium: 일반 준비 경로도 같은 방식으로 잃지 않는다
        self.assertEqual(self.go("--only", "01")[0], 0)
        merge = state.load(self.rundir, "demo").finish["merge_sha"]
        # 위에 gs의 최종 보고서 커밋이 있어 report.md가 충돌한다. 보고서의 되돌리는 법대로 지금 보고서를 남긴다.
        self.assertIn("revert --continue --no-edit", self.final_report())
        self.someone(f"! git revert --no-edit -m 1 {merge}",
                     "git checkout HEAD -- .goldstack/work/demo/report.md", "git revert --continue --no-edit")
        self.assertNotIn("file_01", self.remote_files())
        self.add_ticket("09")
        code, out, err = self.go("--only", "09")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.integration("show", "gs/demo/integration:file_01"), "01 worker")
        self.assertIn("file_01", self.remote_files())  # 다음 PR이 feature 코드를 다시 들였다
        self.assertIn("file_09", self.remote_files())
        self.assertIn("되돌렸", self.final_report())

    def test_finish_closed_pr_is_recorded_and_next_go_opens_new_pr(self):  # medium: 닫힌 PR에 영구히 갇힘
        (self.bin / "gh.queue").touch()
        self.assertEqual(self.go("--only", "01")[0], 1)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merge_pending")
        (self.bin / "gh.queue").unlink()
        (self.bin / "gh.open").unlink()
        (self.bin / "gh.closed").touch()  # 사람이 PR을 닫았다
        merges = sum(x.startswith("pr merge ") for x in self.lines("gh.log"))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "closed", f)
        self.assertEqual(sum(x.startswith("pr merge ") for x in self.lines("gh.log")), merges)
        self.assertIn("닫혔다", self.final_report())
        self.assertIn("닫혔다", out)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(sum(x.startswith("pr create ") for x in self.lines("gh.log")), 2)
        self.assertIn("file_01", self.remote_files())
        self.assertIn("닫혔다", self.final_report())  # 이전 PR이 닫혔다는 기록을 새 PR에도 남긴다
        self.assertEqual(self.calls(), ["01"])

    def test_report_body_stays_below_github_limit(self):  # medium: 본문 길이 초과로 마무리가 반복 실패
        self.parallel(1, verify="head -c 100000 /dev/zero | tr '\\0' x; echo; echo LAST-LINE; test ! -f BROKEN")
        old = self.rundir / "01" / "1" / "verify.log"
        old.parent.mkdir(parents=True)
        old.write_text("OLD-ATTEMPT\n" + "y" * 100000)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        body = (self.bin / "pr-body.md").read_text()
        self.assertLess(len(body), 65536)
        self.assertEqual(body.strip(), self.final_report())
        self.assertNotIn("OLD-ATTEMPT", body)  # 지난 시도 로그는 붙이지 않는다
        self.assertIn("LAST-LINE", body)  # 로그의 끝을 남긴다
        self.assertIn(str((self.rundir / "finish" / "main-verify.log").resolve()), body)  # 전체 로그 경로

    # --- 다른 계열 리뷰와 수정 1회(06) ---
    def review_with(self, findings):
        """가짜 reviewer가 낼 지적과 가짜 판단 모델(FIX가 claim에 있으면 fix)을 건다."""
        (self.bin / "findings.json").write_text(json.dumps({"findings": findings}, ensure_ascii=False))
        (self.bin / "judge").write_text("#!/bin/bash\n" + FAKE_REVIEW_JUDGE)
        return mock.patch.dict(os.environ, {"PY": sys.executable})

    def review_state(self, tid="01"):
        return state.load(self.rundir, "demo").tickets[tid].review

    def lines(self, name):
        p = self.bin / name
        return p.read_text().splitlines() if p.exists() else []

    def test_review_fix_once_then_merge(self):
        self.assertEqual(self.go("--only", "01")[0], 0)  # 01이 먼저 integration에 있다: diff는 04만이어야 한다
        with self.review_with([
            {"severity": "high", "location": "file_04:1", "claim": "FIX: 값이 틀렸다", "evidence": "cat file_04 → 04"},
            {"severity": "low", "location": "file_04", "claim": "FIX 이름이 마음에 안 든다", "evidence": ""},
            {"severity": "medium", "location": "file_04", "claim": "설명 문서가 없다", "evidence": "티켓 완료 조건"},
        ]):
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "04", "04"])  # 구현 worker, 수정 worker 한 번
        self.assertEqual(self.lines("fix.log"), ["fix 04"])
        self.assertEqual(self.lines("review.calls"), ["codex", "codex", "codex"])  # 01·04 한 번씩, 04 수정 뒤 재리뷰
        self.assertEqual(self.merged(), ["01", "04"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("fixed_04", files)  # 수정 커밋이 병합에 들어갔다
        self.assertIn("수정 worker 시작: 지적 1개", out)
        self.assertIn("[04] 검증 통과", out)
        self.assertTrue((self.rundir / "04/1/fix/verify.log").exists())  # 재리뷰 뒤 verify

        # reviewer에게는 merge-base 기준 그 티켓 diff와 티켓·spec 경로를 줬다
        diff = (self.bin / "review.diff").read_text()
        self.assertIn("file_04", diff)
        self.assertNotIn("file_01", diff)
        prompt = (self.bin / "review.prompt").read_text()
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/tickets/04-t.md"), prompt)
        self.assertIn(str(self.repo.resolve() / ".goldstack/work/demo/spec.md"), prompt)
        # 판단 모델은 새 claude -p(Opus)이고 파일 경로만 받는다
        self.assertIn("-p --model opus", (self.bin / "judge.calls").read_text())
        self.assertNotIn("값이 틀렸다", (self.bin / "judge.input").read_text())

        rec = self.review_state("04")
        self.assertEqual([(f["action"], f["fix_attempt"]) for f in rec["findings"]],
                         [("fix", review.ATTEMPTED), ("report", ""), ("report", "")])  # 근거 없는 지적은 report
        self.assertIn("근거 없음", rec["findings"][1]["why"])
        # 가짜 reviewer의 재리뷰 답은 형식이 틀렸다. 수정을 시도한 fix 지적도 고쳐졌다고 치지 않고 남긴다
        self.assertEqual([f["claim"] for f in review.remaining(rec)],
                         ["FIX: 값이 틀렸다", "FIX 이름이 마음에 안 든다", "설명 문서가 없다"])
        self.assertEqual((rec["findings"][0]["rereview"], rec["findings"][0]["rereview_reason"]),
                         (review.UNCHECKED, review.REASON_FAILED))
        brief = (self.rundir / "04/1/fix/brief.md").read_text()
        self.assertIn("FIX: 값이 틀렸다", brief)
        self.assertNotIn("마음에 안 든다", brief)
        self.assertIn("남은 리뷰 지적 3", out)

    def test_fix_findings_stay_in_report_when_rereview_unchecked(self):
        # 리뷰 #2: 수정 worker가 지적 A만 고치고 B는 거절해도 커밋·종료 코드만으로는 알 수 없다.
        # 재리뷰가 확인하지 못했으면 둘 다 unchecked로 남은 지적에 들어가 보고서에 나와야 한다.
        with self.review_with([
            {"severity": "high", "location": "file_01", "claim": "FIX A: 값이 틀렸다", "evidence": "e1"},
            {"severity": "medium", "location": "file_01", "claim": "FIX B: 경계값 누락", "evidence": "e2"},
        ]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines("fix.log"), ["fix 01"])
        rec = self.review_state()
        self.assertEqual([f["claim"] for f in review.remaining(rec)], ["FIX A: 값이 틀렸다", "FIX B: 경계값 누락"])
        self.assertEqual([f["rereview"] for f in rec["findings"]], [review.UNCHECKED, review.UNCHECKED])
        report = self.final_report()
        self.assertIn("FIX A: 값이 틀렸다", report)
        self.assertIn("FIX B: 경계값 누락", report)
        self.assertIn("남은 리뷰 지적 2", out)
        self.assertEqual([f["fix_attempt"] for f in rec["findings"]], [review.ATTEMPTED, review.ATTEMPTED])

    def test_malformed_judge_output_is_isolated_to_ticket(self):
        # 리뷰 #3: 판단 모델이 형식이 틀린 JSON을 내도 코디네이터가 죽지 않는다. 리뷰 실패처럼 모두 report로 두고 병합한다
        (self.bin / "findings.json").write_text(json.dumps({"findings": [
            {"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]}))
        (self.bin / "judge").write_text('#!/bin/bash\ncat > /dev/null\necho \'{"decisions":[{"id":[],"action":"fix"}]}\'\n')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01"])
        self.assertEqual(self.lines("fix.log"), [])
        rec = self.review_state()
        self.assertIn("판단 모델 호출 불가", rec["note"])
        self.assertEqual([f["action"] for f in rec["findings"]], ["report"])

    def test_unexpected_review_error_is_isolated_to_ticket(self):
        # 리뷰 #3: 리뷰 단계의 예상 못 한 예외도 코디네이터를 죽이지 않는다. 리뷰 실패로 적고 verify로 병합한다
        with mock.patch.object(review, "run", side_effect=RuntimeError("뜻밖의 오류")):
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.merged(), ["01", "04"])
        rec = self.review_state()
        self.assertIn("리뷰 실패", rec["note"])
        self.assertIn("뜻밖의 오류", rec["note"])
        self.assertIn("뜻밖의 오류", self.final_report())

    def test_timed_out_fix_worker_that_touched_integration_is_stopped(self):
        # 리뷰 #4: 수정 worker가 integration을 바꾼 뒤 멈춰 시간 초과되면, 실패 처리 전에 그 worker를 끝내야 한다.
        # 끝내지 않으면 재시도 worker와 함께 살아 남아 계속 바꿀 수 있다.
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
              echo "fix $GS_TICKET" >> "$here/fix.log"
              if [ ! -f "$here/fix.first" ]; then
                touch "$here/fix.first"
                echo $$ > "$here/fix.pid"
                echo x > "$GS_WORKTREE/../integration/evil"
                sleep 30
                exit 1
              fi
              echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
            fi
            echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
        '''))
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]), \
                mock.patch("gs.go._idle_seconds", return_value=0.4), mock.patch.object(worker, "POLL_SECONDS", 0.05):
            code, out, err = self.go("--only", "01")
        pid = int((self.bin / "fix.pid").read_text())
        self.addCleanup(kill_quietly, pid)
        self.assertEqual(code, 0, out + err)
        self.assertIn("integration worktree를 바꿨다", out)
        self.assertEqual(self.lines("fix.log"), ["fix 01", "fix 01"])
        self.assertFalse(alive(pid), "시간 초과된 수정 worker가 살아 있다")

    def test_review_report_only_merges_directly(self):
        with self.review_with([{"severity": "low", "location": "file_01", "claim": "변수 이름이 짧다",
                                "evidence": "file_01 첫 줄"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])  # 수정 worker 없음
        self.assertEqual(self.lines("fix.log"), [])
        self.assertEqual(self.merged(), ["01"])
        self.assertFalse((self.rundir / "01/1/fix").exists())
        rec = self.review_state()
        self.assertEqual(rec["reviewer"], "codex")
        self.assertEqual([(f["severity"], f["action"]) for f in rec["findings"]], [("low", "report")])
        self.assertEqual(len(review.remaining(rec)), 1)

    def test_same_family_reviewer_is_refused(self):
        (self.repo / ".goldstack/work/demo/tickets/10-t.md").write_text(ticket("10").replace("reviewer: codex", "reviewer: claude"))
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "same family")
        sh(self.repo, "git", "push", "-q", "origin", "main")
        code, out, err = self.go("--only", "10")
        self.assertEqual(code, 1)
        self.assertIn("리뷰는 다른 계열이어야 한다", err)
        self.assertIn("아무것도 띄우지 않았다", err)
        self.assertEqual((self.calls(), self.lines("review.calls")), ([], []))
        # 리뷰 단계 자체도 같은 계열이면 reviewer를 부르지 않고 거부한다
        with self.assertRaisesRegex(review.Refused, "같은 계열"):
            review.run(repo=self.repo, worktree=self.repo, rdir=self.rundir / "x", base="main", branch="main",
                       ticket=Path("t"), spec=Path("s"), model="claude", reviewer="claude",
                       cfg=config.load(self.repo)[0])
        self.assertEqual(self.lines("review.calls"), [])

    def test_failed_fix_is_discarded_and_reviewed_work_merged(self):
        (self.bin / "fixfail").touch()
        with self.review_with([{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "01"])
        files = self.integration("ls-tree", "--name-only", "gs/demo/integration").split()
        self.assertIn("file_01", files)
        self.assertNotIn("badfix_01", files)  # 실패한 수정은 버렸다
        rec = self.review_state()
        self.assertIn("수정 worker 실패(종료 코드 3)", rec["fix"])
        self.assertEqual(len(review.remaining(rec)), 1)  # 고치지 못한 fix 지적이 남는다
        self.assertEqual(self.lines("review.calls"), ["codex"])  # 버린 수정은 재리뷰하지 않는다
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].failures, 0)  # 티켓 실패로 세지 않는다

    def test_reviewer_failure_is_recorded_and_ticket_still_merges(self):
        with mock.patch.dict(os.environ, {"GS_REVIEWER_CMD": "echo 'not json'"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01"])
        self.assertIn("리뷰 없음", self.review_state()["note"])
        self.assertIn("리뷰 실패", self.review_state()["note"])
        self.assertIn("리뷰 실패", self.final_report())  # 리뷰 없이 병합했다는 사실이 보고서에 나온다

    # --- 실패·멈춤과 재시도(07) ---
    def timeout_retry(self, runner):
        script = self.bin / "worker.sh"
        script.write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if [ "$GS_TICKET" = 04 ]; then
              echo done > file_04; git add file_04; git commit -qm done; exit $?
            fi
            if [ ! -f "$here/first" ]; then
              touch "$here/first"
              echo $$ > "$here/old.pid"
              echo 'first attempt stuck'
              echo 'keep this evidence' > debug.txt
              sleep 20
              exit 1
            fi
            grep -q '판단 모델의 실패 요약' "$GS_BRIEF" || exit 9
            grep -q '시간 초과' "$GS_BRIEF" || exit 10
            test ! -e debug.txt || exit 11
            echo recovered > file_01
            git add file_01 && git commit -qm recovered
        '''))
        env = {"GS_RUNNER": runner}
        if runner == "herdr":
            path = self.bin / "herdr"
            path.write_text("#!/bin/bash\n" + FAKE_HERDR)
            path.chmod(0o755)
            env.update(HERDR_BIN_PATH=str(path), HERDR_SESSION="t", HERDR_WORKSPACE_ID="w1")
        with mock.patch.dict(os.environ, env), mock.patch("gs.go._idle_seconds", return_value=0.4), \
                mock.patch.object(worker, "POLL_SECONDS", 0.05), \
                mock.patch.object(adapters, "for_model", wraps=adapters.for_model) as choose:
            code, out, err = self.go("--only", "01,04")
        self.assertEqual(code, 0, out + err)
        self.assertEqual([c.args[0] for c in choose.call_args_list], ["claude", "claude", "claude"])
        self.assertEqual(self.calls(), ["01", "01", "04"])
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        old = self.rundir / "wt/01"
        self.assertEqual(ts.failed_worktrees, [str(old)])
        self.assertEqual((old / "debug.txt").read_text(), "keep this evidence\n")
        self.assertEqual(ts.worktree, str(self.rundir / "wt/01-retry-1"))
        self.assert_ticket_cleaned("01", "-retry-1")
        self.assertIn("gs/demo/01", self.integration("branch", "--list", "gs/demo/01"))
        self.assertIn("first attempt stuck", (self.rundir / "01/1/failure.log").read_text())
        self.assertIn("시간 초과", out)
        self.assertIn("-p --model opus", (self.bin / "judge.calls").read_text())
        # 판단 모델에는 로그 내용이 아닌 경로만 준다.
        prompt = (self.bin / "failure-judge.input").read_text()
        self.assertNotIn("first attempt stuck", prompt)
        self.assertEqual(Path(prompt.splitlines()[-1]), self.rundir / "01/1/failure.log")
        if runner == "herdr":
            cmds = (self.bin / "herdr.log").read_text().splitlines()
            self.assertIn("pane close w1:p1", cmds)  # 유휴 시간 초과는 실패 pane도 닫는다
            self.assertEqual(sum(c.startswith("pane close") for c in cmds), 3)
        self.assertFalse(alive(int((self.bin / "old.pid").read_text())))

    def test_idle_timeout_retries_successfully(self):
        self.timeout_retry("subprocess")

    def test_idle_timeout_terminates_process_and_herdr_pane(self):
        self.timeout_retry("herdr")

    def test_output_or_commits_reset_idle_timeout(self):
        # 각각 전체 실행 시간은 유휴 제한보다 길지만, 출력 또는 커밋이 계속 생긴다.
        for mode in ("output", "commits"):
            with self.subTest(mode=mode):
                tid = "17" if mode == "output" else "18"
                self.add_ticket(tid)
                (self.bin / "worker.sh").write_text(textwrap.dedent(f'''\
                    for i in 1 2 3 4 5 6; do
                      sleep 0.15
                      if [ '{mode}' = 'output' ]; then echo "working $i";
                      else echo "$i" > file_$GS_TICKET; git add -A; git commit -qm "step $i"; fi
                    done
                    echo done > file_$GS_TICKET; git add -A; git commit -qm done
                '''))
                with mock.patch("gs.go._idle_seconds", return_value=0.4):
                    code, out, err = self.go("--only", tid)
                self.assertEqual(code, 0, out + err)
                self.assertEqual(state.load(self.rundir, "demo").tickets[tid].attempts, 1)
                self.assertNotIn("시간 초과", out)

    def test_twice_failed_skips_transitive_dependents_only(self):
        self.add_ticket("11")
        (self.repo / ".goldstack/work/demo/tickets/09-t.md").write_text(ticket("09", '["03"]'))
        self.parallel(3)
        code, out, err = self.go("--only", "02,03,09,11")
        self.assertEqual(code, 1, out + err)
        st = state.load(self.rundir, "demo").tickets
        self.assertEqual({tid: ts.status for tid, ts in st.items()},
                         {"02": "failed", "03": "skipped", "09": "skipped", "11": "merged"})
        self.assertEqual(sorted(self.calls()), ["02", "02", "11"])
        self.assertEqual((st["02"].attempts, st["02"].failures), (2, 2))
        self.assertEqual(len(st["02"].failed_worktrees), 2)
        for wt in st["02"].failed_worktrees:
            self.assertTrue(Path(wt).is_dir())
        self.assertEqual(st["03"].attempts, 0)
        self.assertEqual(st["09"].attempts, 0)
        self.assertEqual(self.merged(), ["11"])

    def _fail_once_then_succeed(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            if [ ! -f "$here/first" ]; then touch "$here/first"; exit 1; fi
            echo done > file_01; git add -A; git commit -qm done
        '''))

    def test_repending_after_lost_integration_resets_failures(self):  # 07 리뷰(claude) 지적: 중간
        # 지난 실행: 01이 한 번 실패한 뒤 병합됐다(state merged, failures=1). 그 PR·integration은 버려졌다.
        self.rundir.mkdir(parents=True, exist_ok=True)
        st = state.load(self.rundir, "demo")
        ts = st.ticket("01")
        ts.status, ts.failures, ts.failure_summary = "merged", 1, ""
        state.save(self.rundir, st)
        self._fail_once_then_succeed()
        code, out, err = self.go("--only", "01")
        self.assertIn("integration에 표시가 없다", out)
        self.assertEqual(code, 0, out + err)  # 첫 실패에서 바로 failed가 되지 않고 재시도한다
        self.assertIn("한 번 재시도", out)

    def test_start_error_does_not_overwrite_previous_failure_evidence(self):  # 07 리뷰(claude) 지적: 낮음
        (self.bin / "worker.sh").write_text("exit 1\n")
        from gs import go as gomod
        real, calls = gomod.git.branch_exists, []

        def flaky(*a, **kw):
            calls.append(a)
            if any("retry" in str(x) for x in a):
                raise OSError("boom at retry start")
            return real(*a, **kw)
        with mock.patch.object(gomod.git, "branch_exists", side_effect=flaky):
            self.go("--only", "01")
        first = self.rundir / "01" / "1" / "failure.log"
        self.assertIn("종료 코드", first.read_text())
        self.assertNotIn("boom at retry start", first.read_text())

    def test_verify_failure_retries_in_fresh_worktree(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            if [ ! -f "$here/first" ]; then
              touch "$here/first" BROKEN
            else
              test ! -e BROKEN || exit 8
              grep -q '검증 실패' "$GS_BRIEF" || exit 9
            fi
            echo done > file_01; git add -A; git commit -qm done
        '''))
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts), ("merged", 2))
        self.assertTrue((self.rundir / "01/1/verify.log").exists())
        self.assertTrue((self.rundir / "01/2/verify.log").exists())
        self.assertTrue((self.rundir / "wt/01/BROKEN").exists())
        self.assertNotIn("BROKEN", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())

    def test_judge_failure_still_retries_with_evidence_path(self):
        with mock.patch.dict(os.environ, {"GS_JUDGE": "/does/not/exist"}):
            code, out, err = self.go("--only", "06")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual(ts.attempts, 2)
        brief = (self.rundir / "06/2/brief.md").read_text()
        self.assertIn("실패 요약 호출 불가", brief)
        self.assertIn(str(self.rundir / "06/1/failure.log"), brief)

    def test_resume_after_first_failure_keeps_retry_limit(self):
        from gs.go import _start as real_start

        def start(r, t, runner):
            if r.st.ticket(t.id).failures:
                raise RuntimeError("coordinator interrupted before retry")
            return real_start(r, t, runner)

        with mock.patch("gs.go._start", side_effect=start):
            with self.assertRaisesRegex(RuntimeError, "coordinator interrupted"):
                self.go("--only", "06")
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual((ts.status, ts.failures), ("pending", 1))
        code, out, err = self.go("--only", "06")
        self.assertEqual(code, 1, out + err)
        ts = state.load(self.rundir, "demo").tickets["06"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("failed", 2, 2))
        self.assertEqual(self.calls(), ["06", "06"])
        self.assertIn("판단 모델의 실패 요약", (self.rundir / "06/2/brief.md").read_text())

    # --- verify 시간 제한(v1 01): GS_VERIFY_TIMEOUT=1초 ---
    def hang_verify(self, stage):
        """stage(ticket: 병합 전, integration: 마무리 integration, main: main 검증)에서만 멈추는 verify.
        멈출 때 자식을 백그라운드로 띄우고 그 pid를 bin/bg_<n>에 적는다. 나머지는 `test ! -f BROKEN`."""
        (self.bin / "verify.sh").write_text(textwrap.dedent(f"""\
            here="{self.bin}"
            if git rev-parse -q --verify MERGE_HEAD >/dev/null; then now=ticket
            elif git symbolic-ref -q HEAD >/dev/null; then now=integration
            else now=main; fi
            hang=no
            case "$now" in
              ticket) [ -f HANG ] && hang=yes ;;
              integration) [ {stage} = integration ] && hang=yes ;;
              main) [ {stage} = main ] && [ -f file_01 ] && hang=yes ;;
            esac
            if [ $hang = yes ]; then
              n=$(ls "$here" | grep -c '^bg_')
              sleep 300 & echo $! > "$here/bg_$n"
              echo "hanging in $now"; sleep 300
            fi
            test ! -f BROKEN
            """))
        self.parallel(1, verify=f"bash {self.bin / 'verify.sh'}")

    def assert_children_dead(self):
        pids = [int(p.read_text()) for p in sorted(self.bin.glob("bg_*"))]
        self.assertTrue(pids)
        for pid in pids:
            for _ in range(60):  # 고아는 init이 거둔다
                if not alive(pid):
                    break
                time.sleep(0.05)
            self.assertFalse(alive(pid), f"verify의 백그라운드 자식 {pid}가 살아 있다")

    def test_ticket_verify_timeout_retries_with_same_model(self):
        self.hang_verify("ticket")
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if [ ! -f "$here/first" ]; then
              touch "$here/first"; echo x > HANG  # 첫 시도: verify가 멈춘다
            else
              grep -q '검증 시간 초과' "$GS_BRIEF" || exit 9
            fi
            echo done > file_01; git add -A; git commit -qm done
        '''))
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        ts = state.load(self.rundir, "demo").tickets["01"]
        self.assertEqual((ts.status, ts.attempts, ts.failures), ("merged", 2, 1))
        self.assertEqual(self.calls(), ["01", "01"])
        log = self.rundir / "01/1/verify.log"
        self.assertIn(f"[01] 실패: 검증 시간 초과(0.02분, 로그 {log})", out)
        self.assertIn("같은 모델(claude)로", out)
        self.assertTrue(log.read_text().endswith("\n시간 초과: 0.02분\n"))
        self.assertIn("검증 시간 초과(0.02분", (self.rundir / "01/1/failure.log").read_text())
        self.assertNotIn("시간 초과", (self.rundir / "01/2/verify.log").read_text())
        self.assertNotIn("HANG", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assert_children_dead()

    def test_integration_verify_timeout_does_not_merge(self):
        self.hang_verify("integration")
        initial = sh(self.remote, "git", "rev-parse", "main")
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual((f["phase"], f["integration_ok"]), ("not_merged", False))
        self.assertEqual(state.load(self.rundir, "demo").tickets["01"].status, "merged")
        self.assertFalse(any(x.startswith("pr merge ") for x in self.lines("gh.log")))
        self.assertEqual(sh(self.remote, "git", "rev-parse", "main"), initial)
        log = (self.rundir / "finish/integration-verify.log").read_text()
        self.assertTrue(log.startswith(f"$ bash {self.bin / 'verify.sh'}\nHEAD: "), log)
        self.assertTrue(log.endswith("\n시간 초과: 0.02분\n"), log)
        self.assertFalse((self.rundir / "finish/integration-final-verify.log").exists())
        self.assertTrue(git_clean(self.rundir / "wt/integration"))
        self.assert_children_dead()

    def test_main_verify_timeout_reverts_merge(self):
        self.hang_verify("main")
        initial = sh(self.remote, "git", "rev-parse", "main")
        with mock.patch.dict(os.environ, {"GS_VERIFY_TIMEOUT": "1"}):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertTrue(f["integration_ok"])
        self.assertFalse(f["main_ok"])
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        log = (self.rundir / "finish/main-verify.log").read_text()
        self.assertTrue(log.endswith("\n시간 초과: 0.02분\n"), log)
        self.assertIn("시간 초과: 0.02분", self.final_report())
        self.assertEqual(list(self.rundir.glob("gs-main-*")), [])
        self.assert_children_dead()

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
        self.parallel(3, verify=f"touch {self.bin / 'verifying'}; test ! -f BROKEN && sleep 1")
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

    def push_blocked(self, remotes, expected_code=0):
        code, out, err = self.go("--only", "16")
        self.assertEqual(code, expected_code, out + err)
        if expected_code:
            self.assertIn("origin/main에 없다", err)  # 서로 다른 fetch/push 원격의 병합을 main 성공으로 보지 않는다
        self.assertTrue((self.bin / "fetch_16").exists(), out)  # fetch는 된다
        self.assertNotIn("pushed", (self.bin / "push_16").read_text())
        for remote in remotes:
            self.assertNotIn("leak", sh(remote, "git", "branch", "--list", "leak"))
        self.assertEqual((self.bin / "gh_16").read_text().strip(), worker.GH_BLOCKED)  # gh는 사용자 인증을 못 쓴다

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
        self.add_ticket("07")
        code, out, _ = self.go("--only", "01,07")
        self.assertEqual(code, 1)
        self.assertIn("[07] 실패: worker가 integration worktree를 바꿨다", out)
        self.assertNotIn("evil", self.integration("ls-tree", "--name-only", "gs/demo/integration").split())
        self.assertNotIn("evil", sh(self.remote, "git", "ls-tree", "--name-only", "main").split())

    def test_dirty_integration_is_cleaned_and_ticket_fails(self):  # 지적 3
        self.add_ticket("08")
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
        self.assertEqual(self.calls(), ["01", "02", "02", "04", "05", "05", "06", "06"])

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


class TrunkUpstreamTest(unittest.TestCase):
    """git.base·git.remote가 main·origin이 아닌 레포. origin 원격도 main 브랜치도 없으니 남은 가정은 바로 실패한다."""
    BASE, REMOTE = "trunk", "upstream"
    setUp, tearDown, go = GoTest.setUp, GoTest.tearDown, GoTest.go
    rundir, integration, parallel, lines, final_report = (GoTest.rundir, GoTest.integration, GoTest.parallel,
                                                          GoTest.lines, GoTest.final_report)
    under_report = GoTest.under_report

    def test_go_merges_and_verifies_on_configured_base_and_remote(self):
        initial = sh(self.remote, "git", "rev-parse", "trunk")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertTrue(f["integration_ok"] and f["main_ok"])
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['merge_sha']}^1"), initial)
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "main"), "")
        self.assertEqual(self.integration("remote"), "upstream")
        self.assertEqual(self.integration("show", "upstream/trunk:file_01"), "01 worker")
        self.assertEqual(sh(self.remote, "git", "branch", "--list", "gs/*"), "")
        gh = self.lines("gh.log")
        self.assertTrue(any(x.startswith("pr create --base trunk ") for x in gh), gh)
        self.assertTrue(any(x.startswith("pr list ") and "--base trunk" in x for x in gh), gh)
        report = self.final_report()
        for text in ("git fetch upstream trunk", 'git worktree add --detach "$dir" upstream/trunk',
                     'git -C "$dir" push upstream HEAD:refs/heads/trunk', "trunk verify: True"):
            self.assertIn(text, report)
        self.assertNotIn("origin", report)
        self.assertEqual(self.go("--only", "01")[0], 0)  # 재실행도 trunk·upstream으로 끝난다

    def test_base_failure_reverts_on_configured_base(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        initial = sh(self.remote, "git", "rev-parse", "trunk")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted", out + err)
        self.assertEqual(self.under_report(), f["revert_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^"), f["merge_sha"])
        self.assertEqual(sh(self.remote, "git", "rev-parse", f"{f['revert_sha']}^{{tree}}"),
                         sh(self.remote, "git", "rev-parse", f"{initial}^{{tree}}"))
        self.assertIn("trunk에 push함", f["outcome"])

    def test_require_committed_compares_with_configured_base(self):
        (self.repo / ".goldstack/work/demo/tickets/01-t.md").write_text(ticket("01") + "more\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1)
        self.assertIn(".goldstack/work/demo가 upstream/trunk와 다르다", err)


if __name__ == "__main__":
    unittest.main()
