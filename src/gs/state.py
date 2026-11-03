"""실행 상태 `.work/<f>/run/state.json`과 실행 잠금 `.work/<f>/run/lock`.

상태의 원천은 state.json 하나다(ORIGINS 실패 3). `gs go`의 요약·PR 본문과 `gs status`가 모두 이것을 읽는다.
쓰기는 같은 디렉터리의 임시 파일에 쓴 뒤 rename한다. 읽는 쪽은 반쯤 쓴 파일을 보지 않는다.

잠금은 lock 파일에 대한 flock이다. 프로세스가 죽으면 커널이 풀어 주므로 죽은 프로세스의 잠금은 저절로 회수된다.
lock 파일에는 잡은 프로세스의 pid를 적어 둔다(보여 주기용). 정상 종료 때는 내용을 비운다(파일은 지우지 않는다:
지우면 같은 이름의 다른 inode를 두 프로세스가 각자 잠그는 틈이 생긴다).
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

PENDING, RUNNING, MERGED, FAILED, SKIPPED = "pending", "running", "merged", "failed", "skipped"
STATUSES = (PENDING, RUNNING, MERGED, FAILED, SKIPPED)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


@dataclass
class TicketState:
    status: str = PENDING
    attempts: int = 0  # worker를 띄운 횟수. 죽은 실행이 남긴 running은 세지 않는다
    branch: str = ""
    pane: str = ""  # 실행기 위치: herdr면 "pane <id>", subprocess면 "pid <n>"
    started_at: str = ""
    ended_at: str = ""
    log: str = ""  # worker 로그 경로
    reason: str = ""  # 실패·건너뜀 이유


@dataclass
class State:
    feature: str
    pid: int = 0  # 마지막으로 이 상태를 쓴 `gs go`
    only: list[str] | None = None
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    tickets: dict[str, TicketState] = field(default_factory=dict)

    def ticket(self, tid: str) -> TicketState:
        return self.tickets.setdefault(tid, TicketState())


def path(rundir: Path) -> Path:
    return rundir / "state.json"


def load(rundir: Path, feature: str) -> State:
    """state.json을 읽는다. 없으면 빈 상태."""
    p = path(rundir)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return State(feature=feature)
    tickets = {}
    for tid, d in raw.get("tickets", {}).items():
        known = {k: v for k, v in d.items() if k in TicketState.__dataclass_fields__}
        tickets[tid] = TicketState(**known)
    top = {k: v for k, v in raw.items() if k in State.__dataclass_fields__ and k != "tickets"}
    top.setdefault("feature", feature)
    return State(**top, tickets=tickets)


def save(rundir: Path, st: State) -> None:
    """임시 파일에 쓰고 rename한다(원자적)."""
    rundir.mkdir(parents=True, exist_ok=True)
    st.updated_at = now()
    data = json.dumps(asdict(st), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".state.", suffix=".tmp", dir=rundir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path(rundir))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Locked(Exception):
    def __init__(self, pid: int | None):
        self.pid = pid
        super().__init__(f"이미 다른 gs go가 돌고 있다(pid {pid if pid else '?'})")


def lock_path(rundir: Path) -> Path:
    return rundir / "lock"


class Lock:
    """feature 하나에 `gs go` 하나. with 문으로 쓴다."""

    def __init__(self, rundir: Path):
        self.path = lock_path(rundir)
        self.fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Locked(_read_pid(self.path)) from None
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        os.fsync(fd)
        self.fd = fd

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            os.ftruncate(self.fd, 0)  # 비운 뒤 푼다: 비어 있으면 '돌고 있지 않음'
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None

    def __enter__(self) -> "Lock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _read_pid(p: Path) -> int | None:
    try:
        txt = p.read_text().strip()
    except FileNotFoundError:
        return None
    return int(txt) if txt.isdigit() else None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def running_pid(rundir: Path) -> int | None:
    """지금 이 feature에 `gs go`가 돌고 있으면 그 pid. 읽기만 한다(잠그지 않는다)."""
    pid = _read_pid(lock_path(rundir))
    return pid if pid and _alive(pid) else None
