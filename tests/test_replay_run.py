"""gs replay 실행: 가짜 worker·리뷰어·판단 모델로 임시 레포(bare 원격)에서 재생 한 번을 돌리고 결과 표 행을 본다."""
import contextlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config, replay
from support import alive, isolate_git_env, kill_quietly, sh

FEATURE, TID = "demo", "03"
WORK = f".goldstack/work/{FEATURE}"
TICKET = (f'---\nid: "{TID}"\ntitle: t{TID}\nblocked_by: []\nmodel: claude\nreviewer: codex\n'
          'touches: ["src/a.py"]\n---\n## 목표\n03 원래 목표\n')
WORKER = "claude:fable/high"

# 가짜 worker. 할 일은 bin/mode의 낱말로 고른다. cwd는 재생 worktree다.
FAKE_WORKER = r"""
here="$(dirname "$0")"
mode=" $(cat "$here/mode" 2>/dev/null) "
has() { case "$mode" in *" $1 "*) return 0 ;; esac; return 1; }
echo $$ > "$here/worker.pid"
printf '%s' "$GS_WORKER_TESTS" > "$here/worker_tests"
[ -f setup.out ] && touch "$here/setup_seen"
if has hang; then touch "$here/started"; for i in $(seq 1200); do sleep 0.05; done; exit 1; fi
if has result; then
  echo '{"type":"result","subtype":"success","result":"끝","total_cost_usd":4.1,"usage":{"input_tokens":120000,"cache_read_input_tokens":1500000,"cache_creation_input_tokens":300000,"output_tokens":40000}}'
fi
if has push; then git push -q origin HEAD:refs/heads/leak 2>"$here/push.err" && echo pushed >> "$here/push.err"; fi
if has edit-inputs; then
  echo "worker가 고친 티켓" >> .goldstack/work/demo/tickets/03-t.md
  echo "worker가 고친 spec" >> .goldstack/work/demo/spec.md
fi
if ! has none; then mkdir -p src; echo work > src/a.py; git add -A; git commit -qm work; fi
if has broken; then touch BROKEN; git add BROKEN; git commit -qm broken; fi
if has mutate; then touch MUTATE; git add MUTATE; git commit -qm mutate; fi
if has hangverify; then touch HANGV; git add HANGV; git commit -qm hangv; fi
if has move-base; then git update-ref refs/heads/main HEAD; git branch stray HEAD; fi
if has dirty; then echo left > left.txt; fi
if has exit1; then exit 1; fi
exit 0
"""

# 가짜 reviewer: 프롬프트가 가리키는 티켓·spec을 그때 복사해 두고, 지금 트리의 상태를 남긴다.
FAKE_REVIEWER = r"""
here="$(dirname "$0")"
echo "$GS_REVIEWER" >> "$here/review.calls"
cat > "$here/review.prompt"
cp "$(grep -o '/[^ `]*/03-t\.md' "$here/review.prompt" | head -n 1)" "$here/review.ticket"
cp "$(grep -o '/[^ `]*/spec\.md' "$here/review.prompt" | head -n 1)" "$here/review.spec"
pwd -P > "$here/review.cwd"
git status --porcelain --untracked-files=all > "$here/review.status"
if [ -f "$here/review.fail" ]; then echo '이건 JSON 답이 아니다'; exit 0; fi
if [ -f "$here/findings.json" ]; then cat "$here/findings.json"; else echo '{"findings": []}'; fi
"""

# 가짜 판단 모델: claim에 FIX가 있으면 fix. judge.fail이면 형식이 틀린 답을 낸다.
FAKE_JUDGE = r"""#!/bin/bash
here="$(dirname "$0")"
echo call >> "$here/judge.calls"
cat > "$here/judge.input"
if [ -f "$here/judge.fail" ]; then echo '분류 답이 아니다'; exit 0; fi
"%(py)s" - "$(grep -o '/[^ `]*findings.json' "$here/judge.input" | head -n 1)" <<'PYEOF'
import json, sys
fs = json.load(open(sys.argv[1]))["findings"]
print(json.dumps({"decisions": [{"id": f["id"], "action": "fix" if "FIX" in f["claim"] else "report", "why": "가짜"}
                                for f in fs]}))
PYEOF
"""


def finding(severity, claim):
    return {"severity": severity, "location": "src/a.py:1", "claim": claim, "evidence": "돌려 봤다"}


class ReplayRunTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.bin = root / "bin"
        self.bin.mkdir()
        for name in ("claude", "codex"):  # 진짜 CLI를 부르지 않는다
            (self.bin / name).write_text("#!/bin/sh\nexit 1\n")
            (self.bin / name).chmod(0o755)
        (self.bin / "worker.sh").write_text(FAKE_WORKER)
        (self.bin / "reviewer.sh").write_text(FAKE_REVIEWER)
        (self.bin / "judge").write_text(FAKE_JUDGE % {"py": sys.executable})
        (self.bin / "judge").chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "GS_WORKER_CMD": f"bash {self.bin / 'worker.sh'}",
            "GS_REVIEWER_CMD": f"bash {self.bin / 'reviewer.sh'}",
            "GS_JUDGE": str(self.bin / "judge"),
            "GS_RUNNER": "subprocess",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        env.start()
        self.addCleanup(env.stop)
        self.remote = root / "remote.git"
        sh(root, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.repo = root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        cfg = (config.DEFAULT_CONFIG.format(base='"main"').replace('setup = ""', 'setup = "echo prepared > setup.out"')
               + '\n[hook.worker_tests]\ndeny = ["replay-test-deny"]\n')
        verify = (f"test -f setup.out && test ! -f BROKEN && {{ test ! -f MUTATE || touch made-by-verify; }} && "
                  f"{{ test ! -f HANGV || {{ touch {self.bin}/verifying; sleep 30; }}; }}")
        self.write(config.CONFIG_PATH, cfg)
        self.write(".gitignore", ".goldstack/work/*/run/\n/setup.out\n")
        self.write(f"{WORK}/spec.md", f'---\nfeature: {FEATURE}\nverify: "{verify}"\n---\n# spec 원문\n')
        self.write(f"{WORK}/tickets/{TID}-t.md", TICKET)
        self.start = self.commit("seed")
        # gs go가 남기는 이력: 티켓 브랜치 → integration의 `Merge 03:` → base
        sh(self.repo, "git", "branch", f"gs/{FEATURE}/integration")
        sh(self.repo, "git", "checkout", "-q", "-b", f"gs/{FEATURE}/{TID}")
        self.write("src/a.py", "original\n")
        self.commit("original work")
        sh(self.repo, "git", "checkout", "-q", f"gs/{FEATURE}/integration")
        sh(self.repo, "git", "merge", "--no-ff", "-q", "-m", f"Merge {TID}: t{TID}\n\ngs-ticket: {FEATURE}/{TID}",
           f"gs/{FEATURE}/{TID}")
        sh(self.repo, "git", "checkout", "-q", "main")
        sh(self.repo, "git", "merge", "--no-ff", "-q", "-m", "Merge pull request #1", f"gs/{FEATURE}/integration")
        sh(self.repo, "git", "remote", "add", "origin", str(self.remote))
        sh(self.repo, "git", "push", "-q", "origin", "main", f"gs/{FEATURE}/integration")

    # --- 도우미 ---
    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", message)
        return sh(self.repo, "git", "rev-parse", "HEAD")

    def mode(self, *words):
        (self.bin / "mode").write_text(" ".join(words))

    def replay(self, *extra, worker=WORKER):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "replay", f"{FEATURE}/{TID}", "--worker", worker, *extra])
        return code, out.getvalue(), err.getvalue()

    def ok(self, *extra):
        code, out, err = self.replay(*extra)
        self.assertEqual(code, 0, out + err)
        return out

    @property
    def table(self):
        return self.repo / replay.TABLE_REL

    def rows(self):
        lines = self.table.read_text(encoding="utf-8").splitlines()
        return [dict(zip(replay.HEADER, (c.strip() for c in line.strip().strip("|").split(" | "))))
                for line in lines[2:]]

    def row(self):
        rows = self.rows()
        self.assertEqual(len(rows), 1, rows)
        return rows[0]

    def logdir(self, row):
        return self.repo / row["로그"]

    def heads(self, repo):
        return sh(repo, "git", "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads/")

    def assert_no_replay_worktrees(self):
        listed = sh(self.repo, "git", "worktree", "list", "--porcelain")
        self.assertEqual([line for line in listed.splitlines() if line.startswith("worktree ")],
                         [f"worktree {self.repo}"], listed)
        for path in (self.repo / WORK / "run" / "replay").glob("*/*"):
            self.assertNotIn(path.name, ("wt", "clean"), path)

    # --- 정상 행 ---
    def test_normal_run_appends_one_row_from_the_original_start_commit(self):
        heads = self.heads(self.repo)
        out = self.ok()
        self.assertIn(f"시작 commit: {self.start}", out)
        lines = self.table.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "| " + " | ".join(replay.HEADER) + " |")
        self.assertEqual(lines[1], "|" + "---|" * len(replay.HEADER))
        r = self.row()
        self.assertRegex(r["날짜"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual((r["티켓"], r["시작"], r["worker"], r["커밋"]), (f"{FEATURE}/{TID}", self.start[:7], WORKER, "1"))
        self.assertEqual((r["verify"], r["지적 h/m/l"], r["fix"]), ("통과", "0/0/0", "0"))
        self.assertEqual((r["worker(분)"], r["토큰 입력/캐시/출력"], r["cost"], r["/usage"]), ("0", "–", "–", "–"))
        self.assertEqual(r["비고"], "worker 종료 0")
        self.assertRegex(r["로그"], rf"^{re.escape(WORK)}/run/replay/{TID}-fable-\d{{8}}-\d{{6}}/$")
        logdir = self.logdir(r)
        # worker는 setup을 마친 worktree에서 gs go와 같은 brief·환경으로 돌았다
        self.assertTrue((self.bin / "setup_seen").exists())
        brief = (logdir / "brief.md").read_text(encoding="utf-8")
        self.assertIn("너는 goldstack worker다", brief)
        self.assertIn("03 원래 목표", brief)
        self.assertIn("replay-test-deny", (self.bin / "worker_tests").read_text())
        for name in ("worker.log", "verify.log", "review/diff.patch", "result.json", f"input/{TID}-t.md", "input/spec.md"):
            self.assertTrue((logdir / name).is_file(), name)
        self.assertIn("test -f setup.out", (logdir / "verify.log").read_text(encoding="utf-8"))
        # 리뷰어는 티켓 reviewer 하나, 깨끗한 트리(worker head 그대로)에서 한 번이다
        self.assertEqual((self.bin / "review.calls").read_text(), "codex\n")
        self.assertEqual(Path((self.bin / "review.cwd").read_text().strip()), (logdir / "clean").resolve())
        self.assertEqual((self.bin / "review.status").read_text(), "")
        self.assertFalse((self.bin / "judge.calls").exists())  # 지적이 없으면 판단 모델을 부르지 않는다
        self.assert_no_replay_worktrees()
        self.assertEqual(self.heads(self.repo), heads)
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain"), "?? .goldstack/trials/")  # 커밋하지 않는다

    def test_findings_are_counted_by_severity_and_judged_with_start_touches(self):
        (self.bin / "findings.json").write_text(json.dumps({"findings": [
            finding("high", "FIX 깨짐"), finding("medium", "FIX 빠짐"), finding("low", "이름 취향")]}))
        self.ok()
        r = self.row()
        self.assertEqual((r["지적 h/m/l"], r["fix"]), ("1/1/1", "2"))
        judged = (self.bin / "judge.input").read_text(encoding="utf-8")
        self.assertEqual((self.bin / "judge.calls").read_text(), "call\n")
        self.assertIn("`src/a.py`", judged)  # 시작 commit 티켓의 touches가 고칠 수 있는 파일이다
        self.assertIn(str(self.logdir(r) / "input" / f"{TID}-t.md"), judged)

    # --- 커밋 없음, worker 실패 ---
    def test_no_commit_means_verify_and_review_did_not_run(self):
        self.mode("none")
        self.ok()
        r = self.row()
        self.assertEqual((r["커밋"], r["verify"], r["지적 h/m/l"], r["fix"]), ("0", "안 돎", "안 돎", "안 돎"))
        self.assertFalse((self.bin / "review.calls").exists())
        self.assertFalse((self.logdir(r) / "verify.log").exists())
        self.assert_no_replay_worktrees()

    def test_worker_exit_1_with_commit_still_verifies_and_reviews(self):
        self.mode("exit1")
        self.ok()
        r = self.row()
        self.assertEqual((r["커밋"], r["verify"], r["지적 h/m/l"]), ("1", "통과", "0/0/0"))
        self.assertEqual(r["비고"], "worker 종료 1")
        self.assertTrue((self.bin / "review.calls").exists())

    def test_uncommitted_changes_left_by_worker_are_noted(self):
        self.mode("dirty")
        self.ok()
        self.assertEqual(self.row()["비고"], f"worker 종료 0, {replay.DIRTY}")

    # --- verify ---
    def test_verify_failure_is_recorded_and_review_still_runs(self):
        self.mode("broken")
        self.ok()
        r = self.row()
        self.assertEqual((r["커밋"], r["verify"], r["지적 h/m/l"], r["fix"]), ("2", "실패", "0/0/0", "0"))
        self.assertEqual((self.bin / "review.calls").read_text(), "codex\n")

    def test_verify_that_changes_the_tree_fails_and_review_sees_the_commit_only(self):
        self.mode("mutate")
        self.ok()
        r = self.row()
        self.assertEqual(r["verify"], "실패(트리 바뀜)")
        self.assertIn("made-by-verify", (self.logdir(r) / "verify.log").read_text(encoding="utf-8"))
        self.assertEqual((self.bin / "review.status").read_text(), "")  # verify가 만든 파일은 리뷰 전에 치운다

    # --- 리뷰·판단 실패 ---
    def test_review_call_failure_is_not_zero_findings(self):
        (self.bin / "review.fail").touch()
        self.ok()
        r = self.row()
        self.assertEqual((r["지적 h/m/l"], r["fix"]), (replay.REVIEW_FAILED, replay.REVIEW_FAILED))
        self.assertEqual(r["verify"], "통과")

    def test_judge_failure_is_not_zero_fixes(self):
        (self.bin / "findings.json").write_text(json.dumps({"findings": [finding("high", "FIX 깨짐")]}))
        (self.bin / "judge.fail").touch()
        self.ok()
        r = self.row()
        self.assertEqual((r["지적 h/m/l"], r["fix"]), ("1/0/0", replay.JUDGE_FAILED))

    # --- 사본 ---
    def test_review_and_judge_read_the_frozen_copies_not_the_worker_edits(self):
        self.mode("edit-inputs")
        (self.bin / "findings.json").write_text(json.dumps({"findings": [finding("high", "FIX 깨짐")]}))
        self.ok()
        r = self.row()
        logdir = self.logdir(r)
        head = json.loads((logdir / "result.json").read_text(encoding="utf-8"))["head"]
        edited = sh(self.repo, "git", "show", f"{head}:{WORK}/tickets/{TID}-t.md")
        self.assertIn("worker가 고친 티켓", edited)  # worker head의 티켓은 바뀌었다(이 시험이 그 경우를 본다)
        self.assertIn("worker가 고친 spec", sh(self.repo, "git", "show", f"{head}:{WORK}/spec.md"))
        self.assertEqual((self.bin / "review.ticket").read_text(encoding="utf-8"), TICKET)
        self.assertNotIn("worker가 고친 spec", (self.bin / "review.spec").read_text(encoding="utf-8"))
        prompt = (self.bin / "review.prompt").read_text(encoding="utf-8")
        self.assertIn(f"`{logdir / 'input' / f'{TID}-t.md'}`", prompt)
        self.assertIn(f"`{logdir / 'input' / 'spec.md'}`", prompt)
        judged = (self.bin / "judge.input").read_text(encoding="utf-8")
        self.assertIn(f"`{logdir / 'input' / f'{TID}-t.md'}`", judged)
        self.assertIn(f"`{logdir / 'input' / 'spec.md'}`", judged)

    # --- 브랜치·원격 ---
    def test_branches_moved_by_worker_are_restored_and_noted(self):
        heads = self.heads(self.repo)
        self.mode("move-base")
        out = self.ok()
        self.assertEqual(self.heads(self.repo), heads)  # main은 원래 commit, stray는 없다
        r = self.row()
        self.assertEqual(r["비고"], f"worker 종료 0, {replay.REFS_RESTORED}")
        self.assertEqual((r["커밋"], r["verify"]), ("1", "통과"))
        self.assertIn("브랜치를 되돌렸다: refs/heads/main", out)
        self.assertIn("브랜치를 되돌렸다: refs/heads/stray", out)

    def test_remote_is_untouched_even_when_worker_pushes(self):
        before = self.heads(self.remote)
        self.mode("push")
        self.ok()
        self.assertEqual(self.heads(self.remote), before)
        self.assertNotIn("pushed", (self.bin / "push.err").read_text())

    # --- 표 ---
    def test_row_is_appended_to_an_existing_table(self):
        old = "| " + " | ".join(replay.HEADER) + " |\n|" + "---|" * len(replay.HEADER) + "\n| 옛 행 |"
        self.write(replay.TABLE_REL, old)  # 끝 줄바꿈 없음
        self.ok()
        text = self.table.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(old + "\n"), text)
        self.assertEqual(text.count("| 날짜 |"), 1)
        self.assertEqual(len(self.rows()), 2)
        self.assertEqual(self.rows()[1]["티켓"], f"{FEATURE}/{TID}")

    def test_usage_column_and_claude_result_tokens(self):
        self.mode("result")
        self.ok("--usage", "41,44.5")
        r = self.row()
        self.assertEqual((r["/usage"], r["토큰 입력/캐시/출력"], r["cost"]), ("41→44.5%", "120k/1.8M/40k", "$4.10"))

    # --- 계열 ---
    def test_same_family_as_reviewer_is_refused_before_anything_is_made(self):
        code, out, err = self.replay(worker="codex:gpt-x/high")
        self.assertEqual(code, 1, out + err)
        self.assertIn("리뷰 거부", err)
        self.assertIn(f"시작 commit: {self.start}", out)
        self.assertFalse((self.repo / WORK / "run").exists())
        self.assertFalse(self.table.exists())
        self.assertFalse((self.bin / "worker.pid").exists())
        self.assert_no_replay_worktrees()

    def test_base_overrides_the_start_commit(self):
        later = sh(self.repo, "git", "rev-parse", "main")
        self.ok("--base", later)
        self.assertEqual(self.row()["시작"], later[:7])

    # --- 신호 ---
    def interrupt(self, sig, mode, ready):
        """gs replay를 프로세스로 띄우고 ready 파일이 생기면 sig를 보낸다. (종료 코드, 출력)."""
        self.mode(mode)
        log = self.bin / "gs.log"
        with log.open("w") as f:
            proc = subprocess.Popen([sys.executable, "-m", "gs.cli", "--repo", str(self.repo), "replay", f"{FEATURE}/{TID}",
                                     "--worker", WORKER], stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)
        try:
            deadline = time.monotonic() + 60
            while not (self.bin / ready).exists():
                self.assertIsNone(proc.poll(), log.read_text())
                self.assertLess(time.monotonic(), deadline, log.read_text())
                time.sleep(0.05)
            os.kill(proc.pid, sig)
            code = proc.wait(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            pid = self.bin / "worker.pid"
            if pid.exists():
                self.addCleanup(kill_quietly, int(pid.read_text()))
        return code, log.read_text()

    def assert_interrupted(self, code, log):
        self.assertEqual(code, 130, log)
        self.assertIn("중단", log)
        self.assertFalse(alive(int((self.bin / "worker.pid").read_text())), log)
        self.assert_no_replay_worktrees()
        self.assertFalse(self.table.exists())

    def test_sigterm_during_worker_stops_it_and_removes_the_worktree(self):
        self.assert_interrupted(*self.interrupt(signal.SIGTERM, "hang", "started"))

    def test_sighup_during_worker_stops_it_and_removes_the_worktree(self):
        self.assert_interrupted(*self.interrupt(signal.SIGHUP, "hang", "started"))

    def test_sigint_during_verify_removes_both_worktrees(self):
        code, log = self.interrupt(signal.SIGINT, "hangverify", "verifying")
        self.assert_interrupted(code, log)
        made = list((self.repo / WORK / "run" / "replay").glob("*/verify.log"))
        self.assertEqual(len(made), 1)  # 깨끗한 트리까지 만들고 verify 중이었다


if __name__ == "__main__":
    unittest.main()
