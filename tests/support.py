"""임시 레포 환경 격리와 gs go 시나리오 시험의 공용 fixture."""
import atexit
import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from gs import adapters, cli, config, state, worker

# 실행 전 샌드박스 점검(gs.sandbox)이 이 머신의 codex·Landlock에 기대지 않게 한다. 점검을 시험하는 시험은 값을 직접 넣는다.
# CI에는 codex가 없고, GoTest의 가짜 codex는 종료 1이다.
os.environ.setdefault("GS_SANDBOX_PROBE", "pass")

# check의 가짜 모델 이름을 실제 홈 캐시와 대조하지 않는다. 목록 시험은 CODEX_HOME을 따로 덮어쓴다.
_model_home = tempfile.TemporaryDirectory(prefix="gs-test-models-")
atexit.register(_model_home.cleanup)
os.environ["CODEX_HOME"] = _model_home.name

REQUIRE_LANDLOCK = "GS_REQUIRE_LANDLOCK"


def landlock_required(env=None) -> bool:
    """`GS_REQUIRE_LANDLOCK=1`이면 Landlock 시험을 건너뛰지 않고 실패시킨다(CI의 `linux-only` job)."""
    return (os.environ if env is None else env).get(REQUIRE_LANDLOCK) == "1"


def landlock_gate(abi: int, env=None) -> tuple[str, str]:
    """Landlock 시험을 돌릴지 정한다. `("run", "")`, `("skip", 이유)`, `("fail", 이유)` 중 하나다.

    ABI가 1 이상이면 돌린다. 못 쓰는데 `GS_REQUIRE_LANDLOCK=1`이면 skip 대신 실패다. 두 Landlock 시험 파일이 함께 쓴다."""
    if abi >= 1:
        return "run", ""
    reason = "Landlock을 쓸 수 없는 머신(리눅스가 아니거나 커널이 지원하지 않음)"
    if landlock_required(env):
        return "fail", f"{REQUIRE_LANDLOCK}=1인데 {reason}"
    return "skip", reason


def skip_or_fail_landlock(test: unittest.TestCase, reason: str, env=None) -> None:
    """Landlock 시험 안에서 환경이 모자랄 때: 보통은 skip, `GS_REQUIRE_LANDLOCK=1`이면 실패."""
    if landlock_required(env):
        test.fail(f"{REQUIRE_LANDLOCK}=1인데 {reason}")
    test.skipTest(reason)


def requires_landlock(abi: int, env=None):
    """클래스 데코레이터. Landlock이 없으면 시험을 skip하고, `GS_REQUIRE_LANDLOCK=1`이면 시험마다 실패시킨다."""
    action, reason = landlock_gate(abi, env)

    def decorate(cls):
        if action == "run":
            return cls
        if action == "skip":
            return unittest.skip(reason)(cls)

        def failing(self):
            self.fail(reason)

        for name in [n for n in dir(cls) if n.startswith("test")]:
            if callable(getattr(cls, name)):
                setattr(cls, name, failing)
        return cls

    return decorate


APPLE_GIT_SHIM = "/usr/bin/git"
_shim_dir = None  # import 때 만든 링크 디렉터리. 프로세스가 끝날 때 지운다


def real_git_for_shim(path=None, shim=APPLE_GIT_SHIM):
    """`git`이 Apple shim(/usr/bin/git)이면 `xcrun --find git`이 가리키는 진짜 git 경로, 아니면 None.

    xcrun이 없거나 실패하거나 진짜 git이 실행 파일이 아니면 None이다(리눅스 포함)."""
    git = shutil.which("git", path=path)
    if git != shim:
        return None
    try:
        found = subprocess.run(["xcrun", "--find", "git"], capture_output=True, text=True, timeout=30,
                               env={**os.environ, "PATH": path} if path is not None else None)
    except (OSError, subprocess.SubprocessError):
        return None
    real = found.stdout.strip()
    if found.returncode != 0 or not real or real == git or not os.access(real, os.X_OK):
        return None
    return real


def link_real_git(real, parent=None):
    """진짜 git 링크 하나만 든 새 디렉터리를 만들어 경로를 돌려준다. 디렉터리 통째로 PATH에 얹으면 python3·make 등을 가린다."""
    directory = tempfile.mkdtemp(prefix="gs-test-git-", dir=parent)
    os.symlink(real, os.path.join(directory, "git"))
    return directory


def real_git_env(real):
    """진짜 git의 하위 명령·템플릿 경로. 찾지 못하면 None.

    Command Line Tools의 git은 링크된 위치를 기준으로 이 둘을 찾는다. Xcode가 없는 Mac에서 그대로 링크하면
    `git init`이 `hooks` 없는 저장소를 만들고 하위 명령 경로도 틀어진다."""
    try:
        found = subprocess.run([real, "--exec-path"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    exec_path = found.stdout.strip()
    templates = os.path.normpath(os.path.join(exec_path, "..", "..", "share", "git-core", "templates"))
    if found.returncode != 0 or not os.path.isdir(exec_path) or not os.path.isdir(templates):
        return None
    return {"GIT_EXEC_PATH": exec_path, "GIT_TEMPLATE_DIR": templates}


def bypass_git_shim():
    """Apple shim이면 링크 디렉터리를 PATH 맨 앞에 올린다. 아니거나 진짜 git의 경로를 모르면 아무것도 바꾸지 않는다."""
    global _shim_dir
    real = real_git_for_shim()
    env = real_git_env(real) if real is not None else None
    if env is None:
        return None
    _shim_dir = link_real_git(real)
    atexit.register(shutil.rmtree, _shim_dir, ignore_errors=True)
    os.environ["PATH"] = _shim_dir + os.pathsep + os.environ.get("PATH", "")
    os.environ.update(env)
    return _shim_dir


bypass_git_shim()


def fake_clis(test, *names):
    """가짜 CLI를 PATH 앞에 올린다. `gs check`는 CLI가 PATH에 있는지만 보므로, 진짜 CLI가 있는 머신과 없는 머신(CI)에서 같게 돈다."""
    root = tempfile.TemporaryDirectory()
    test.addCleanup(root.cleanup)
    for name in names:
        path = Path(root.name) / name
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    patch = mock.patch.dict(os.environ, {"PATH": root.name + os.pathsep + os.environ["PATH"]})
    patch.start()
    test.addCleanup(patch.stop)


ONLY_MERGES = "GS_TEST_ONLY_MERGES"  # 시험 전용(go.ONLY_MERGES_ENV). test_only_no_merge만 이 변수 없이 새 규칙을 본다


def isolate_git_env(test):
    """임시 레포 시험의 공통 환경. GoTest와 자체 fixture(test_adapters 등)의 `--only`가 마무리까지 가던 동작도 여기서 유지한다."""
    patch = mock.patch.dict(os.environ)
    patch.start()
    test.addCleanup(patch.stop)
    os.environ[ONLY_MERGES] = "1"
    for name in tuple(os.environ):
        if name in ("GIT_CONFIG_COUNT", "GH_TOKEN") or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            os.environ.pop(name)


def git_clean(wt):
    return subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout == ""


def alive(pid):
    """좀비는 죽은 것으로 본다."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def group_alive(pgid):
    """프로세스 그룹에 좀비 아닌 프로세스가 있나."""
    rows = subprocess.run(["ps", "-A", "-o", "pgid=,stat="], capture_output=True, text=True).stdout.splitlines()
    return any(int(row.split()[0]) == pgid and not row.split()[1].startswith("Z") for row in rows if len(row.split()) == 2)


def kill_group_quietly(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):  # macOS: 좀비만 남은 그룹이면 PermissionError
        pass


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
if [ -f "$here/barrier" ]; then  # 시작한 worker가 barrier개가 될 때까지 기다린다(최대 60초): 동시 실행의 증거
  for i in $(seq 1200); do [ "$(grep -c '^start' "$here/events.log")" -ge "$(cat "$here/barrier")" ] && break; sleep 0.05; done
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
  15) for i in $(seq 1200); do [ -f "$here/verifying" ] && break; sleep 0.05; done  # 다른 티켓의 검증 도중에
      touch "$GS_WORKTREE/../integration/BROKEN"; git -C "$GS_WORKTREE/../integration" add BROKEN
      echo 15 > file_15; git add -A; git commit -qm t15 ;;
  16) git fetch -q origin && echo ok > "$here/fetch_16"
      if git push -q origin HEAD:refs/heads/leak 2>"$here/push_16"; then echo pushed >> "$here/push_16"; fi
      echo "$GH_TOKEN" > "$here/gh_16"
      echo 16 > file_16; git add -A; git commit -qm t16 ;;
  *)  echo "$GS_TICKET $GS_ROLE" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET" ;;
esac
"""


def times_out_once_ready(ready: Path):
    """`bash -c` 명령(verify)의 시간 제한을 실제 시간 대신 "명령이 준비됐다"로 정한다.

    짧은 제한(1초)이면 부하에서 bash가 pid 파일을 쓰기도 전에 시간이 끝나 시험이 흔들린다. 명령이 할 일을 마치고 `ready` 파일을 만든다.
    그 파일이 생기고도 명령이 안 끝났으면 시간 초과다. 시간 초과 뒤 정리(SIGTERM→SIGKILL, 자손 종료)는 실제 코드가 한다.
    """
    class ReadyPopen(subprocess.Popen):
        def wait(self, timeout=None):
            if timeout is None or self.args[:2] != ["bash", "-c"]:
                return super().wait(timeout)
            give_up = time.monotonic() + 120  # 명령이 끝내 준비되지 못해도 시험이 영영 서지 않게. 그때는 단정이 실패한다
            while True:
                try:
                    return super().wait(0.05)
                except subprocess.TimeoutExpired:
                    if ready.exists() or time.monotonic() > give_up:
                        raise

    return mock.patch.object(subprocess, "Popen", ReadyPopen)


# 멈춘 worker를 알아채는 유휴 제한(초). 멀쩡한 가짜 worker가 부하로 이만큼 조용해지면 시험이 틀리게 시간 초과로 본다. 짧게 두지 않는다
IDLE_SECONDS = 5.0

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
"""  # worker는 한 번에 하나다(max_workers 1). 병렬 시험은 ParallelTest. 리뷰 중인 티켓은 자리를 비우니 티켓 순서가 중요하면 blocked_by로 고정한다


def ticket(tid, deps="[]", title=None):
    title = title or f"t{tid}"
    return f'---\nid: "{tid}"\ntitle: {title}\nblocked_by: {deps}\nmodel: claude\nreviewer: codex\n---\n## 목표\n{tid}\n'


class _ShError(subprocess.CalledProcessError):
    """CalledProcessError인데 메시지에 stderr도 싣는다."""

    def __str__(self):
        return f"{super().__str__()}\nstderr:\n{self.stderr}"


def sh(cwd, *args):
    try:
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as e:
        raise _ShError(e.returncode, e.cmd, e.stdout, e.stderr) from None


class GoTest(unittest.TestCase):
    """시험 메서드 없이 준비·정리와 도우미만 제공한다."""
    BASE, REMOTE = "main", "origin"  # .goldstack/config.toml [git]. TrunkUpstreamTest가 바꾼다
    # 병합 뒤 첫 base 검증 건너뛰기(finish._same_as_verified). 가짜 gh는 base를 옮기지 않고 병합해 병합 커밋이 늘 integration과 같은
    # 코드다. 켜 두면 main에서만 실패하게 만든 시험(분리 HEAD·병합 커밋 제목으로 가른다)이 검증 없이 verified가 되어 실패·revert·재시도를
    # 보지 못한다. 그래서 기본은 끈다(건너뛰기가 없던 때와 같다). 건너뛰기는 test_postmerge_skip이 켜고 본다.
    POSTMERGE_SKIP = False

    def setUp(self):
        isolate_git_env(self)
        if not getattr(self, "POSTMERGE_SKIP", False):  # G = support.GoTest로 메서드만 빌려 쓰는 시험도 끈다
            same = mock.patch("gs.finish._same_as_verified", return_value=False)
            same.start()
            self.addCleanup(same.stop)
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

    def add_ticket(self, tid, title=None, push=True, deps="[]"):
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        (self.repo / ".goldstack/work" / "demo" / "tickets" / f"{tid}-t.md").write_text(ticket(tid, deps, title=title))
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

    # --- 병합한 티켓 worktree·브랜치 정리(v1 02) ---
    def assert_ticket_cleaned(self, tid, suffix=""):
        wt = self.rundir / "wt" / (tid + suffix)
        self.assertFalse(wt.exists())
        self.assertNotIn(str(wt), self.integration("worktree", "list", "--porcelain"))
        self.assertEqual(self.integration("branch", "--list", f"gs/demo/{tid}{suffix}"), "")

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

    # --- 08 리뷰(claude) 반영 ---
    def break_main(self, advance=False):
        """main 검증(분리 HEAD)에서 file_01이 있으면 실패하는 verify. advance면 revert 직전의 검증(코드가 같아 다시 도는 재시도) 도중
        다른 사람이 main에 push해 revert push가 거부된다."""
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
            {'[ -f "$(dirname "$0")/failed_once" ] && bash "$(dirname "$0")/advance.sh"' if advance else ':'}
            touch "$(dirname "$0")/failed_once"
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
        with mock.patch.dict(os.environ, env), mock.patch("gs.go._idle_seconds", return_value=IDLE_SECONDS), \
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

    def _fail_once_then_succeed(self):
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            if [ ! -f "$here/first" ]; then touch "$here/first"; exit 1; fi
            echo done > file_01; git add -A; git commit -qm done
        '''))

    # --- verify 시간 제한(v1 01): GS_VERIFY_TIMEOUT=1초 ---
    def hang_verify(self, stage):
        """stage(ticket: 병합 전, integration: 마무리 integration, main: main 검증)에서만 멈추는 verify.
        멈출 때 자식을 백그라운드로 띄우고 그 pid를 bin/bg_<n>에 적은 뒤 bin/hung을 만든다. 나머지는 `test ! -f BROKEN`."""
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
              echo "hanging in $now"; touch "$here/hung"; sleep 300
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
