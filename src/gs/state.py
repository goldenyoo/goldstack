"""실행 상태 `.goldstack/work/<f>/run/state.json`과 실행 잠금 `.goldstack/work/<f>/run/lock`.

상태의 원천은 state.json 하나다(ORIGINS 실패 3). `gs go`의 요약·PR 본문과 `gs status`가 모두 이것을 읽는다.
쓰기는 같은 디렉터리의 임시 파일에 쓴 뒤 rename한다. 읽는 쪽은 반쯤 쓴 파일을 보지 않는다.

잠금은 lock 파일에 대한 flock이다. 프로세스가 죽으면 커널이 풀어 주므로 죽은 프로세스의 잠금은 저절로 회수된다.
lock 파일에는 잡은 프로세스의 pid를 적어 둔다(보여 주기용). 정상 종료 때는 내용을 비운다(파일은 지우지 않는다:
지우면 같은 이름의 다른 inode를 두 프로세스가 각자 잠그는 틈이 생긴다).
'돌고 있나'는 잠금이 실제로 잡혀 있는지로 판단한다. 적힌 pid만 믿으면 죽은 gs의 pid가 재사용됐을 때 속는다.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import median

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
    worktree: str = ""
    failures: int = 0  # 이번 실행의 실패 횟수. 중단 후 이어갈 때도 재시도 한도를 유지한다
    failed_worktrees: list[str] = field(default_factory=list)  # 재시도·재실행 뒤에도 보존
    kept_worktrees: list[str] = field(default_factory=list)  # 병합됐지만 미커밋 변경 때문에 남긴 경로
    failure_summary: str = ""  # 재시도 brief에 붙일 판단 모델 요약 파일
    # 마지막 시도의 리뷰 기록(06, review.run): reviewer, dir, merge_base, note, fix, findings.
    # 재리뷰가 있었으면 rereviews(회차마다 round, dir, base, head, note, failed)도 있다.
    # 지적마다 severity·location·claim·evidence·action(fix|report)·why, 그리고 수정·재리뷰 결과(review.Finding):
    #   fix_attempt("" | attempted | discarded), fix_round(이 지적을 받은 마지막 수정 worker 회차, 0이면 받은 적 없음),
    #   fix_reason(수정 못 한 이유: 한도, 띄우지 못함, 수정 worker 실패…),
    #   rereview("" | resolved | unresolved | unchecked), rereview_reason(unchecked의 이유: 시간 초과 | 한도 | 재리뷰 실패),
    #   rereview_evidence(판정 근거·실패 내용), rereview_round(그 결과를 낸 재리뷰 회차),
    #   found_round(0 첫 리뷰, 1·2 그 회차 재리뷰가 새로 낸 지적. 2회차는 늘 report).
    # 지적 하나의 결말은 이 순서로 읽는다: action이 report면 보고만 → rereview가 있으면 그 값(2차 수정을 못 했거나 버렸어도
    # 1차 재리뷰의 unresolved는 그대로 미해결이다) → fix_reason이 있으면 수정 못 함.
    review: dict = field(default_factory=dict)
    # 두 번째 리뷰(second_reviewer)의 기록. 모양은 review와 같다. second_reviewer가 없는 티켓은 비어 있다
    second_review: dict = field(default_factory=dict)
    # 단계 전환마다 추가한다. attempt는 worker 실행 디렉터리 번호(중단 재개 때도 재사용하지 않음).
    # 각 항목: attempt, phase, model, started_at, ended_at. 지난 시도도 보고서에 합산한다.
    phases: list[dict] = field(default_factory=list)


@dataclass
class State:
    feature: str
    pid: int = 0  # 마지막으로 이 상태를 쓴 `gs go`
    only: list[str] | None = None
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    tickets: dict[str, TicketState] = field(default_factory=dict)
    finish: dict = field(default_factory=dict)  # 08: PR·병합·main 검증·revert의 재개 지점
    phase: str = ""  # feature 전체 마무리 중이면 finish
    progress: dict = field(default_factory=dict)
    agy_calls: int = 0  # 이번 실행에서 gs가 띄운 agy 호출 수(worker 1번·리뷰 1번 = 1회, 재시도·수정·재리뷰 포함). 실행마다 0에서

    def ticket(self, tid: str) -> TicketState:
        return self.tickets.setdefault(tid, TicketState())


def reviews(ts: TicketState) -> list[dict]:
    """티켓의 리뷰 기록들: 첫 리뷰, 있으면 두 번째 리뷰. 빈 기록은 뺀다."""
    return [rec for rec in (ts.review, ts.second_review) if rec]


def agy_reached(st: State, limit: int) -> bool:
    """이번 실행의 agy 호출이 상한에 닿았나. 닿았으면 더 띄우지 않는다."""
    return st.agy_calls >= limit


PHASE_LABELS = {"worker": "worker", "review": "리뷰", "fix": "수정", "rereview": "재리뷰", "fix2": "수정 2",
                "verify": "검증", "finish": "마무리", "checks": "CI 대기", "setup": "준비"}


def end_phase(ts: TicketState, at: str | None = None) -> None:
    if ts.phases and not ts.phases[-1]["ended_at"]:
        ts.phases[-1]["ended_at"] = at or now()


def begin_phase(ts: TicketState, phase: str, model: str, *, attempt: int | None = None,
                at: str | None = None) -> None:
    at = at or now()
    end_phase(ts, at)
    if attempt is None:
        attempt = ts.phases[-1]["attempt"] if ts.phases else ts.attempts
    ts.phases.append({"attempt": attempt, "phase": phase, "model": model, "started_at": at, "ended_at": ""})


def seconds_between(start: str, end: str) -> float:
    a, b = parse_time(start), parse_time(end)
    return max(0, (b - a).total_seconds()) if a and b else 0


def minutes(seconds: float) -> int:
    """정수 분 반올림(정확히 30초도 올림)."""
    return int(max(0, seconds) / 60 + 0.5)


def phase_durations(ts: TicketState) -> dict[str, float]:
    totals = {}
    for p in ts.phases:
        if p["ended_at"]:
            phase = p["phase"]
            totals[phase] = totals.get(phase, 0) + seconds_between(p["started_at"], p["ended_at"])
    return totals


def load_eta_history(repo: Path, feature: str) -> float | None:
    """다른 feature의 merged 티켓 소요 중앙값(초). 로컬 실행 기록만 읽는다."""
    durations = []
    for p in (repo / ".goldstack" / "work").glob("*/run/state.json"):
        if p.parent.parent.name == feature:
            continue
        try:
            st = load(p.parent, p.parent.parent.name)
            samples = []
            for ts in st.tickets.values():
                if ts.status != MERGED:
                    continue
                starts = [start for phase in ts.phases
                          if (start := parse_time(phase["started_at"]))]
                start = min(starts) if starts else parse_time(ts.started_at)
                end = parse_time(ts.ended_at)
                if start and end and end >= start:
                    samples.append((end - start).total_seconds())
            durations.extend(samples)
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            continue  # 깨졌거나 읽을 수 없는 이력은 실행을 막지 않는다
    return median(durations) if durations else None


def calculate_progress(st: State, order: list[str], max_workers: int, *, prior=(),
                       models: dict[str, str] | None = None, at: str | None = None,
                       history_median_s: float | None = None) -> dict:
    """이번 실행 평균으로 ETA를 계산한다. 완료 표본이 없으면 이전 실행 중앙값을 쓴다."""
    at = st.finished_at or at or now()
    run_start = parse_time(st.started_at)
    terminal = (MERGED, FAILED, SKIPPED)
    done = sum(st.tickets[tid].status in terminal for tid in order)
    running, durations = [], []
    for tid in order:
        ts = st.tickets[tid]
        if ts.status == RUNNING and not st.finished_at:
            p = ts.phases[-1] if ts.phases else {}
            running.append({"id": tid, "phase": p.get("phase", "worker"),
                            "model": p.get("model", (models or {}).get(tid, ""))})
        if tid in prior or ts.status not in terminal or not ts.started_at or not ts.ended_at:
            continue
        # 시작 시각은 최신 worker의 것이라, 재시도를 포함한 첫 단계부터 잰다.
        starts = [start for p in ts.phases
                  if (start := parse_time(p["started_at"])) and run_start and start >= run_start]
        start = min(starts) if starts else parse_time(ts.started_at)
        end = parse_time(ts.ended_at)
        if start and end and run_start and start >= run_start:
            durations.append(max(0, (end - start).total_seconds()))
    if st.phase in ("finish", "setup") and not st.finished_at:
        # 빈 id는 개별 티켓이 아닌 feature 전체의 보고서·PR·base 검증을 뜻한다.
        phase = "setup" if st.phase == "setup" else "checks" if st.finish.get("phase") == "checks_pending" else "finish"
        running = [{"id": "", "phase": phase, "model": "claude" if phase == "finish" else ""}]
    total = len(order)
    historical = not durations and history_median_s is not None
    average = sum(durations) / len(durations) if durations else history_median_s
    eta = minutes(average * (total - done) / max(1, max_workers)) * 60 if average is not None else None
    elapsed = int(seconds_between(st.started_at, at))
    filled = 8 * done // total if total else 0
    parts = [f"{'▓' * filled}{'░' * (8 - filled)} {st.feature} {done}/{total}"]
    for p in running:
        label = PHASE_LABELS[p["phase"]]
        model = f"({p['model']})" if p["model"] else ""
        parts.append(f"{p['id'] + ' ' if p['id'] else ''}{label} 중{model}")
    eta_text = f"약 {eta // 60}분 남음" if eta is not None else "남은 시간 계산 중"
    if historical:
        eta_text += "(이전 실행 기준)"
    parts += [f"{minutes(elapsed)}분", eta_text]
    return {"done": done, "total": total, "running": running, "elapsed_s": elapsed, "eta_s": eta,
            "line": " · ".join(parts)}


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


ACQUIRE_TRIES = 10


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
        for i in range(ACQUIRE_TRIES):  # running_pid가 잠깐 잡는 공유 잠금과 겹쳤을 수 있어 몇 번 더 본다
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if i == ACQUIRE_TRIES - 1:
                    os.close(fd)
                    raise Locked(_read_pid(self.path)) from None
                time.sleep(0.02)
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


def _held(p: Path) -> bool:
    """누군가 잠금을 잡고 있나. 공유 잠금을 잡아 보고 바로 푼다(파일을 만들거나 바꾸지 않는다)."""
    try:
        fd = os.open(p, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def running_pid(rundir: Path) -> int | None:
    """지금 이 feature에 `gs go`가 돌고 있으면 그 pid(잠금은 잡혔는데 pid를 아직 안 적었으면 -1). 아니면 None.

    판단은 잠금이 잡혀 있는지로 한다. lock 파일의 pid는 보여 주기용이다(죽은 gs의 pid는 재사용될 수 있다).
    """
    p = lock_path(rundir)
    if not _held(p):
        return None
    for _ in range(5):  # 잡은 직후 pid를 쓰는 사이일 수 있다
        pid = _read_pid(p)
        if pid:
            return pid
        time.sleep(0.02)
    return -1
