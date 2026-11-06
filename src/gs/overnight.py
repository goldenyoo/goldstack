"""`gs overnight`: 무인으로 켠 세션의 승인 창을 거부로 바꾸는 표시와 그 판정, 도는 밤에 feature를 더하는 대기열, 사이 단계 묶기.

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

대기열은 밤샘 파일(`.goldstack/overnight/<날짜>.md`)의 `결과` 표다. 저장소를 따로 두지 않는다. `/overnight`이 feature가 끝날 때마다
이 파일을 다시 읽으므로 `gs overnight add`가 더한 줄을 잇는다. 줄 더하기끼리는 잠금으로 줄을 잃지 않는다. 모델의 Edit 도구는 잠금을
모르지만 그때 디스크에 있는 글에 글자를 바꾸므로 더해진 줄이 남는다(2026-11-06 Claude Code 2.1.319로 쟀다). Write 도구로 통째로 쓰면 지워지므로
skill이 Edit을 쓰라고 적는다. 살아 있는 표시가 곧 코디네이터다. `/overnight`이 첫 `gs go`를 띄울 때 켜서 밤이 끝날 때 끄기 때문이다.
`/go`로만 돌고 있으면 표시가 없고, 이어 줄 세션이 없다.

대기열을 닫는 것은 `disarm`이다. 아침 보고를 쓴 밤은 표시가 있을 때만 줄을 받으므로, `disarm`이 `add`와 같은 잠금 안에서 표를 보고
`대기` 줄이 남았으면 끄지 않는다. 표시를 본 `add`가 더한 줄은 끄기 전에 드러나고, 끈 뒤의 `add`는 끝난 밤으로 거부된다.
끈 다음에 다시 읽고 다시 켜지 않는다. 그 틈의 `add`가 새 파일로 가고, 사람이 없는 밤에 `arm`이 창을 띄울 수 있다.

`gs overnight next <다음>`은 사이 단계의 기계적인 일(base 위로 올리기, goldstack 레포면 재설치, `gs check`)을 묶어 허용 규칙을 줄인다.
§6 재확인과 spec 수정은 판단이라 모델이 한다. push는 하지 않는다. `/go` 2단계가 fast-forward로만 올린다.
실행 중에 끝낸 grill은 로컬 커밋으로 남아 base와 갈라진다. 올려도 되는 것은 grill 경로의 커밋뿐이다. 다른 경로는 `/go` 2단계의 push로 검증 없이 base에
들어가므로, base가 앞서지 않았어도 거부한다. 다시 쳐도 된다. 이미 올린 base는 그대로고 재설치가 거부되면 끝난 뒤 다시 치면 잇는다.
재설치는 이 프로세스가 읽을 파일을 바꾼다. 그래서 필요한 모듈을 먼저 다 읽고, `gs check`는 PATH의 `gs`를 새 프로세스로 부른다. 다음 `gs go`가 쓸 그 `gs`다.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from . import feature as featmod
from . import git

OVERNIGHT_DIR = ".goldstack/overnight"
ARMED_DIR = f"{OVERNIGHT_DIR}/armed"
DENIED_LOG = f"{OVERNIGHT_DIR}/denied.log"

PS_TIMEOUT = 10  # 초. 넘기면 판정 실패로 보고 창으로 돌아간다
# Linux의 lstart는 부팅 시각에서 계산해 호출마다 1초쯤 흔들린다. 같은 pid가 이 안에 재사용되는 일은 없다
START_SLACK = 2
PS_LINE = re.compile(r"\s*(\d+)\s+(\d+)\s+(\w{3}\s+\w{3}\s+\d+\s+\d+:\d+:\d+\s+\d+)\s+(.*)")
LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"

QUEUE_LOCK = f"{OVERNIGHT_DIR}/.queue.lock"
NIGHT_FILE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md")  # `<날짜>.md`, 같은 날 둘째부터 `<날짜>-2.md`
FEATURE_NAME = re.compile(r"(?!\.)[^\s|/\\]+")  # 표의 한 칸이자 경로의 한 조각
RESULT_HEADING = "## 결과"
REPORT_HEADING = "## 아침 보고"
TABLE_SEPARATOR = re.compile(r"\|[\s:|-]+\|")
WAITING = "대기"
ROWS_LEFT = f"`{WAITING}` 줄이 남아"
NO_COORDINATOR = "코디네이터: 없음"
MAKE_NIGHT = "`/overnight <feature>`로 시작하거나 `/overnight add <feature>`로 새 밤샘 파일을 만든다"

STEP_BASE = "base 위로 올리기"
STEP_UPDATE = "gs self-update"
STEP_CHECK = "gs check"
STEP_FAILED = "■ 실패 단계"
REBASE_CONFLICT = "rebase 충돌"
CHECK_TIMEOUT = 300  # 초. 넘기면 그 단계의 실패다
GRILL_DIRS = (".goldstack/work/", ".goldstack/out-of-scope/", ".goldstack/ideas/")  # `/go` 2단계가 커밋하는 경로
GRILL_FILE = ".goldstack/profile.md"


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
    """이 Claude 세션의 표시만 지운다. 켜져 있지 않아도 성공이다. 다른 세션의 표시는 그대로 둔다.

    아침 보고를 쓴 밤에 `대기` 줄이 남았으면 끄지 않고 실패한다. 끄면 아무도 그 줄을 잇지 않는다.
    """
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
    if not any(marker.same(session) for marker in live):  # 잠금 파일도 만들지 않는다
        print(f"이미 꺼져 있다: Claude 세션 pid {session.pid}", file=out)
        return 0
    with _queue_lock(root):
        left = _rows_left(root)
        if not left:
            _marker(root, session.pid).unlink(missing_ok=True)
    if left:
        print(f"오류: 가장 최근 밤샘 파일에 아침 보고가 있는데 {ROWS_LEFT} 끄지 않았다: {', '.join(left)}. "
              "그 줄을 잇거나 상태를 고친 뒤 다시 친다", file=err)
        return 1
    print(f"끔: Claude 세션 pid {session.pid}의 승인 창이 다시 뜬다", file=out)
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


# ---------------------------------------------------------------- 대기열

class ResultFileError(Exception):
    """밤샘 파일에 줄을 더할 수 없는 이유."""


def latest_night(root: Path) -> Path | None:
    """가장 최근 밤샘 파일. 이름으로 고른다. 글자 순서로는 `<날짜>-2.md`가 `<날짜>.md`보다 앞이고, 고친 시각은 옛 밤을 고쳐도 바뀐다."""
    nights = {}
    for path in (root / OVERNIGHT_DIR).glob("*.md"):
        m = NIGHT_FILE.fullmatch(path.name)
        if m:
            nights[(m.group(1), int(m.group(2) or 1))] = path
    return nights[max(nights)] if nights else None


@contextlib.contextmanager
def _queue_lock(root: Path):
    """줄 더하기와 대기열 닫기를 하나씩. 밤샘 파일은 rename으로 바뀌므로 잠금은 따로 둔 파일에 건다. 프로세스가 죽으면 저절로 풀린다."""
    fd = os.open(root / QUEUE_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _cells(line: str) -> list[str]:
    return [cell.strip(" `") for cell in line.strip().strip("|").split("|")]


def _result_table(lines: list[str]) -> list[int]:
    """`결과` 표의 줄 번호들(머리와 구분 줄 포함). 표가 없거나 모양이 다르면 ResultFileError. 고칠 자리를 어림하지 않는다."""
    start = next((i for i, line in enumerate(lines) if line.rstrip() == RESULT_HEADING), None)
    table: list[int] = []
    if start is not None:
        for i in range(start + 1, len(lines)):
            line = lines[i].strip()
            if line.startswith("|"):
                table.append(i)
            elif table or line.startswith("#"):
                break
    if (len(table) < 2 or _cells(lines[table[0]])[0] != "feature"
            or not TABLE_SEPARATOR.fullmatch(lines[table[1]].strip())):
        raise ResultFileError(f"`{RESULT_HEADING[3:]}` 표를 찾지 못했다. 표 모양을 고친 뒤 다시 친다")
    return table


def _replace(path: Path, text: str) -> None:
    """읽는 쪽이 반쯤 쓴 파일을 보지 않게 rename한다."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _reported(lines: list[str]) -> bool:
    return any(line.rstrip() == REPORT_HEADING for line in lines)


def _rows_left(root: Path) -> list[str]:
    """아침 보고를 쓴 가장 최근 밤에 남은 `대기` 줄의 feature들. 잠금 안에서 부른다.

    표를 읽지 못하면 없다고 본다. `add`도 그 표에 더하지 못하고, 끄기는 창을 되돌릴 뿐이다.
    """
    night = latest_night(root)
    if night is None:
        return []
    try:
        lines = night.read_text(encoding="utf-8").split("\n")
        rows = _result_table(lines)[2:] if _reported(lines) else []
    except (ResultFileError, OSError, UnicodeDecodeError):
        return []
    return [cells[0] for cells in (_cells(lines[i]) for i in rows) if cells[1:2] == [WAITING]]


def _reopened(root: Path) -> bool:
    """아침 보고가 있는 밤을 잇는 세션이 있는가. `/overnight resume`은 멈춘 밤의 보고를 남긴 채 같은 파일을 잇는다.

    보고를 막 쓰고 아직 끄지 않은 세션도 여기 든다. 그 세션은 `disarm`이 거부해서 더해진 줄을 잇는다.
    """
    try:
        return bool(_live_markers(root, processes()))
    except (OSError, subprocess.SubprocessError) as e:
        # 끝났다고 하면 skill이 새 파일을 만들어 도는 코디네이터가 읽지 않는 표에 줄이 간다
        raise ResultFileError(f"아침 보고가 있는데 프로세스 목록을 읽지 못해({e}) 이 밤을 잇는 세션이 있는지 모른다. 다시 친다") from e


def _enqueue(root: Path, night: Path, name: str) -> str | None:
    """잠금 안에서 부른다. 줄을 더했으면 None, 이미 있으면 그 줄의 상태.

    아침 보고를 쓰고 잇는 세션이 없는 밤에는 더하지 않는다. 며칠 전 허락이 새 feature에 쓰이게 된다.
    """
    lines = night.read_text(encoding="utf-8").split("\n")
    if _reported(lines) and not _reopened(root):
        raise ResultFileError(f"아침 보고까지 쓴 끝난 밤이다. {MAKE_NIGHT}")
    table = _result_table(lines)
    for i in table[2:]:
        cells = _cells(lines[i])
        if cells[0] == name:
            return cells[1] if len(cells) > 1 else "?"
    lines.insert(table[-1] + 1, f"| {name} | {WAITING} | 0 | – | – |")
    _replace(night, "\n".join(lines))
    return None


def _coordinator(root: Path) -> str:
    """`코디네이터: …` 한 줄. 프로세스 목록을 못 읽어도 줄은 이미 더해졌으니 실패로 돌리지 않는다. `모름`은 `없음`이 아니어서 코디네이터를 새로 세우지 않는다."""
    try:
        table = processes()
    except (OSError, subprocess.SubprocessError) as e:
        return f"코디네이터: 모름(프로세스 목록을 읽지 못했다: {e})"
    live = _live_markers(root, table)
    if not live:
        return f"{NO_COORDINATOR}. 이 줄을 이을 세션이 없다. `/overnight add`나 `/overnight resume`을 친 세션이 잇는다"
    session = current_session(table)
    if session and any(marker.same(session) for marker in live):
        return f"코디네이터: 이 세션(pid {session.pid})"
    return "코디네이터: 세션 pid " + ", ".join(str(marker.pid) for marker in live)


def add(repo: Path, name: str, out: TextIO, err: TextIO) -> int:
    """가장 최근 밤샘 파일의 `결과` 표에 `대기` 줄을 더하고 이을 세션이 있는지 알린다. 이미 있으면 그대로 두고 성공이다."""
    root = shared_root(repo) or repo
    if not FEATURE_NAME.fullmatch(name):
        print(f"오류: feature 이름으로 쓸 수 없다: {name!r}", file=err)
        return 1
    if not featmod.work_dir(root, name).is_dir():
        print(f"오류: {featmod.work_rel(name)}가 없다. feature 이름을 확인하거나 `/grill`부터 한다", file=err)
        return 1
    night = latest_night(root)
    if night is None:  # 잠금 파일도 만들지 않는다
        print(f"오류: 줄을 더할 밤샘 파일이 없다. {MAKE_NIGHT}", file=err)
        return 1
    where = night.relative_to(root)
    _ensure_ignored(root)
    try:
        with _queue_lock(root):
            state = _enqueue(root, night, name)
    except (ResultFileError, OSError, UnicodeDecodeError) as e:
        print(f"오류: {where}: {e}", file=err)
        return 1
    print(f"더함: {where}의 결과 표에 {name}({WAITING})" if state is None else f"이미 있다: {where}의 {name}({state})", file=out)
    print(_coordinator(root), file=out)
    return 0


# ---------------------------------------------------------------- 사이 단계

class NextError(Exception):
    """`gs overnight next`의 한 단계가 실패한 이유. 이름은 `feedback._KIND_WORDS`의 낱말로 짓는다."""


def _outside_grill(repo: Path, commits: str) -> list[str]:
    """`commits` 범위가 건드린 경로 중 grill 경로 밖. 합친 diff가 아니라 커밋마다 본다. 고쳤다 되돌린 변경도 그 커밋의 일이다.

    `--no-renames`가 없으면 grill 경로로 옮긴 커밋의 옛 경로가 안 보이고, `--diff-merges=separate`가 없으면 병합 커밋의 경로가 안 보인다.
    """
    names = git.run(repo, "log", "--no-renames", "--diff-merges=separate", "--name-only", "-z", "--format=", commits).stdout
    return sorted({path for path in names.split("\0") if path and not path.startswith(GRILL_DIRS) and path != GRILL_FILE})


def _rebasing(repo: Path) -> bool:
    """`git rev-parse --git-path`는 worktree마다 맞는 자리를 낸다."""
    return any((repo / git.out(repo, "rev-parse", "--git-path", name)).exists() for name in ("rebase-merge", "rebase-apply"))


def _pull_rebase(repo: Path, remote: str, base: str, env: dict[str, str]) -> None:
    """실패하면 시작 전 상태로 돌린다. `--no-autostash`: 설정이 있어도 커밋 안 된 변경을 치우지 않는다. 있으면 git이 시작을 거부한다."""
    before = git.sha(repo, "HEAD")
    cp = git.run(repo, "pull", "--rebase", "--no-autostash", remote, base, check=False, env=env)
    if cp.returncode == 0:
        return
    detail = (cp.stderr or cp.stdout).strip()
    if not _rebasing(repo):
        raise NextError(f"git pull --rebase가 시작하지 못했다: {detail}")
    paths = [path for path in git.run(repo, "diff", "--name-only", "--diff-filter=U", "-z", check=False).stdout.split("\0") if path]
    abort = git.run(repo, "rebase", "--abort", check=False)
    if abort.returncode or _rebasing(repo) or git.sha(repo, "HEAD") != before:
        raise NextError(f"{REBASE_CONFLICT}을 되돌리지 못했다. 사람이 `git status`로 본다(시작 전 HEAD {before}): {abort.stderr.strip()}")
    raise NextError(f"{REBASE_CONFLICT}: 시작 전 상태로 되돌렸다. 충돌 파일: {', '.join(paths) or detail}")


def _onto_base(repo: Path, remote: str, base: str) -> str:
    """`<remote>/<base>` 위로 올리고 한 일을 돌려준다. 받기만 하고 push하지 않는다."""
    branch = git.run(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if branch != base:
        raise NextError(f"현재 브랜치가 {base}가 아니다({branch or 'detached HEAD'})")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")  # 사람이 없는 밤에 비밀번호를 기다리지 않는다
    try:
        git.run(repo, "fetch", remote, base, env=env)
        tip = git.sha(repo, "FETCH_HEAD")  # `<remote>/<base>`는 fetch refspec을 좁힌 레포에서 안 움직인다
        outside = _outside_grill(repo, f"{tip}..HEAD")
        if outside:
            raise NextError(f"push 안 된 커밋에 grill 경로 밖 파일이 있어 올리지 않았다: {', '.join(outside)}")
        ahead, behind = git.count(repo, f"{tip}..HEAD"), git.count(repo, f"HEAD..{tip}")
        if not behind:
            return f"이미 {remote}/{base} 위다(push 안 된 grill 커밋 {ahead}개)"
        if not ahead:
            git.run(repo, "pull", "--ff-only", remote, base, env=env)
            return f"{behind}커밋 fast-forward"
        _pull_rebase(repo, remote, base, env)
        return f"grill 커밋 {ahead}개를 {remote}/{base} 위로 rebase"
    except git.GitError as e:
        raise NextError(str(e)) from e


def _is_goldstack(repo: Path) -> bool:
    """gs 자신을 고치는 레포인가. 읽지 못하는 `pyproject.toml`은 아니라고 본다."""
    try:
        with (repo / "pyproject.toml").open("rb") as f:
            project = tomllib.load(f).get("project")
    except (OSError, ValueError):
        return False
    return isinstance(project, dict) and project.get("name") == "goldstack"


def advance(repo: Path, name: str, out: TextIO, err: TextIO) -> int:
    """`gs overnight next`. base 위로 올리기, goldstack 레포면 `gs self-update`, 새 프로세스로 `gs check`. 첫 실패에서 그 단계를 알리고 1로 끝난다."""
    from . import config, selfupdate  # 재설치 전에 읽는다. 창마다 도는 hook은 쓰지 않는 모듈이다

    def failed(step: str, reason: str) -> int:
        out.flush()  # 앞선 단계의 줄이 실패 줄보다 먼저 보이게
        print(f"{STEP_FAILED}: {step}: {reason}", file=err)
        return 1

    if not FEATURE_NAME.fullmatch(name):
        print(f"오류: feature 이름으로 쓸 수 없다: {name!r}", file=err)
        return 1
    cfg, problems = config.load(repo)
    if cfg is None:
        return failed(STEP_BASE, "; ".join(str(p) for p in problems))
    try:
        done = _onto_base(repo, cfg.git.remote, cfg.git.base)
    except NextError as e:
        return failed(STEP_BASE, str(e))
    print(f"■ {STEP_BASE}: {done}", file=out, flush=True)

    if not _is_goldstack(repo):
        print(f"■ {STEP_UPDATE}: 건너뜀(goldstack 레포가 아니다)", file=out, flush=True)
    elif selfupdate.self_update(repo, None, "main", out, err) != 0:
        return failed(STEP_UPDATE, "이유는 위 줄이다")
    else:
        print(f"■ {STEP_UPDATE}: 끝", file=out, flush=True)

    try:
        cp = subprocess.run(["gs", "check", "--", name], cwd=repo, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", stdin=subprocess.DEVNULL, timeout=CHECK_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as e:
        return failed(STEP_CHECK, f"돌리지 못했다: {e}")
    out.write(cp.stdout)
    err.write(cp.stderr)
    if cp.returncode:
        return failed(STEP_CHECK, f"`gs check {name}` 종료 코드 {cp.returncode}")
    print(f"■ 명령 통과: `gs check {name}`의 경고와 §6 재확인은 모델이 본다", file=out)
    return 0
