"""herdr 원격 실행: 준비 검사(`check`), `/go` 세션 띄우기(`go`), 상태 조회(`status`).

비밀 값·인증 출력은 전송하지 않고 판정만 돌려받는다. 원격 스크립트의 git 출력도 pane에 찍지 않는다.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import types
import uuid
import zlib
from importlib import metadata
from pathlib import Path
from typing import TextIO

from . import adapters, config, git, herdr, version
from .feature import WORK

TIMEOUT = 90
STATUS_TIMEOUT = 20  # herdr의 ssh ConnectTimeout(10초)보다 길게. 끊긴 머신은 시간 초과가 아니라 `error` 줄로 판정한다.
PULL_TIMEOUT = 60  # 원격 git pull 하나. 준비 전체는 TIMEOUT을 더한 만큼 기다린다.
FETCH_TIMEOUT = 60  # 로컬 git fetch 하나.
CREATE_TIMEOUT = 30  # 세션 workspace 만들기·프롬프트 보내기 하나.
SHELL_READY_MS = 30_000  # 새 pane의 셸이 명령을 받을 때까지. 표시 줄을 다시 보내는 시도를 모두 합한 상한이다.
SHELL_READY_TRIES = 5  # 표시 줄을 보내는 최대 횟수. 시도 하나는 SHELL_READY_MS를 이 수로 나눈 만큼 기다린다.
AGENT_READY_MS = 120_000  # claude가 입력을 받을 때까지(herdr 상한 300000).
MIN_FREE = 1024 ** 3  # 최소 1 GiB. worker 산출물을 위한 여유 공간.
GUIDE = "docs/guide.md의 tmux 절"
FEATURE_NAME = re.compile(r"\w[\w.-]*")  # `/go`의 인자는 공백으로 나뉘고 경로에도 들어간다.
EXIT_PREFIX = "GS_REMOTE_EXIT="
SHELL_START_HINT = ("시간 초과; 새 셸이 입력을 받지 않는다. 셸 시작 질문(예: oh-my-zsh 업데이트 질문)이 "
                    "떠 있는지 원격에서 셸을 열어 답한다")
# 원격 세션에는 사람이 없다. 멈춘 실행을 보고 회고·수정·재실행으로 번지지 않게 `/go` 뒤에 붙인다(한 줄이어야 herdr가 한 번에 보낸다).
UNATTENDED = ("사람이 없다. 실행이 멈추면 로그를 읽어 원인 후보만 적고 멈춘다. "
              "회고·수정·재실행은 하지 않는다.")
RELOGIN_HINT = ("재부팅이나 잠자기 뒤에는 Claude 로그인이 풀릴 수 있다. 비대화형 ssh 판정은 이를 못 잡으니 "
                "원격 pane에서 claude 화면을 직접 보고 로그인 요청이 떠 있으면 다시 로그인한다")
NOT_REFUSED = ("timeout", "remote", "unknown")  # 서버의 거절 코드가 아니다. 요청이 적용됐는지 모른다.

# 원격 python3는 gs의 실행 환경과 독립적으로 준비 상태를 검사한다.
# CLI 출력에는 인증 정보가 있을 수 있어 정해진 버전·참/거짓만 결과에 싣는다.
PROBE = r'''
import json, os, shutil, subprocess, sys
from pathlib import Path
repo, commit, minimum, remote = sys.argv[1:]
p = Path(repo).expanduser()
valid = p.is_dir() and (p / '.git').exists()
cwd = str(p) if valid else None

def run(args):
    try:
        cp = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=8,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='false',
                                     SSH_ASKPASS='false', GCM_INTERACTIVE='Never'))
        return cp.returncode == 0, cp.stdout.strip()
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False, ''

def ver(args):
    ok, text = run(args)
    return text.splitlines()[0] if ok and text else None

result = {'repo': valid, 'env': valid and (p / '.goldstack/local.env').is_file()}
result['gs'] = ver(['gs', '--version'])
result['plugin'] = None
ok, text = run(['claude', 'plugin', 'list', '--json'])
if ok:
    try:
        plugins = json.loads(text)
        if isinstance(plugins, list):
            for item in plugins:
                if (isinstance(item, dict) and str(item.get('id', '')).split('@')[0] == 'goldstack'
                        and item.get('enabled', True) is not False):
                    result['plugin'] = item.get('version')
                    break
    except ValueError:
        pass
for name, args in [('gh', ['gh', 'auth', 'status']),
                   ('claude', ['claude', 'auth', 'status']),
                   ('codex', ['codex', 'login', 'status'])]:
    ok, text = run(args)
    if name == 'claude' and ok:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get('loggedIn') is False:
                ok = False
        except ValueError:
            pass
    result[name + '_auth'] = ok
for name in ('claude', 'codex', 'agy'):
    result[name + '_version'] = ver([name, '--version'])
try:
    result['disk'] = shutil.disk_usage(str(p) if valid else str(Path.home())).free >= int(minimum)
except OSError:
    result['disk'] = False
result['grill'] = False
if valid and commit:
    result['grill'] = (run(['git', 'cat-file', '-e', commit + '^{commit}'])[0]
                       or run(['git', '-c', 'credential.interactive=false',
                               'fetch', '--dry-run', remote, commit])[0])
print(json.dumps(result), flush=True)
'''

# `gs remote go`의 원격 준비. 잠금을 먼저 봐서 돌고 있는 실행 밑에서 pull하지 않는다.
# 잠금 판정은 state.running_pid와 같다. git 출력은 인증 정보가 있을 수 있어 싣지 않는다.
PREPARE = r'''
import fcntl, json, os, subprocess, sys
from pathlib import Path
repo, feature, base, remote, pull_timeout = sys.argv[1:]
p = Path(repo).expanduser()
run_dir = p / '.goldstack/work' / feature / 'run'
env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='false', SSH_ASKPASS='false', GCM_INTERACTIVE='Never')

def git(args, timeout=8):
    try:
        cp = subprocess.run(['git', '-c', 'credential.interactive=false'] + args, cwd=str(p), env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        return cp.returncode == 0, cp.stdout.strip()
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False, ''

def running():
    try:
        fd = os.open(str(run_dir / 'lock'), os.O_RDONLY)
    except OSError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        text = os.read(fd, 32).decode(errors='replace').strip()
        return int(text) if text.isdigit() else -1
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    finally:
        os.close(fd)

result = {'running': running(), 'on_base': False, 'pulled': False, 'spec': False, 'path': str(p.resolve())}
if not result['running']:
    result['on_base'] = git(['symbolic-ref', '--short', '-q', 'HEAD']) == (True, base)
    if result['on_base']:
        result['pulled'] = git(['pull', '--ff-only', '-q', remote, base], int(pull_timeout))[0]
    if result['pulled']:
        result['spec'] = (p / '.goldstack/work' / feature / 'spec.md').is_file()
print(json.dumps(result), flush=True)
'''

# 원격 `gs status`를 그대로 pane에 찍고 종료 코드를 끝 줄에 남긴다.
STATUS = r'''
import subprocess, sys
from pathlib import Path
repo, feature, prefix = sys.argv[1:]
try:
    code = subprocess.run(['gs', '--repo', str(Path(repo).expanduser()), 'status', feature],
                          stdin=subprocess.DEVNULL, timeout=30).returncode
except OSError:
    print('원격에 gs를 실행하지 못했다')
    code = 127
except subprocess.TimeoutExpired:
    print('원격 gs status 시간 초과')
    code = 124
print(prefix + str(code), flush=True)
'''


def _run(args: list[str], timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def grill_commit(repo: Path, feature: str | None = None) -> str:
    """feature의 마지막 spec 커밋. 안 주면 현재 브랜치의 feature, 일반 브랜치에서는 마지막 grill spec을 쓴다."""
    branch = _run(["git", "branch", "--show-current"], 10, repo).stdout.strip().split("/")
    if feature is None and len(branch) >= 3 and branch[0] == "gs":
        feature = branch[1]
    path = f"{WORK}/{feature}/spec.md" if feature else f"{WORK}/*/spec.md"
    cp = _run(["git", "log", "-1", "--format=%H", "--", path], 10, repo)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def _root_pane(result: dict) -> str:
    root = result.get("root_pane")
    pane = root.get("pane_id") if isinstance(root, dict) else None
    if not isinstance(pane, str) or not pane:
        raise herdr.HerdrError("remote", "workspace 응답에 root_pane.pane_id가 없다")
    return pane


def _shell_ready(machine: str, pane: str, budget: float = SHELL_READY_MS / 1000) -> None:
    """새 pane의 셸이 입력을 받을 때까지 표시 줄을 보내 확인한다. 전체 대기는 budget초 안이다.

    셸 시작 질문(예: oh-my-zsh 업데이트 `[Y/n]`)이 떠 있으면 첫 입력 글자가 질문의 답으로 먹힌다.
    그래서 실제 조각을 보내기 전에 표시 줄을 보내 줄 첫머리에 단독으로 나올 때까지 기다리고,
    먹혔으면 새 표시 줄로 다시 보낸다. 명령은 `printf`로 시작해 첫 글자가 `Y`(업데이트 승낙)로 읽히지 않는다.
    끝내 나오지 않으면 `timeout` 코드의 HerdrError를 `shell_start`를 켠 채 올린다.
    """
    deadline = time.monotonic() + budget
    attempt = budget / SHELL_READY_TRIES
    for _ in range(SHELL_READY_TRIES):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        marker = f"GS_REMOTE_READY_{uuid.uuid4().hex}"
        try:
            herdr.machine_run(machine, ["pane", "run", pane, f"printf '\\n%s\\n' {marker}"], min(left, CREATE_TIMEOUT))
            # 전송에 걸린 시간을 뺀 잔여로 다시 잰다. 전체 대기가 budget을 넘지 않게 프로세스 제한도 잔여로 막는다.
            left = deadline - time.monotonic()
            if left <= 0:
                break
            wait = min(attempt, left)
            herdr.machine_run(machine, ["pane", "wait-output", pane, "--regex", f"(?m)^{marker}\\r?$",
                                        "--timeout", str(max(1, int(wait * 1000))), "--source", "recent-unwrapped"],
                              min(wait + 5, left))
            return
        except herdr.HerdrError as e:
            if e.code != "timeout":
                raise
    error = herdr.HerdrError("timeout", "새 pane의 셸이 입력을 받지 않는다")
    error.shell_start = True
    raise error


def _script_in_pane(machine: str, script: str, argv: list[str], *, label: str,
                    timeout: float = TIMEOUT, lines: int = 200) -> str:
    """임시 workspace의 pane에서 python3 스크립트를 돌려 그 출력을 돌려준다. pane은 닫는다.

    고유한 끝 줄까지 기다린다. 모든 herdr 호출에 제한 시간이 있다.
    """
    deadline = time.monotonic() + timeout

    def remaining() -> float:
        left = deadline - time.monotonic()
        if left <= 0:
            raise herdr.HerdrError("timeout", "원격 검사 시간 초과")
        return left

    def call(args: list[str]) -> str:
        return herdr.machine_run(machine, args, remaining())

    pane = _root_pane(herdr.machine_call(machine, ["workspace", "create", "--label", label, "--no-focus"], remaining()))
    token = uuid.uuid4().hex
    start, end = f"GS_CHECK_START_{token}", f"GS_CHECK_END_{token}"
    # 새 셸이 canonical 모드여도 받도록 각 입력을 1024바이트보다 짧게 나눈다.
    # 경로·원격 이름도 payload에 넣어 인자가 길어져도 입력 한도를 지킨다.
    payload = "import sys;sys.argv=" + repr(["gs-remote", *argv]) + "\n" + script
    packed = base64.b64encode(zlib.compress(payload.encode())).decode()
    variable = f"GS_CHECK_{token}"

    def run_and_wait(command: str, marker: str) -> None:
        call(["pane", "run", pane, command])
        call(["pane", "wait-output", pane, "--regex", f"(?m)^{marker}\\r?$",
              "--timeout", str(max(1, int(remaining() * 1000))), "--source", "recent-unwrapped"])

    try:
        # 셸 시작 질문이 첫 글자를 먹을 수 있어 조각을 보내기 전에 셸이 입력을 받는지 본다.
        _shell_ready(machine, pane, min(SHELL_READY_MS / 1000, remaining()))
        for index, offset in enumerate(range(0, len(packed), 400)):
            chunk = packed[offset:offset + 400]
            previous = f'"${variable}"' if offset else ""
            marker = f"GS_CHECK_CHUNK_{token}_{index}"
            run_and_wait(f"{variable}={previous}{shlex.quote(chunk)}; printf '\\n%s\\n' {marker}", marker)
        script = "import base64,zlib,sys;exec(zlib.decompress(base64.b64decode(sys.argv[1])))"
        command = ("printf '\\n%s\\n' " + shlex.quote(start) + "; "
                   + shlex.join(["python3", "-c", script]) + f' "${variable}"'
                   + f"; unset {variable}; printf '\\n%s\\n' " + shlex.quote(end))
        run_and_wait(command, end)
        text = call(["pane", "read", pane, "--format", "text", "--source", "recent-unwrapped",
                     "--lines", str(lines), "--raw"])
        # --raw는 pane read의 JSON 포장 대신 텍스트를 받는다.
        rows = text.replace("\r", "").splitlines()
        begin = rows.index(start)
        finish = rows.index(end, begin + 1)
        return "\n".join(rows[begin + 1:finish]).strip()
    except (ValueError, IndexError) as e:
        raise herdr.HerdrError("remote", "원격 결과가 없다(python3와 pane 출력을 확인한다)") from e
    finally:
        # 임시 pane을 닫는다. 정리 실패가 원래 결과를 가리지 않는다.
        try:
            herdr.machine_run(machine, ["pane", "close", pane], 5)
        except herdr.HerdrError:
            pass


def _json_in_pane(machine: str, script: str, argv: list[str], *, label: str, timeout: float = TIMEOUT) -> dict:
    text = _script_in_pane(machine, script, argv, label=label, timeout=timeout)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise herdr.HerdrError("remote", "원격 결과를 읽지 못했다(python3와 pane 출력을 확인한다)") from e
    if not isinstance(data, dict):
        raise herdr.HerdrError("remote", "원격 결과가 객체가 아니다")
    return data


def probe(machine: str, repo_path: str, commit: str, timeout: float = TIMEOUT, *,
          git_remote: str = "origin") -> dict:
    return _json_in_pane(machine, PROBE, [repo_path, commit, str(MIN_FREE), git_remote],
                         label="gs remote check", timeout=timeout)


def prepare(machine: str, repo_path: str, feature: str, base: str, git_remote: str) -> dict:
    """돌고 있는 실행을 보고, 없으면 원격 레포를 base로 fast-forward한다."""
    return _json_in_pane(machine, PREPARE, [repo_path, feature, base, git_remote, str(PULL_TIMEOUT)],
                         label="gs remote prepare", timeout=TIMEOUT + PULL_TIMEOUT)


def launch(machine: str, repo_path: str, feature: str) -> tuple[str, str, bool]:
    """원격 herdr 서버의 새 workspace에 claude를 띄우고 `/go`를 보낸 뒤 기다리지 않고 (workspace, pane, 전송 확인)을 돌려준다.

    pane은 원격 서버 소유이고 이 프로세스는 끝까지 붙어 있지 않는다. 환경 변수나 파일을 넘기지 않으므로
    비밀은 건너가지 않는다(원격 비밀은 원격 local.env가 맡는다). `/go`를 보내기 전에 실패하거나 서버가 `/go`를
    거절하면 만든 workspace를 닫는다. `/go`를 받았는지 모르면 돌고 있을 수 있으니 닫지 않고 전송 확인 False를 돌려준다.
    """
    created = herdr.machine_call(machine, ["workspace", "create", "--cwd", repo_path,
                                           "--label", f"gs remote go {feature}", "--no-focus"], CREATE_TIMEOUT)
    pane = _root_pane(created)
    info = created.get("workspace")
    workspace = info.get("workspace_id") if isinstance(info, dict) else None
    if not isinstance(workspace, str) or not workspace:
        raise herdr.HerdrError("remote", "workspace 응답에 workspace_id가 없다")

    def close(cause: BaseException) -> None:
        try:
            herdr.machine_run(machine, ["workspace", "close", workspace], 10)
        except herdr.HerdrError:
            if isinstance(cause, herdr.HerdrError):
                cause.leftover = workspace

    try:
        # agent start는 셸 프롬프트에서만 받는다. 새 셸이 명령을 돌릴 수 있을 때까지 기다린다.
        _shell_ready(machine, pane)
        # 이름은 살아 있는 agent 사이에서 유일해야 하고 feature 이름의 문자를 다 받지 못한다. 이후는 pane id로 부른다.
        herdr.machine_run(machine, ["agent", "start", f"gs-go-{uuid.uuid4().hex[:8]}", "--kind", "claude",
                                    "--pane", pane, "--timeout", str(AGENT_READY_MS)], AGENT_READY_MS / 1000 + 5)
    except BaseException as e:
        close(e)
        raise
    try:
        herdr.machine_run(machine, ["agent", "prompt", pane, f"/go {feature} {UNATTENDED}"], CREATE_TIMEOUT)
    except KeyboardInterrupt:
        return workspace, pane, False
    except herdr.HerdrError as e:
        if e.code in NOT_REFUSED:
            return workspace, pane, False
        close(e)
        raise
    return workspace, pane, True


def _not_pushed(repo: Path, cfg: config.Config, feature: str) -> str | None:
    """`/go` 2단계·`gs go`와 같은 조건: feature의 spec·티켓이 깨끗하고 `<remote>/<base>`와 같다. 어긋나면 이유."""
    from . import go as gomod

    try:
        fetched = _run(["git", "fetch", "-q", cfg.git.remote, cfg.git.base], FETCH_TIMEOUT, repo)
    except (OSError, subprocess.TimeoutExpired):
        return f"{cfg.git.remote}/{cfg.git.base}를 받지 못했다. 연결을 확인하고 다시 친다"
    if fetched.returncode:
        return f"{cfg.git.remote}/{cfg.git.base}를 받지 못했다. 연결과 git.remote·git.base 설정을 확인한다"
    run = types.SimpleNamespace(name=feature, repo=repo, base_ref=f"{cfg.git.remote}/{cfg.git.base}")
    try:
        gomod._require_committed(run)
    except git.GitError as e:
        return str(e)
    return None


def _failure_text(e: herdr.HerdrError) -> str:
    """오류 코드만 보인다. 본문은 원격 출력일 수 있다."""
    if getattr(e, "shell_start", False):
        return SHELL_START_HINT
    if e.code == "timeout":
        return "시간 초과(요청은 적용됐을 수 있다)"
    return e.code if re.fullmatch(r"[a-z_]+", e.code or "") and e.code not in ("remote", "unknown") else "요청 실패"


def _feature_problem(feature: str) -> str | None:
    if FEATURE_NAME.fullmatch(feature):
        return None
    return f"feature 이름 {feature!r}을 원격에 보낼 수 없다(글자·숫자·._-만)"


def go(repo: Path, machine: str, feature: str, out: TextIO, err: TextIO) -> int:
    """검사 → push 확인 → 원격 준비(실행 중 확인·pull) → 세션 띄우기. 앞이 실패하면 세션을 띄우지 않고 1이다.

    `/go` 전송을 확인하지 못하면 세션을 남기고 확인 방법을 출력한 뒤 1이다.
    """
    problem = _feature_problem(feature)
    if problem:
        print(f"오류: {problem}", file=err)
        return 1
    if not (repo / WORK / feature / "spec.md").is_file():
        print(f"오류: {WORK}/{feature}/spec.md가 없다 → /grill {feature}", file=err)
        return 1
    if check(repo, machine, out, err, feature):
        print("gs remote go: 빠진 것이 있어 세션을 띄우지 않았다.", file=err)
        return 1
    cfg, _ = config.load(repo)  # check가 이미 읽어 오류가 없음을 확인했다
    problem = _not_pushed(repo, cfg, feature)
    if problem:
        print(f"오류: {problem}. 세션을 띄우지 않았다.", file=err)
        return 1
    quoted = shlex.quote(machine)
    status_command = f"gs remote status {quoted} {feature}"
    try:
        ready = prepare(machine, config.read_local_env(repo)[f"GS_REMOTE_REPO_{machine}"], feature,
                        cfg.git.base, cfg.git.remote)
    except herdr.HerdrError as e:
        print(f"오류: 원격 준비 실패({_failure_text(e)}). 세션을 띄우지 않았다.", file=err)
        return 1
    running = ready.get("running")
    if running:
        shown = running if isinstance(running, int) and running > 0 else "?"
        print(f"{feature}의 gs go가 {machine}에서 이미 돌고 있다(pid {shown}). 세션을 띄우지 않았다.", file=err)
        print(f"상태: {status_command}", file=err)
        return 1
    for key, remedy in (("on_base", f"원격 레포가 {cfg.git.base} 브랜치가 아니다. 원격에서 브랜치를 옮긴다"),
                        ("pulled", f"원격 git pull --ff-only {cfg.git.remote} {cfg.git.base} 실패. 원격 레포의 인증·갈라짐·커밋 안 된 변경을 확인한다"),
                        ("spec", f"원격 레포에 {WORK}/{feature}/spec.md가 없다. 원격의 {cfg.git.remote} 주소를 확인한다")):
        if ready.get(key) is not True:
            print(f"오류: {remedy}. 세션을 띄우지 않았다.", file=err)
            return 1
    path = ready.get("path")
    if not isinstance(path, str) or not path:
        print("오류: 원격 결과에 레포 경로가 없다. 세션을 띄우지 않았다.", file=err)
        return 1
    try:
        workspace, pane, sent = launch(machine, path, feature)
    except herdr.HerdrError as e:
        print(f"오류: 원격 세션을 띄우지 못했다({_failure_text(e)}).", file=err)
        leftover = getattr(e, "leftover", None)
        if leftover:
            print(f"workspace {leftover}를 닫지 못했다 → herdr --machine {quoted} workspace close {leftover}", file=err)
        elif e.code == "agent_not_ready":
            print("claude가 승인 화면에서 멈췄다. 원격에서 한 번 claude를 띄워 로그인·폴더 신뢰를 끝낸다.", file=err)
        else:
            print(f"남은 것이 있는지 본다 → herdr --machine {quoted} workspace list", file=err)
        return 1
    stream = out if sent else err
    if sent:
        print(f"■ {machine}에서 /go {feature} 시작", file=out)
    else:
        print(f"오류: /go {feature}의 전송 응답을 받지 못했다. 전달됐을 수 있어 세션을 닫지 않았다.", file=err)
    print(f"workspace: {workspace}", file=stream)
    print(f"pane: {pane}", file=stream)
    print(f"상태: {status_command}", file=stream)
    print(f"화면: herdr --machine {quoted} pane read {shlex.quote(pane)} --lines 40", file=stream)
    if sent:
        return 0
    print(f"화면에 /go가 없을 때만 닫고 다시 친다 → herdr --machine {quoted} workspace close {shlex.quote(workspace)}", file=err)
    return 1


def status(repo: Path, machine: str, feature: str, out: TextIO, err: TextIO) -> int:
    """원격 `gs status <feature>`의 출력과 종료 코드를 그대로 돌려준다."""
    problem = _feature_problem(feature)
    if problem:
        print(f"오류: {problem}", file=err)
        return 1
    if not shutil.which(herdr.bin()):
        print(f"오류: herdr가 없다 → {GUIDE}을 따른다", file=err)
        return 1
    key = f"GS_REMOTE_REPO_{machine}"
    path = config.read_local_env(repo).get(key, "")
    if not path:
        print(f"오류: .goldstack/local.env에 {key}=<원격 레포 절대 경로>를 쓴다", file=err)
        return 1
    try:
        text = _script_in_pane(machine, STATUS, [path, feature, EXIT_PREFIX], label="gs remote status", lines=1000)
    except herdr.HerdrError as e:
        print(f"오류: 원격 상태를 읽지 못했다({_failure_text(e)}). gs remote check {shlex.quote(machine)}로 확인한다.", file=err)
        return 1
    rows = text.splitlines()
    last = rows.pop() if rows else ""
    if not re.fullmatch(re.escape(EXIT_PREFIX) + r"[0-9]+", last):
        print("오류: 원격 상태 결과가 잘렸다. 다시 친다.", file=err)
        return 1
    body = "\n".join(rows).strip()
    if body:
        print(body, file=out)
    return int(last[len(EXIT_PREFIX):])


def _local_cli(repo: Path, name: str) -> str | None:
    binary = adapters.claude_bin() if name == "claude" else os.environ.get("GS_" + name.upper(), name)
    try:
        cp = _run([binary, "--version"], 8, repo)
        return cp.stdout.strip().splitlines()[0] if cp.returncode == 0 and cp.stdout.strip() else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def check(repo: Path, machine: str, out: TextIO, err: TextIO, feature: str | None = None) -> int:
    """feature를 주면 그 feature의 grill 커밋을 본다(`gs remote go`)."""
    failed = False

    def item(name: str, ok: bool, remedy: str) -> None:
        nonlocal failed
        failed |= not ok
        print(f"{'통과' if ok else '빠짐'}: {name} → {'준비됨' if ok else remedy}", file=out)

    if not shutil.which(herdr.bin()):
        print(f"오류: herdr가 없다 → {GUIDE}을 따른다", file=err)
        return 1
    try:
        # 지정한 머신만 묻는다. 머신을 안 주면 저장된 머신 전부에 ssh해서 끊긴 머신 하나가 전체를 늦춘다.
        cp = _run([herdr.bin(), "machine", "status", machine], STATUS_TIMEOUT)
        # 지정한 머신이 끊겨도 종료 1이니 그 머신의 줄로 판정한다.
        rows = [line.replace('\\t', '\t').split() for line in cp.stdout.splitlines()]
        row = next((r for r in rows if len(r) == 3 and machine in r[:2]), None)
        if row is None:
            print(f"오류: 저장된 머신이 아니다 → herdr 머신 등록 또는 {GUIDE}을 따른다", file=err)
            return 1
        connected = row[-1] == "reachable"
        item("연결", connected, "herdr machine status로 연결을 복구한다")
        if not connected:
            return 1
        key = f"GS_REMOTE_REPO_{machine}"
        path = config.read_local_env(repo).get(key, "")
        item("레포 경로 설정", bool(path), f".goldstack/local.env에 {key}=<원격 레포 절대 경로>를 쓴다")
        if not path:
            return 1
        cfg, problems = config.load(repo)
        if cfg is None:
            for problem in problems:
                print(problem, file=err)
            return 1
        commit = grill_commit(repo, feature)
        data = probe(machine, path, commit, git_remote=cfg.git.remote)
        local = version.installation(repo)
        remote_gs = data.get("gs")
        item("gs", remote_gs == f"gs {local.version}", "원격에서 gs self-update(미설치면 gs 설치)")
        item("goldstack 플러그인", bool(local.plugin_version) and data.get("plugin") == local.plugin_version,
             "원격에서 gs self-update; 로컬 플러그인 버전도 확인한다")
        for name, login in (("gh", "gh auth login"), ("claude", "claude auth login"), ("codex", "codex login")):
            item(f"{name} 인증", data.get(name + "_auth") is True, f"원격에서 {login}" + ("; 재부팅·잠자기 뒤라면 pane에서 claude 로그인 화면을 다시 본다" if name == "claude" else ""))
        item("디스크 여유", data.get("disk") is True, "원격 레포 볼륨에 1 GiB 이상 확보한다")
        item("레포 경로", data.get("repo") is True, f"{key} 경로에 레포를 clone한다")
        item(".goldstack/local.env", data.get("env") is True, "원격 레포에 .goldstack/local.env를 직접 준비한다(값은 검사하지 않음)")
        item("grill 커밋 수신", bool(commit) and data.get("grill") is True,
             f"feature spec을 커밋·push하고 원격 레포의 {cfg.git.remote}과 git 인증을 확인한다")
        for name in ("claude", "codex", "agy"):
            current, remote = _local_cli(repo, name), data.get(name + "_version")
            if current != remote or current is None:
                print(f"경고: {name} 버전 차이 또는 조회 불가 → 양쪽 {name} --version을 확인한다", file=out)
    except (OSError, subprocess.TimeoutExpired, herdr.HerdrError, metadata.PackageNotFoundError) as e:
        # 명령 출력에는 비밀이 있을 수 있어 예외 본문을 그대로 내보내지 않는다.
        reason = "시간 초과" if isinstance(e, subprocess.TimeoutExpired) or getattr(e, "code", "") == "timeout" else "조회 실패"
        if getattr(e, "shell_start", False):
            reason = SHELL_START_HINT
        item("원격 검사", False, f"{reason}; herdr 연결·python3·pane 상태를 확인하고 다시 실행한다")
    print(f"안내: {RELOGIN_HINT}", file=out)
    return int(failed)
