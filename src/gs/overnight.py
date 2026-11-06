"""`gs overnight`: 무인으로 켠 세션의 승인 창을 거부로 바꾸는 표시와 그 판정.

`gs overnight arm`이 `.goldstack/overnight/armed/<pid>.json`에 표시를 남기고, `gs hook permissionrequest`(`hook.py`)가
이 표시를 보고 창 대신 거부를 낸다. 창은 사람이 없으면 닫히지 않아 아침까지 선다. 거부는 세션이 받아 다음 일로 넘어간다.

세션을 가르는 값은 **가장 가까운 조상 Claude 프로세스의 (pid, 시작 시각)**이다.
- `arm`은 Bash 도구의 자식이고 hook은 Claude가 띄운 자식이다. 같은 Claude 프로세스 아래이므로 양쪽에서 같은 값이 나온다
  (2026-11-06 Claude Code 2.1.319 `claude -p`, `--settings`로 건 hook에서 쟀다. 플러그인 경로는 재지 않았다).
- hook 입력의 `session_id`는 `arm`이 알 길이 없다. 그런 환경 변수가 문서에 없다(spec §6). Claude Code 2.1.319의 Bash 환경에
  `CLAUDE_PID`·`CLAUDE_CODE_SESSION_ID`가 보이지만 문서에 없는 값이라 기대지 않는다.
- 레포와 cwd로는 같은 레포의 다른 세션을 가르지 못한다.
- **가장 가까운** 조상이라야 켜진 코디네이터가 `gs go`로 띄운 worker claude가 표시를 물려받지 않는다.
- pid만 믿으면 죽은 세션의 pid가 재사용됐을 때 속는다(`state.py`의 잠금과 같은 이유). 그래서 시작 시각도 맞춘다.
  프로세스가 사라진 표시는 어떤 세션의 값과도 맞지 않아 저절로 꺼진 것이 되고, `arm`·`disarm`이 지운다.

표시는 레포의 주 체크아웃에 둔다. linked worktree로 `cd`한 세션도 같은 표시를 본다. 세션이 다른 레포로 옮겨 가면 그 레포에는
표시가 없어 창이 그대로 뜬다. `arm`·`disarm`은 거부와 창 사이만 바꾼다. 어느 쪽도 호출을 허용하지 않으므로 모델이 꺼도
권한이 넓어지지 않는다. 판정이 실패하면 창으로 돌아간다. 낮 세션을 건드리지 않는 쪽이다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from . import feature as featmod

OVERNIGHT_DIR = ".goldstack/overnight"
ARMED_DIR = f"{OVERNIGHT_DIR}/armed"
DENIED_LOG = f"{OVERNIGHT_DIR}/denied.log"

PS_TIMEOUT = 10  # 초. 넘기면 판정 실패로 보고 창으로 돌아간다
# Linux의 lstart는 부팅 시각에서 계산해 호출마다 1초쯤 흔들린다. 같은 pid가 이 안에 재사용되는 일은 없다
START_SLACK = 2
PS_LINE = re.compile(r"\s*(\d+)\s+(\d+)\s+(\w{3}\s+\w{3}\s+\d+\s+\d+:\d+:\d+\s+\d+)\s+(.*)")
LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"


@dataclass(frozen=True)
class Process:
    ppid: int
    started: int  # epoch 초
    command: str


@dataclass(frozen=True)
class Session:
    pid: int
    started: int  # epoch 초

    def same(self, other: Session) -> bool:
        return self.pid == other.pid and abs(self.started - other.started) <= START_SLACK


# ---------------------------------------------------------------- 세션 찾기

def processes() -> dict[int, Process]:
    """{pid: Process}. `ps`가 안 되면 OSError나 SubprocessError."""
    cp = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,ppid=,lstart=,command="], capture_output=True,
                        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=PS_TIMEOUT,
                        env={**os.environ, "LC_ALL": "C"})
    if cp.returncode != 0:
        raise OSError(cp.stderr.strip() or f"ps 종료 코드 {cp.returncode}")
    table = {}
    for line in cp.stdout.splitlines():
        m = PS_LINE.fullmatch(line)
        if not m:
            continue
        try:
            started = int(time.mktime(time.strptime(" ".join(m.group(3).split()), LSTART_FORMAT)))
        except (ValueError, OverflowError):
            continue
        table[int(m.group(1))] = Process(int(m.group(2)), started, m.group(4))
    return table


def is_claude(command: str) -> bool:
    """명령줄이 Claude Code 프로세스인가. 첫 단어로 가른다. 인자에 `claude`가 든 셸이나 편집기는 세션이 아니다.

    네이티브 설치는 `claude …`(버전 경로를 직접 띄우면 `…/claude/versions/2.1.319 …`)이고 npm 설치는 `node …/claude …`다.
    """
    words = command.split()
    if not words:
        return False
    if os.path.basename(words[0]) == "claude" or "/claude/versions/" in words[0]:
        return True
    return (os.path.basename(words[0]) in ("node", "bun") and len(words) > 1
            and (os.path.basename(words[1]) == "claude" or words[1].endswith("/claude-code/cli.js")))


def current_session(table: dict[int, Process] | None = None) -> Session | None:
    """이 프로세스의 가장 가까운 조상 Claude. Claude 세션 안이 아니면 None."""
    table = processes() if table is None else table
    pid = os.getppid()
    seen: set[int] = set()
    while pid in table and pid not in seen:
        seen.add(pid)
        row = table[pid]
        if is_claude(row.command):
            return Session(pid, row.started)
        pid = row.ppid
    return None


def shared_root(start: Path) -> Path | None:
    """`start`가 속한 레포의 주 체크아웃. linked worktree에서만 git을 부른다. 낮 세션의 창마다 프로세스를 띄우지 않는다."""
    root = featmod.find_repo_root(start.resolve())
    if root is None or (root / ".git").is_dir():
        return root
    cp = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root,
                        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    common = Path(cp.stdout.strip())
    # 서브모듈과 bare 레포의 worktree는 공용 디렉터리가 `.git`이 아니다. 자기 자리를 레포로 본다
    return common.parent if cp.returncode == 0 and common.name == ".git" else root


# ---------------------------------------------------------------- 표시

def _marker(root: Path, pid: int) -> Path:
    return root / ARMED_DIR / f"{pid}.json"


def _read_marker(path: Path) -> Session | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session(int(data["pid"]), int(data["started"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_marker(root: Path, session: Session) -> None:
    """읽는 쪽이 반쯤 쓴 파일을 보지 않게 rename한다. 세션마다 파일이 달라 다른 세션의 표시를 덮지 않는다."""
    directory = root / ARMED_DIR
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": session.pid, "started": session.started}, f)
    os.replace(tmp, _marker(root, session.pid))


def _live_markers(root: Path, table: dict[int, Process]) -> list[Session]:
    """살아 있는 세션의 표시들. 프로세스가 사라진 표시와 읽지 못하는 표시는 지운다."""
    live = []
    for path in sorted((root / ARMED_DIR).glob("*.json")):
        marker = _read_marker(path)
        row = table.get(marker.pid) if marker else None
        if marker and row and marker.same(Session(marker.pid, row.started)) and path == _marker(root, marker.pid):
            live.append(marker)
        else:
            path.unlink(missing_ok=True)
    return live


def _ensure_ignored(root: Path) -> None:
    """표시와 기록이 `git status`에 보이면 `gs go`의 깨끗한 트리 검사를 깬다. `gs init`이 무시 줄을 넣기 전의 옛 레포도 막는다."""
    directory = root / OVERNIGHT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    cp = subprocess.run(["git", "check-ignore", "-q", str(root / ARMED_DIR)], cwd=root, capture_output=True,
                        stdin=subprocess.DEVNULL)
    if cp.returncode != 0:
        ignore = directory / ".gitignore"
        prefix = "\n" if ignore.exists() else ""
        with ignore.open("a", encoding="utf-8") as f:
            f.write(f"{prefix}*\n")


def _table(err: TextIO) -> dict[int, Process] | None:
    try:
        return processes()
    except (OSError, subprocess.SubprocessError) as e:
        print(f"오류: 프로세스 목록을 읽지 못해 세션을 가를 수 없다({e})", file=err)
        return None


def arm(repo: Path, out: TextIO, err: TextIO) -> int:
    """이 Claude 세션의 승인 창을 거부로 바꾼다. 같은 세션에서 다시 쳐도 같다."""
    table = _table(err)
    if table is None:
        return 1
    session = current_session(table)
    if session is None:
        print("오류: 조상에 claude 프로세스가 없다. 거부할 세션을 정하려면 그 Claude 세션의 Bash에서 친다", file=err)
        return 1
    root = shared_root(repo) or repo
    _ensure_ignored(root)
    _live_markers(root, table)
    _write_marker(root, session)
    print(f"켬: Claude 세션 pid {session.pid}의 승인 창을 거부한다. 거부 기록은 {DENIED_LOG}. "
          "끄기는 그 세션에서 `gs overnight disarm`", file=out)
    return 0


def disarm(repo: Path, out: TextIO, err: TextIO) -> int:
    """이 Claude 세션의 표시만 지운다. 켜져 있지 않아도 성공이다. 다른 세션의 표시는 그대로 둔다."""
    table = _table(err)
    if table is None:
        return 1
    root = shared_root(repo) or repo
    live = _live_markers(root, table)
    session = current_session(table)
    if session is None:
        others = ", ".join(str(marker.pid) for marker in live) or "없음"
        print(f"오류: 조상에 claude 프로세스가 없어 어느 표시를 끌지 모른다. 켜진 세션 pid: {others}. "
              "그 세션에서 치거나 그 세션을 끝낸다", file=err)
        return 1
    path = _marker(root, session.pid)
    if any(marker.same(session) for marker in live):
        path.unlink(missing_ok=True)
        print(f"끔: Claude 세션 pid {session.pid}의 승인 창이 다시 뜬다", file=out)
    else:
        print(f"이미 꺼져 있다: Claude 세션 pid {session.pid}", file=out)
    return 0


# ---------------------------------------------------------------- hook 쪽 판정

def armed_root(cwd: Path) -> Path | None:
    """이 프로세스를 띄운 세션이 `cwd`의 레포에서 켜져 있으면 그 레포. 표시가 없는 레포에서는 `ps`를 부르지 않는다."""
    root = shared_root(cwd)
    if root is None or not any((root / ARMED_DIR).glob("*.json")):
        return None
    session = current_session()
    if session is None:
        return None
    marker = _read_marker(_marker(root, session.pid))
    return root if marker and marker.same(session) else None


def record_denied(root: Path, call: str) -> None:
    """시각과 호출 이름을 한 줄 더한다. 줄 하나를 한 번에 쓰므로 세션 둘이 함께 더해도 줄이 섞이지 않는다."""
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with (root / DENIED_LOG).open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {call}\n")
