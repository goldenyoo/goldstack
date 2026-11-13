"""spec의 verify 명령 실행. 티켓 병합 전, integration, integration-final, main·main-retry·main-recheck가 모두 이것을 쓴다.

명령은 새 프로세스 그룹(`start_new_session`)에서 `bash -c '<verify>' gs-verify:<로그 경로>`로 돈다(verify 뒤에 KEEP_BASH가 붙는다). 시간 = `GS_VERIFY_TIMEOUT`(초, 시험 seam)이
있으면 그것, 없으면 spec `verify_minutes` × 60. 넘기면 그룹 전체에 SIGTERM, GRACE초 뒤 남았으면 SIGKILL을 보낸다.
`subprocess.run(timeout=)`은 bash만 죽이고 그 자손(pytest 등)은 남기 때문에 그룹으로 끝낸다.
한 번 돌 때마다 로그 끝에 `종료 코드: <N>` 줄을 남긴다. 통과도 시간 초과도 같다(시간 초과는 `시간 초과: <N>분` 줄 뒤다).

끊김(Result.interrupted)은 명령이 신호로 죽은 것처럼 보이는 실패다: 종료 코드가 음수거나(bash가 죽음) 128보다 크거나(bash의 자식이 죽음),
이번 실행의 출력에 줄 처음부터 SIGNAL_LINE 형태가 있다. xargs는 띄운 자식이 신호로 죽으면 그 줄을 남기고 나머지 자식을 기다려 1로 끝나서 종료 코드만으로는 가르지 못한다.
앞선 재시도의 출력은 보지 않는다. 통과와 시간 초과는 끊김이 아니다. `uv run`처럼 자식의 신호를 종료 코드로 옮기는 명령을 xargs가 띄우면 줄이 남지 않아 일반 실패로 보인다(실측).
끊기면 남은 그룹을 끝낸다: bash나 xargs가 신호로 죽으면 돌던 자식이 남는데(실측), 그 자식이 다음 검증과 같은 트리를 함께 쓰고 로그 끝 뒤에 이어 쓰지 않게 한다.
끊김을 어떻게 할지는 부르는 쪽이 정한다: 티켓 검증은 수리 없이 한 번 다시 돌리고(go._verify_interrupted), 마무리 검증은 여느 실패와 같다.

표지(mark): gs만 SIGKILL로 죽으면 새 세션의 검증은 살아 남아 다음 gs go의 검증과 같은 트리를 함께 바꾼다. 번호를 저장하지 않고 명령줄의 표지로 찾는다(worker.kill_script와 같은 방식).
표지는 그 검증의 로그 경로라 검증마다 다르고, run 디렉터리 아래라 어느 feature의 것인지 드러난다. 다음 gs go가 잠금을 잡자마자 stop_stale로 그 run의 표지를 모두 끝낸다.
같은 run의 다른 검증도 끝내는 이유: 티켓 검증과 integration 검증은 같은 worktree를 쓰는데 재개 뒤 어느 검증이 먼저 돌지 모른다. 한 feature에 gs go는 하나이고 검증은 한 번에 하나라, 잠금을 잡은 때 살아 있는 검증은 모두 옛 것이다.
못 찾는 것: 검증이 스스로 `exec`로 bash를 대신했거나, bash만 먼저 죽고 자식이 남은 그룹. 명령줄에 표지가 없다.

판별(triage, config `[verify]`, goldstack-v31 02): 바뀐 코드와 무관한 시험 하나의 1회성 실패로 검증이 떨어지지 않게 한다. 실패한 시험 파일을 따로 돌리는 것은 판별에만 쓰고,
통과 판정은 언제나 전체 명령이 한다(따로 돌려 통과해도 `&&` 사슬의 뒤 명령, 정규식이 못 뽑는 import 오류를 전체 재실행이 다시 본다). 한 시도는 이렇다:
1. 전체 명령이 실패했고(`Result.ok`가 아님) 시간 초과·끊김이 아니면, 그 실행의 출력만(앞 시도·gs가 먼저 쓴 머리말은 빼고)에 `failed_file`을 re.MULTILINE으로 맞춰 첫 그룹을 모으고 중복을 뺀다.
2. 매치가 없거나, `max_files`를 넘거나, 값이 SAFE_FILE이 아니거나(셸 명령 틀에 그대로 들어간다. 따옴표로 막지 않고 값을 제한한다), 호출자의 확인 함수(`unchanged`)가
   트리가 바뀌었다고 하거나 그 함수가 없으면 판별하지 않는다. 로그에 `판별 안 함: <이유>` 한 줄을 남기고 실패 그대로다.
3. 파일마다 `rerun`의 `{file}`을 그 값으로 바꿔 같은 cwd·환경·표지로 돌린다. 판별 실행들은 검증 시간(limit_seconds) 하나를 나눠 쓴다. 하나라도 `Result.ok`가
   아니면(시간 초과는 종료 0이어도) 판별 실패이고 실패 그대로다. 판별 실행의 끝 줄은 `판별 종료 코드: <N>`이다(`종료 코드:` 줄은 전체 명령에만 쓴다).
4. 모두 통과하고 확인 함수가 트리 그대로라고 하면 전체 명령을 한 번 더 돈다. 그 결과가 이 시도의 결과다(`Result.triaged`에 파일들). 통과를 받아들일지는
   호출자가 트리를 보고 정하고, 받아들이면 flaky가 `flaky: <label> <파일들> 따로 돌려 통과, 전체 다시 통과`를 쓴다.
verify_retries와 함께 쓰면 시도마다 판별을 먼저 한다. 전체를 한 번 더 도는 것은 재시도와 별개로 시도당 한 번이고, 그 결과는 다시 판별하지 않는다.
따로 돌린 파일이 시간 안에 신호 없이 실패하면 결정적 실패로 보고 남은 재시도 없이 그 시도의 결과를 돌려준다. 판별을 못 했거나 꺼져 있으면,
판별 파일이 시간 초과(판별 시간 예산 소진 포함)·끊김으로 끝났으면, 판별 통과 뒤 전체가 다시 실패했으면 verify_retries만큼 재시도한다.
재시도 전에도 확인 함수를 부르고 트리가 바뀌었으면 `검증 재시도 안 함: …` 줄을 남기고 더 돌리지 않는다. 판별이나 앞 실행이 바꾼 트리를 다음 실행이 되돌려
호출자의 최종 비교를 통과하는 일을 막는다. 그 시도의 실패 결과를 돌려주고 바뀐 트리는 손대지 않는다(트리 변경 판정은 호출자의 비교가 한다).
설정은 호출자가 실행 중인 config 값을 넘긴다(검증하는 worktree의 config를 읽지 않는다). 측정 키는 metrics.sample·metrics.triage가 적는다.

취소(cancel, goldstack-v37 01): 티켓 검증은 루프 밖 스레드에서 돈다(go._merge_step). 부른 쪽이 루프를 떠나면 cancel(threading.Event)을 세운다.
도는 명령은 CANCEL_TICK마다, 그리고 셸이 끝났을 때 그것을 보고, 서 있으면 프로세스 그룹을 끝내고(stop) Cancelled를 올린다. 명령을 띄우기 전에도 보고 서 있으면 띄우지 않는다:
판별 파일, 판별 뒤 전체 실행, 재시도 어느 것이든 다음 명령이 나가지 않는다. 취소된 검증은 결과가 없어 로그 끝에 `종료 코드:` 줄이 없다. cancel이 없으면 전처럼 끝까지 기다린다.
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import IO, Callable
from urllib.parse import quote

from . import metrics
from .feature import WORK

GRACE = 5.0  # SIGTERM 뒤 SIGKILL까지 기다리는 초
# 신호로 죽은 자식을 알리는 줄. xargs 문구는 macOS xargs 실측 값이다(`xargs: sleep: terminated with signal 15; aborting`, 종료 코드 1). 리눅스 xargs는 재지 않았다
SIGNAL_LINE = re.compile(r"^(?:xargs: .*terminated with signal \d+|killed by signal \d+)", re.MULTILINE)
MARK = "gs-verify:"
# bash -c는 마지막 단순 명령을 exec로 대신해 표지가 ps에서 사라진다(`bash -c 'sleep 7' 표지`의 ps는 `sleep 7`뿐이다. 실측). 뒤에 명령을 남겨 bash가 끝까지 있게 한다.
# 종료 코드는 그대로다. 그 명령이 신호로 죽으면 음수 대신 128+N인데 둘 다 끊김이다. 줄바꿈이어야 verify 끝의 주석·`&`에도 붙는다
KEEP_BASH = "\nexit $?"
MARKED_ROW = re.compile(r"^bash -c .*exit \$\? (" + MARK + r"\S+)$")  # 줄바꿈은 ps가 바꿔 보인다(macOS `\012`). 표지는 공백이 없어 마지막 낱말이다
PS_SECONDS = 30.0
SAFE_FILE = re.compile(r"[A-Za-z0-9_.-]+")  # 판별에 쓸 수 있는 시험 파일 값. 이것만 rerun의 {file} 자리에 넣는다
CANCEL_TICK = 0.2  # 도는 명령이 취소(cancel)를 보는 간격(초)


class Cancelled(Exception):
    """부른 쪽이 검증을 취소했다(cancel). 돌던 명령의 프로세스 그룹은 끝냈고 다음 명령은 띄우지 않았다. 검증 실패가 아니다: 결과가 없다."""


@dataclass(frozen=True)
class Result:
    code: int  # 시간 초과면 끝낸 bash의 종료 코드(음수 = 시그널)
    timed_out: bool
    minutes: str  # 시간 제한(분). 로그·실패 이유에 쓴다
    retries: int = 0  # 첫 실행을 제외하고 다시 돌린 횟수
    samples: tuple[dict, ...] = field(default=(), compare=False)  # 재시도까지 각 명령의 시간·결과
    interrupted: bool = False  # 이 실행이 신호로 끊긴 것처럼 보인다. 시간 초과는 timed_out이고 끊김이 아니다
    triaged: tuple[str, ...] = ()  # 따로 돌려 통과한 시험 파일. 있으면 이 결과는 판별 뒤 전체를 한 번 더 돈 것이다
    launch_failed: bool = False

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out


@dataclass(frozen=True)
class _TriageResult:
    files: tuple[str, ...] = ()  # 모두 통과하고 트리가 그대로여서 전체를 한 번 더 돌릴 파일들
    deterministic_failure: bool = False  # 시간 초과·끊김 없이 실패해 verify_retries도 멈춘다


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


def mark(path) -> str:
    """이 경로의 검증 표지. ps는 로캘에 따라 비ASCII를 바꿔 보이므로(macOS LC_ALL=C: `M-m...`, 실측) ASCII로 적는다."""
    return MARK + quote(os.path.realpath(path), safe="/")


def run(spec, cwd: Path, stream: IO[str], triage=None, unchanged: Callable[[], bool] | None = None,
        cancel: threading.Event | None = None) -> Result:
    """실패한 명령을 최대 verify_retries만큼 다시 돌린다. 각 실행의 시간 제한은 같다. 돌려주는 결과는 마지막 전체 실행의 것이고, 실행마다 로그 끝에 종료 코드 줄을 남긴다.

    triage는 config `[verify]`(config.VerifyConfig), unchanged는 트리가 검증 전 그대로면 True인 함수다. 둘 다 있고 triage가 켜져 있으면 시도마다 판별하고(머리말),
    따로 돌린 파일이 시간 초과·끊김 없이 실패하면 남은 재시도를 멈춘다. 판별 생략·꺼짐, 판별 파일의 시간 초과·끊김, 판별 통과 뒤 전체 실패는 재시도한다.
    재시도 전에도 unchanged를 불러 트리가 바뀌었으면 더 돌리지 않고 그 시도의 실패 결과를 돌려준다(바뀐 트리는 그대로 두어 호출자의 최종 비교가 본다).
    cancel이 서면 도는 명령의 프로세스 그룹을 끝내고 Cancelled를 올린다. 다음 명령(판별·판별 뒤 전체·재시도)은 띄우지 않는다(머리말)."""
    samples = []
    on = triage is not None and triage.enabled
    attempt = 0
    while True:
        offset = _offset(stream)
        result = _full(spec, cwd, stream, samples, cancel=cancel)
        outcome = _TriageResult()
        if not result.ok and on:
            outcome = _triage(spec, cwd, stream, triage, unchanged, result, _output(stream, offset), samples, cancel)
            if outcome.files:
                result = replace(_full(spec, cwd, stream, samples, after_triage=True, cancel=cancel), triaged=outcome.files)
        if result.ok or attempt >= getattr(spec, "verify_retries", 0):
            break
        if on and unchanged is not None and not unchanged():
            stream.write("\n검증 재시도 안 함: 검증 중 트리가 바뀌었다\n")
            break
        if outcome.deterministic_failure:
            break
        if cancel is not None and cancel.is_set():  # 재시도 줄도 쓰지 않는다: 돌지 않을 재시도다
            raise Cancelled("검증을 다시 돌리지 않는다: 취소됐다")
        attempt += 1
        stream.write(f"\n검증 재시도 {attempt}\n")
    return replace(result, retries=attempt, samples=tuple(samples))


def flaky(result: Result, label: str, stream: IO[str]) -> None:
    """재시도·판별 성공은 원본 로그에 남겨 보고서의 수집 증거에도 들어가게 한다. 판별로 통과했으면 재시도 줄 대신 판별 줄만 쓴다."""
    if result.ok and result.triaged:
        stream.write(f"\nflaky: {label} {' '.join(result.triaged)} 따로 돌려 통과, 전체 다시 통과\n")
    elif result.ok and result.retries:
        stream.write(f"\nflaky: {label} 재시도 {result.retries}번 만에 통과\n")


def _full(spec, cwd: Path, stream: IO[str], samples: list, *, after_triage: bool = False,
          cancel: threading.Event | None = None) -> Result:
    """전체 명령 한 번. 로그 끝에 종료 코드 줄, 측정에 표본 하나. 취소되면 둘 다 없이 Cancelled다."""
    start = metrics.clock()
    result = _run_once(spec, cwd, stream, *_given(cancel))
    stream.write(f"\n종료 코드: {result.code}\n")
    stream.flush()
    metrics.sample(samples, start, result, after_triage=after_triage)
    return result


def failed_files(pattern: str, output: str) -> tuple[str, ...]:
    """출력에서 pattern(re.MULTILINE)의 첫 그룹을 나온 순서대로, 중복 없이. 그룹이 맞지 않은 매치는 빈 문자열이다(SAFE_FILE이 아니라 판별하지 않는다)."""
    found: dict[str, None] = {}
    for m in re.compile(pattern, re.MULTILINE).finditer(output):
        found.setdefault(m.group(1) or "", None)
    return tuple(found)


def _triage(spec, cwd: Path, stream: IO[str], triage, unchanged, result: Result, output: str, samples: list,
            cancel: threading.Event | None = None) -> _TriageResult:
    """판별(머리말 1–3). 전체를 한 번 더 돌릴 파일들과 재시도를 멈출 결정적 실패 여부를 돌려준다. 측정은 실패한 전체 실행의 표본에 붙인다."""
    start = metrics.clock()

    def skip(reason: str, why: str, files: tuple[str, ...] = ()) -> _TriageResult:
        stream.write(f"\n판별 안 함: {why}\n")
        metrics.triage(samples, "skipped", files, reason, start)
        return _TriageResult()

    if result.timed_out:
        return skip("timeout", "전체 검증이 시간 초과로 끝났다")
    if result.interrupted:
        return skip("interrupted", "전체 검증이 끊겼다")
    files = failed_files(triage.failed_file, output)
    if not files:
        return skip("no_match", "출력에서 failed_file에 맞는 실패 시험 파일을 찾지 못했다")
    if len(files) > triage.max_files:
        return skip("too_many", f"실패한 시험 파일 {len(files)}개가 max_files {triage.max_files}개보다 많다: {' '.join(files)}", files)
    bad = next((name for name in files if not SAFE_FILE.fullmatch(name)), None)
    if bad is not None:
        return skip("bad_value", f"시험 파일 값 {bad!r}에 [A-Za-z0-9_.-] 밖 문자가 있다", files)
    if unchanged is None:
        return skip("no_check", "트리를 확인할 함수가 없다", files)
    if not unchanged():
        return skip("tree_changed", "검증 중 트리가 바뀌었다", files)
    total = limit_seconds(spec)
    deadline = _clock() + total
    for name in files:
        command = triage.rerun.replace("{file}", name)
        stream.write(f"\n판별 {name}: $ {command}\n")
        left = deadline - _clock()
        if left > 0:
            res = _launch(command, left, cwd, stream, *_given(cancel))
        else:
            stream.write(f"판별 시간({minutes(total)}분)을 다 써서 돌리지 않았다\n")
            res = Result(1, True, minutes(total))
        stream.write(f"\n판별 종료 코드: {res.code}\n")
        if not res.ok:
            stream.write(f"\n판별 실패: {name}" + (" 시간 초과" if res.timed_out else "") + ". 전체 검증은 다시 돌리지 않는다\n")
            metrics.triage(samples, "failed", files, name, start)
            return _TriageResult(deterministic_failure=not res.timed_out and not res.interrupted and not res.launch_failed)
    if not unchanged():
        stream.write("\n판별 통과, 전체 검증은 다시 돌리지 않는다: 판별 중 트리가 바뀌었다\n")
        metrics.triage(samples, "passed", files, "tree_changed", start)
        return _TriageResult()
    stream.write(f"\n판별 통과: {' '.join(files)}. 전체 검증을 한 번 더 돌린다\n")
    stream.flush()
    metrics.triage(samples, "passed", files, "", start)
    return _TriageResult(files=files)


def _given(cancel: threading.Event | None) -> tuple[threading.Event, ...]:
    """취소 통로는 있을 때만 넘긴다. 없으면 _run_once·_launch를 옛 서명 그대로 부른다(시험이 그 둘을 바꿔 끼운다)."""
    return () if cancel is None else (cancel,)


def _clock() -> float:
    """판별 시간 예산의 시계. 시험이 바꾼다."""
    return time.monotonic()


def _run_once(spec, cwd: Path, stream: IO[str], cancel: threading.Event | None = None) -> Result:
    """spec.verify를 cwd에서 spec의 시간 제한으로 돌린다(_launch)."""
    return _launch(spec.verify, limit_seconds(spec), cwd, stream, *_given(cancel))


def _launch(command: str, seconds: float, cwd: Path, stream: IO[str], cancel: threading.Event | None = None) -> Result:
    """command를 cwd에서 돌려 출력을 stream에 쓴다. 시간을 넘기면 끝에 `시간 초과: <N>분` 줄을 남긴다. 끊겼으면 남은 그룹을 끝낸다.

    cancel이 이미 서 있으면 띄우지 않고 Cancelled, 도는 중에 서면 그룹을 끝내고 Cancelled다(_wait)."""
    limit = minutes(seconds)
    if cancel is not None and cancel.is_set():
        raise Cancelled(f"검증 명령을 띄우지 않는다: 취소됐다(`{command}`)")
    stream.flush()
    try:
        start = os.lseek(stream.fileno(), 0, os.SEEK_CUR)  # 자식과 함께 쓰는 위치다. 여기부터가 이번 실행의 출력이다
        p = subprocess.Popen(["bash", "-c", command + KEEP_BASH, mark(_log_path(stream, cwd))], cwd=cwd, stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, env=env(), start_new_session=True)
    except OSError as e:
        stream.write(f"검증 명령 실행 실패: {e}\n")
        return Result(1, False, limit, launch_failed=True)
    try:
        code = _wait(p, seconds, cancel)
        interrupted = _interrupted(code, stream, start)
        if interrupted:
            stop(p)
        return Result(code, False, limit, interrupted=interrupted)
    except subprocess.TimeoutExpired:
        code = stop(p)
        stream.write(f"\n시간 초과: {limit}분\n")
        stream.flush()
        return Result(code, True, limit)
    except BaseException:
        stop(p)  # 코디네이터가 죽어도(Ctrl-C 등), 취소돼도(Cancelled) 검증 프로세스를 남기지 않는다
        raise


def _wait(p: subprocess.Popen, seconds: float, cancel: threading.Event | None) -> int:
    """p가 끝나기를 seconds까지 기다려 종료 코드를 돌려준다. 넘기면 TimeoutExpired. cancel이 있으면 CANCEL_TICK마다 보고, 서 있으면 Cancelled(그룹은 _launch가 끝낸다).
    셸이 끝난 뒤에도 본다: 취소 뒤 셸이 스스로 끝났어도 그룹에 남은 자식이 있을 수 있다."""
    if cancel is None:
        return p.wait(timeout=seconds)
    deadline = time.monotonic() + seconds
    while True:
        try:
            code = p.wait(timeout=max(0.0, min(deadline - time.monotonic(), CANCEL_TICK)))
        except subprocess.TimeoutExpired:
            if cancel.is_set():
                raise Cancelled("검증 명령을 끝낸다: 취소됐다") from None
            if time.monotonic() >= deadline:
                raise
            continue
        if cancel.is_set():
            raise Cancelled("검증 명령이 끝났지만 취소됐다: 남은 그룹을 끝낸다")
        return code


def _log_path(stream: IO[str], cwd: Path):
    """표지에 쓸 경로. 이름 없는 파일이면 cwd다."""
    try:
        return os.fspath(stream.name)
    except (AttributeError, TypeError):
        return cwd


def _interrupted(code: int, stream: IO[str], start: int) -> bool:
    """제 시간에 끝난 실행이 신호로 끊긴 것처럼 보이나. 통과는 출력과 상관없이 끊김이 아니다. 로그는 종료 코드로 가리지 못할 때만 읽는다."""
    if code == 0:
        return False
    return code < 0 or code > 128 or SIGNAL_LINE.search(_output(stream, start)) is not None


def _offset(stream: IO[str]) -> int | None:
    """stream 파일의 지금 쓰기 위치. 이 뒤가 다음 실행의 출력이다. 파일이 아니면 None."""
    try:
        stream.flush()
        return os.lseek(stream.fileno(), 0, os.SEEK_CUR)
    except (OSError, ValueError, AttributeError):
        return None


def _output(stream: IO[str], start: int | None) -> str:
    """stream의 파일에서 start부터 끝까지(stream은 쓰기 전용이라 다시 연다). 읽지 못하면 빈 문자열이고 끊김은 종료 코드로만 판단한다(판별은 매치 없음)."""
    if start is None:
        return ""
    try:
        with open(stream.name, "rb") as f:
            f.seek(start)
            return f.read().decode("utf-8", errors="replace")
    except (AttributeError, TypeError, OSError):
        return ""


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


def stop_stale(rundir: Path) -> list[str]:
    """rundir 아래 표지를 단 지난 검증의 프로세스 그룹을 끝내고(SIGTERM, 안 끝나면 SIGKILL) 출력할 줄을 돌려준다. 없으면 빈 목록.

    잠금을 잡은 gs go만 부른다. 찾거나 끝내지 못해도 예외를 내지 않고 경고 줄로 돌려준다: 새 실행을 멈출 이유가 아니다.
    """
    try:
        groups = _marked_groups(rundir)
    except Exception as e:  # noqa: BLE001 — 최선. 위와 같다
        return [f"경고: 지난 실행의 검증을 찾지 못했다: {type(e).__name__}: {e}"]
    lines = []
    for pgid, found in sorted(groups.items()):
        try:
            ended = _end_group(pgid)
        except Exception as e:  # noqa: BLE001 — 최선. 위와 같다
            lines.append(f"경고: 지난 실행의 검증을 끝내지 못했다: 프로세스 그룹 {pgid}({found}): {type(e).__name__}: {e}")
            continue
        lines.append(f"지난 실행의 검증이 아직 돌고 있어 끝냈다: 프로세스 그룹 {pgid}({found})" if ended
                     else f"경고: 지난 실행의 검증을 끝내지 못했다: 프로세스 그룹 {pgid}({found})")
    return lines


def _marked_groups(rundir: Path) -> dict[int, str]:
    """{프로세스 그룹: 표지}. `/`까지 대조해 `run2`나 다른 feature를 잡지 않는다. gs 자신의 그룹은 끝내지 않는다.

    worktree도 레포 루트가 되어(feature.find_repo_root) 다른 feature의 run이 rundir 아래에 생길 수 있다. 그 run은 잠금이 따로라 옛 검증으로 볼 수 없으므로, rundir 뒤에 WORK가 또 나오는 표지는 잡지 않는다.
    """
    under = mark(rundir) + "/"
    other_run = f"/{WORK}/"
    groups = {}
    for pgid, stat, command in _ps():
        row = MARKED_ROW.match(command)
        if row and row[1].startswith(under) and other_run not in row[1][len(under) - 1:] and not stat.startswith("Z") and pgid not in (0, 1, os.getpgrp()):
            groups[pgid] = row[1]
    return groups


def _end_group(pgid: int) -> bool:
    """이 프로세스의 자식이 아니라 거둘 수 없으니 ps로 살아 있는지 본다. 끝났으면 True."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        _signal(pgid, sig)
        deadline = time.monotonic() + GRACE
        while _group_alive(pgid):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
        else:
            return True
    return False


def _group_alive(pgid: int) -> bool:
    """좀비는 죽은 것으로 본다."""
    return any(group == pgid and not stat.startswith("Z") for group, stat, _ in _ps())


def _ps() -> list[tuple[int, str, str]]:
    """[(프로세스 그룹, stat, 명령줄)]. ps가 실패하면 예외다."""
    cp = subprocess.run(["ps", "-A", "-ww", "-o", "pgid=,stat=,command="], capture_output=True, stdin=subprocess.DEVNULL, timeout=PS_SECONDS)
    if cp.returncode:
        raise OSError(f"ps 종료 코드 {cp.returncode}: {cp.stderr.decode('utf-8', errors='replace').strip()}")
    rows = []
    for line in cp.stdout.decode("utf-8", errors="replace").split("\n"):
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit():
            rows.append((int(parts[0]), parts[1], parts[2] if len(parts) > 2 else ""))
    return rows
