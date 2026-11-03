"""`gs status [<feature>]`: state.json을 표로 보여 준다. 읽기 전용이다(파일을 만들거나 바꾸지 않고, 잠그지도 않는다)."""
from __future__ import annotations

import unicodedata
from datetime import datetime
from pathlib import Path

from . import state

LABEL = {"pending": "대기", "running": "실행 중", "merged": "병합", "failed": "실패", "skipped": "건너뜀"}


def status(repo: Path, name: str | None, out) -> int:
    work = repo / ".work"
    if name is not None:
        if not (work / name).is_dir():
            print(f"gs status: .work/{name}이 없다", file=out)
            return 1
        names = [name]
    else:
        recorded = sorted(p.parent.parent.name for p in work.glob("*/run/state.json"))
        names = [n for n in recorded if state.running_pid(work / n / "run")]
        if not names:
            print("실행 중인 feature가 없다.", file=out)
            if recorded:
                print(f"지난 실행 기록: {', '.join(recorded)} (gs status <feature>로 본다)", file=out)
            return 0
    for i, n in enumerate(names):
        if i:
            print(file=out)
        _show(work / n / "run", n, out)
    return 0


def _show(rundir: Path, name: str, out) -> None:
    if not state.path(rundir).exists():
        print(f"{name}: 실행 기록이 없다({state.path(rundir)} 없음)", file=out)
        return
    st = state.load(rundir, name)
    pid = state.running_pid(rundir)
    now = datetime.now().astimezone()
    if pid:
        head = f"{name}: 실행 중(pid {pid})"
    elif st.finished_at:
        head = f"{name}: 끝남({_clock(state.parse_time(st.finished_at), now)})"
    else:
        head = f"{name}: 중단됨(gs go pid {st.pid}가 끝을 남기지 않고 사라졌다)"
    head += f" · 시작 {_clock(state.parse_time(st.started_at), now)}"
    if st.only:
        head += f" · 범위 {','.join(st.only)}"
    print(head, file=out)

    rows = [("티켓", "상태", "시도", "경과", "마지막 출력", "이유")]
    for tid, ts in sorted(st.tickets.items()):
        label = LABEL.get(ts.status, ts.status)
        if ts.status == state.RUNNING and not pid:
            label += "(중단)"
        rows.append((tid, label, str(ts.attempts), _elapsed(ts, pid is not None, st, now),
                     _last_output(ts.log, now), ts.reason))
    widths = [max(_width(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    for r in rows:
        cells = [_pad(c, w) for c, w in zip(r, widths)] + [r[-1]]
        print("  ".join(cells).rstrip(), file=out)


def _elapsed(ts: state.TicketState, live: bool, st: state.State, now: datetime) -> str:
    start = state.parse_time(ts.started_at)
    if start is None:
        return "-"
    end = state.parse_time(ts.ended_at)
    if end is None:
        end = now if live and ts.status == state.RUNNING else state.parse_time(st.updated_at)
    if end is None:
        return "-"
    return duration((end - start).total_seconds())


def _last_output(log: str, now: datetime) -> str:
    if not log:
        return "-"
    try:
        mtime = Path(log).stat().st_mtime
    except OSError:
        return "-"
    t = datetime.fromtimestamp(mtime).astimezone()
    return f"{_clock(t, now)} ({duration((now - t).total_seconds())} 전)"


def duration(seconds: float) -> str:
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _clock(t: datetime | None, now: datetime) -> str:
    if t is None:
        return "-"
    return t.strftime("%H:%M:%S") if t.date() == now.date() else t.strftime("%m-%d %H:%M")


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, w: int) -> str:
    return s + " " * (w - _width(s))
