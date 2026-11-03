"""spec의 verify 명령 실행. 티켓 병합 전, integration, integration-final, main·main-recheck가 모두 이것을 쓴다.

명령은 새 프로세스 그룹(`start_new_session`)에서 `bash -c`로 돈다. 시간 = `GS_VERIFY_TIMEOUT`(초, 시험 seam)이
있으면 그것, 없으면 spec `verify_minutes` × 60. 넘기면 그룹 전체에 SIGTERM, GRACE초 뒤 남았으면 SIGKILL을 보낸다.
`subprocess.run(timeout=)`은 bash만 죽이고 그 자손(pytest 등)은 남기 때문에 그룹으로 끝낸다.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

GRACE = 5.0  # SIGTERM 뒤 SIGKILL까지 기다리는 초


@dataclass(frozen=True)
class Result:
    code: int  # 시간 초과면 끝낸 bash의 종료 코드(음수 = 시그널)
    timed_out: bool
    minutes: str  # 시간 제한(분). 로그·실패 이유에 쓴다

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out


def limit_seconds(spec) -> float:
    raw = os.environ.get("GS_VERIFY_TIMEOUT", "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return spec.verify_minutes * 60


def minutes(seconds: float) -> str:
    m = seconds / 60
    return str(int(m)) if m == int(m) else f"{m:.2f}".rstrip("0").rstrip(".")


def env() -> dict[str, str]:
    """gs 자신의 가상환경·worker 표시는 verify에 물려주지 않는다."""
    return {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "GS_ROLE")}


def run(spec, cwd: Path, stream: IO[str]) -> Result:
    """spec.verify를 cwd에서 돌려 출력을 stream에 쓴다. 시간을 넘기면 끝에 `시간 초과: <N>분` 줄을 남긴다."""
    seconds = limit_seconds(spec)
    limit = minutes(seconds)
    stream.flush()
    try:
        p = subprocess.Popen(["bash", "-c", spec.verify], cwd=cwd, stdin=subprocess.DEVNULL, stdout=stream,
                             stderr=subprocess.STDOUT, env=env(), start_new_session=True)
    except OSError as e:
        stream.write(f"검증 명령 실행 실패: {e}\n")
        return Result(1, False, limit)
    try:
        return Result(p.wait(timeout=seconds), False, limit)
    except subprocess.TimeoutExpired:
        code = stop(p)
        stream.write(f"\n시간 초과: {limit}분\n")
        stream.flush()
        return Result(code, True, limit)
    except BaseException:
        stop(p)  # 코디네이터가 죽어도(Ctrl-C 등) 검증 프로세스를 남기지 않는다
        raise


def stop(p: subprocess.Popen) -> int:
    """p의 프로세스 그룹에 SIGTERM, GRACE초 뒤 남았으면 SIGKILL. bash의 종료 코드를 돌려준다."""
    pgid = p.pid  # start_new_session이라 그룹 id = bash pid
    if _signal(pgid, signal.SIGTERM):
        deadline = time.monotonic() + GRACE
        while time.monotonic() < deadline:
            p.poll()  # 그룹 리더가 좀비로 남아 그룹이 살아 보이지 않게 거둔다
            if not _signal(pgid, 0):
                break
            time.sleep(0.05)
        else:
            _signal(pgid, signal.SIGKILL)
    return p.wait()


def _signal(pgid: int, sig: int) -> bool:
    """그룹에 시그널을 보낸다. 그룹에 프로세스가 없으면 False."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except PermissionError:  # macOS: 좀비만 남은 그룹
        return False
    return True
