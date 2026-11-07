"""실행 상태 `.goldstack/work/<f>/run/state.json`과 실행 잠금 `.goldstack/work/<f>/run/lock`.

상태의 원천은 state.json 하나다(ORIGINS 실패 3). `gs go`의 요약·PR 본문과 `gs status`가 모두 이것을 읽는다.
고치는 것은 go._loop의 스레드뿐이다. 리뷰 스레드는 결과를 돌려주고 호출 도중의 대기·측정은 루프에 넘긴다(review.CallWait).
쓰기는 같은 디렉터리의 임시 파일에 쓴 뒤 rename한다. 읽는 쪽은 반쯤 쓴 파일을 보지 않는다.

잠금은 lock 파일에 대한 flock이다. 프로세스가 죽으면 커널이 풀어 주므로 죽은 프로세스의 잠금은 저절로 회수된다.
lock 파일에는 잡은 프로세스의 pid를 적어 둔다(보여 주기용). 정상 종료 때는 내용을 비운다(파일은 지우지 않는다:
지우면 같은 이름의 다른 inode를 두 프로세스가 각자 잠그는 틈이 생긴다).
'돌고 있나'는 잠금이 실제로 잡혀 있는지로 판단한다. 적힌 pid만 믿으면 죽은 gs의 pid가 재사용됐을 때 속는다.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

from . import transient

PENDING, RUNNING, MERGED, FAILED, SKIPPED = "pending", "running", "merged", "failed", "skipped"
STATUSES = (PENDING, RUNNING, MERGED, FAILED, SKIPPED)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def after(seconds: float) -> str:
    """지금부터 seconds 뒤의 시각."""
    return (datetime.now().astimezone() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


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
    isolation_warnings: list[str] = field(default_factory=list)  # 지난 시도·수정 worker의 격리 실패도 보존
    failure_summary: str = ""  # 재시도 brief에 붙일 판단 모델 요약 파일
    # 마지막 시도의 리뷰 기록(06, review.run): reviewer, dir, merge_base, note, fix, findings, reviewed_head.
    # reviewed_head는 이 리뷰어를 부른 마지막 리뷰·재리뷰의 대상 head다(go가 적는다). 호출이 실패해도 남고 실패는 note·failed가 말한다.
    # 부르지 못한 리뷰(거부, 한도, 트리 실패)는 옮기지 않는다. 옛 state의 기록에는 없다.
    # 재리뷰가 있었으면 rereviews(회차마다 round, dir, base, head, note, failed)도 있다. 수리 재리뷰의 round는 review.REPAIR_ROUND다.
    # kept_round는 catch-up 뒤 빈 diff에서 앞 판정을 유지한 재리뷰 회차다(go._empty_rereview). 지적에 결과를 새로 적으면(한도·오류의 unchecked도) 지운다. 없으면 유지한 적 없다(옛 state도 그렇다).
    # 지적마다 severity·location·claim·evidence·action(fix|report)·why, 그리고 수정·재리뷰 결과(review.Finding):
    #   fix_attempt("" | attempted | discarded), fix_round(이 지적을 받은 마지막 수정 worker 회차, 0이면 받은 적 없음),
    #   fix_reason(수정 못 한 이유: 한도, 띄우지 못함, 수정 worker 실패…),
    #   rereview("" | resolved | unresolved | unchecked), rereview_reason(unchecked의 이유: 시간 초과 | 한도 | 재리뷰 실패),
    #   rereview_evidence(판정 근거·실패 내용), rereview_round(그 결과를 낸 재리뷰 회차),
    #   found_round(0 첫 리뷰, 1·2 그 회차 재리뷰가 새로 낸 지적. 2회차는 늘 report. review.REPAIR_ROUND는 수리 재리뷰의 지적으로 늘 report),
    #   idea_number(보고만 high·medium 지적의 아이디어 파일 번호, findings.py. 옛 state와 정하기 전에는 없다).
    # 지적 하나의 결말은 이 순서로 읽는다: action이 report면 보고만 → rereview가 있으면 그 값(2차 수정을 못 했거나 버렸어도
    # 1차 재리뷰의 unresolved는 그대로 미해결이다) → fix_reason이 있으면 수정 못 함.
    review: dict = field(default_factory=dict)
    # 두 번째 리뷰(second_reviewer)의 기록. 모양은 review와 같다. second_reviewer가 없는 티켓은 비어 있다
    second_review: dict = field(default_factory=dict)
    # 단계 전환마다 추가한다. attempt는 worker 실행 디렉터리 번호(중단 재개 때도 재사용하지 않음).
    # 각 항목: attempt, phase, model(계열), started_at, ended_at. 지난 시도도 보고서에 합산한다.
    # worker·수정 단계에는 tier, actual_model, effort도 보존한다(옛 state에는 없음, 빈 모델·effort는 CLI 기본값).
    phases: list[dict] = field(default_factory=list)
    transient_errors: int = 0  # worker가 일시 오류로 끝난 횟수. failures와 따로 센다(재시작을 넘어 누적)
    network_wait_seconds: float = 0  # 이 티켓이 네트워크 대기로 보낸 시간(누적)
    # 끊긴 worker를 잇는 표시: branch, worktree, base, fix(수정 worker 회차, 0이면 구현), rundir,
    # done(worker는 끝났고 리뷰부터 하면 된다). 있으면 _start가 새 worktree 대신 여기서 잇는다. 비었으면 없음.
    # 리뷰 단계 동안에도 done으로 있다: 끝나지 않은 리뷰는 gs가 어떻게 끝나든 다음 gs go가 다시 한다(go._finish).
    # 수리 중이면 repair(go.REPAIR_*: 어디까지 했나)도 있다. 수리는 검증 실패부터 다시 검증까지 이 표시로 잇는다. 옛 state에는 없다.
    # 끊긴 검증의 다시 검증 차례면 verify_again(True)도 있다(go._verify_interrupted). 옛 state에는 없다.
    network_resume: dict = field(default_factory=dict)
    # 수리(go._start_repair)마다 한 줄. 재시도·재실행 뒤에도 보존한다. 옛 state에는 없다.
    # attempt(시도 번호), verify_log(수리 worker가 받은 실패 로그), reason(첫 검증 실패 이유), base(수리 전 head),
    # worker(수리 worker의 결과. 비면 아직 안 끝났다), result("" 진행 중 | REPAIR_PASSED | REPAIR_FAILED), detail(실패 이유).
    repairs: list[dict] = field(default_factory=list)


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
    # 마무리를 멈춘 오류의 글(finish._note_failure). finish와 달리 새 마무리가 비우지 않고 실행을 넘어 남는다.
    # 결함 수집이 같은 오류를 다시 올리지 않게 대조한다(feedback.finish_anomaly). 옛 state에는 없다.
    finish_errors: list[str] = field(default_factory=list)
    phase: str = ""  # feature 전체 마무리 중이면 finish
    progress: dict = field(default_factory=dict)
    agy_calls: int = 0  # 이번 실행에서 gs가 띄운 agy 호출 수(worker 1번·리뷰 1번 = 1회, 재시도·수정·재리뷰 포함). 실행마다 0에서
    # 네트워크 끊김: errors(일시 오류 수), waited_seconds(기다린 시간, 둘 다 실행을 넘어 누적),
    # wait(지금의 대기: count, due_at. due_at이 비면 다시 띄운 worker로 회복을 확인하는 중), aborted(중단 이유)
    network: dict = field(default_factory=dict)
    # 선택 측정 이력. 재개·재시도·새 마무리에서도 덮어쓰지 않는다. 옛 state에는 없어도 된다.
    # runtime, workers, validations, reviewers, review_calls, finish_stages의 목록(metrics.py).
    metrics: dict = field(default_factory=dict)
    # 실행 시작 때의 push 설정(git.push_settings). 재개해도 덮어쓰지 않고 gs의 push마다 대조한다.
    # 옛 state에는 없다. 없으면 대조를 건너뛰고, 다음 `gs go`가 시작할 때 그 값을 처음 기록한다.
    push_record: dict = field(default_factory=dict)

    def ticket(self, tid: str) -> TicketState:
        return self.tickets.setdefault(tid, TicketState())


def reviews(ts: TicketState) -> list[dict]:
    """티켓의 리뷰 기록들: 첫 리뷰, 있으면 두 번째 리뷰. 빈 기록은 뺀다."""
    return [rec for rec in (ts.review, ts.second_review) if rec]


def reviewed_heads(ts: TicketState) -> set[str]:
    """리뷰 기록들의 reviewed_head. 부르지 못한 리뷰·옛 state의 기록은 값이 없어 빠진다."""
    return {rec["reviewed_head"] for rec in reviews(ts) if rec.get("reviewed_head")}


def agy_reached(st: State, limit: int) -> bool:
    """이번 실행의 agy 호출이 상한에 닿았나. 닿았으면 더 띄우지 않는다."""
    return st.agy_calls >= limit


PHASE_LABELS = {"worker": "worker", "review_wait": "리뷰 대기", "review": "리뷰", "fix_wait": "수정 대기", "fix": "수정",
                "rereview": "재리뷰", "fix2": "수정 2", "repair_wait": "수리 대기", "repair": "수리", "verify": "검증",
                "finish": "마무리", "checks": "CI 대기", "setup": "준비", "network": "네트워크 대기"}

REPAIR_PASSED, REPAIR_FAILED = "passed", "failed"  # TicketState.repairs의 result


def open_repair(ts: TicketState) -> dict | None:
    """결과가 아직 없는 수리 기록. 없으면 None."""
    return ts.repairs[-1] if ts.repairs and not ts.repairs[-1].get("result") else None


def close_repair(ts: TicketState, result: str, detail: str = "") -> None:
    """지금 수리의 결과를 적는다. 수리 중이 아니면 하는 일이 없다. 저장은 부르는 쪽이 한다."""
    if rec := open_repair(ts):
        rec.update(result=result, detail=detail)


def repair_summary(ts: TicketState) -> str:
    """수리한 사실과 결과 한 줄(보고서, `gs status`). 수리한 적이 없으면 빈 문자열."""
    parts = []
    for rec in ts.repairs:
        done = rec.get("worker", "")
        if rec.get("result") == REPAIR_PASSED:
            outcome = "다시 검증 통과"
        elif rec.get("result") == REPAIR_FAILED:
            outcome = f"실패: {rec.get('detail', '')}"
        else:
            outcome = "다시 검증 중" if done else "수리 중"
        parts.append(f"시도 {rec.get('attempt', '?')} " + (f"{done} → " if done else "") + outcome)
    return "수리: " + " · ".join(parts) if parts else ""


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


def network_label(st: State, at: str) -> str:
    """진행 바·`gs status`의 네트워크 줄. 대기 중이 아니면 빈 문자열."""
    wait = st.network.get("wait") or {}
    if not wait:
        return ""
    if not wait.get("due_at"):
        return f"네트워크 회복 확인({wait['count']}회)"
    # 두 시각은 초 단위로 잘려 있어 실제보다 1초까지 벌어진다. 1분이 1초보다 짧으면(GS_NETWORK_MINUTE) 그 1초가 몇십 분으로 보인다
    left = math.ceil(max(0, seconds_between(at, wait["due_at"]) - 1) / transient.minute_seconds())
    return f"네트워크 대기({wait['count']}회, {max(1, left)}분 뒤)"


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


FINISHED_PHASES = ("verified", "reverted")  # 마무리를 끝까지 한 실행(finish.BASE_REPORT_PHASES). 멈춘 실행의 짧은 마무리는 표본이 아니다
MIN_RUNNING_S = 60  # 평균을 넘긴 티켓이 앞으로 걸릴 시간으로 세는 값


def load_finish_history(repo: Path, feature: str) -> float | None:
    """다른 feature의 마무리 시간(마지막 티켓 종료부터 실행 종료까지) 중앙값(초). 로컬 실행 기록만 읽는다.

    표본에서 뺀다: 마무리를 끝까지 하지 않은 실행, 시각이 없거나 거꾸로인 기록, 재개가 섞인 실행(이번 시작 전 단계를
    가진 티켓이 있는 state: 시작 이후의 마무리가 이어 한 일이라 표본이 달라진다). 깨진 기록은 건너뛴다.
    """
    durations = []
    for p in (repo / ".goldstack" / "work").glob("*/run/state.json"):
        if p.parent.parent.name == feature:
            continue
        try:
            st = load(p.parent, p.parent.parent.name)
            sample = _finish_sample(st)
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            continue  # 깨졌거나 읽을 수 없는 이력은 실행을 막지 않는다
        if sample is not None:
            durations.append(sample)
    return median(durations) if durations else None


def _finish_sample(st: State) -> float | None:
    if st.finish.get("phase") not in FINISHED_PHASES:
        return None
    run_start, run_end = parse_time(st.started_at), parse_time(st.finished_at)
    if not run_start or not run_end:
        return None
    ends = []
    for ts in st.tickets.values():
        starts = [parse_time(p["started_at"]) for p in ts.phases] + [parse_time(ts.started_at)]
        if any(start and start < run_start for start in starts):
            return None  # 재개가 섞인 실행
        if ts.ended_at:
            end = parse_time(ts.ended_at)
            if not end or any(start and start > end for start in starts):
                return None  # 깨진 종료 시각(읽을 수 없거나 시작보다 빠름)
            ends.append(end)
    if not ends or run_end < max(ends):
        return None
    return (run_end - max(ends)).total_seconds()


def _ticket_start(ts: TicketState, run_start: datetime | None) -> datetime | None:
    """이번 실행에서 티켓이 시작한 시각. 시작 시각은 최신 worker의 것이라, 재시도를 포함한 첫 단계부터 잰다.
    이번 실행 전의 시각이면 None(지난 실행의 시간은 표본이 아니다)."""
    starts = [start for p in ts.phases
              if (start := parse_time(p["started_at"])) and run_start and start >= run_start]
    start = min(starts) if starts else parse_time(ts.started_at)
    return start if start and run_start and start >= run_start else None


def simulate_schedule(remaining: dict[str, float], running: dict[str, float], deps: dict[str, list[str]],
                      done: set[str], max_workers: int) -> float:
    """남은 티켓이 모두 끝나기까지의 초. remaining은 대기 티켓의 예상 소요, running은 도는 티켓이 앞으로 걸릴 시간.

    막는 티켓이 모두 끝난 대기 티켓을 순서대로 빈 자리에 넣는다. 직렬 사슬은 자리가 남아도 나뉘지 않는다.
    실패·건너뜀에 막혀 영영 시작하지 못하는 티켓은 센다 해도 의미가 없어 뺀다.
    """
    t, active = 0.0, [(left, tid) for tid, left in running.items()]
    done, waiting = set(done), dict(remaining)
    while True:
        for tid in list(waiting):
            if len(active) >= max(1, max_workers):
                break
            if all(d in done for d in deps.get(tid, ())):
                active.append((t + waiting.pop(tid), tid))
        if not active:
            return t
        active.sort()
        t, tid = active.pop(0)
        done.add(tid)


def calculate_progress(st: State, order: list[str], max_workers: int, *, prior=(),
                       models: dict[str, str] | None = None, at: str | None = None,
                       history_median_s: float | None = None, deps: dict[str, list[str]] | None = None,
                       finish_median_s: float | None = None) -> dict:
    """남은 시간을 의존과 max_workers로 흉내 낸 일정에 마무리를 더해 계산한다.

    티켓 하나의 예상 소요는 이번 실행에서 끝난 티켓의 평균이다. 없으면 이전 실행 중앙값(history_median_s)이고
    line에 `(이전 실행 기준)`이 붙는다. 도는 티켓은 예상 소요에서 쓴 시간을 뺀 값(넘겼으면 1분)으로 센다.
    finish_median_s(다른 feature의 마무리 중앙값)가 있으면 더하고, 없으면 `+ 마무리`를 붙인다.
    마무리 중에는 값이 있고 아직 남았을 때만 시간을 보이고, 아니면 `마무리 중`(eta_s는 None)이다.
    """
    at = st.finished_at or at or now()
    run_start = parse_time(st.started_at)
    now_t = parse_time(at)
    terminal = (MERGED, FAILED, SKIPPED)
    done = sum(st.tickets[tid].status in terminal for tid in order)
    running, durations, spent = [], [], {}
    for tid in order:
        ts = st.tickets[tid]
        if ts.status == RUNNING and not st.finished_at:
            p = ts.phases[-1] if ts.phases else {}
            started = _ticket_start(ts, run_start) or parse_time(ts.started_at)
            spent[tid] = max(0, (now_t - started).total_seconds()) if started and now_t else 0
            if p.get("phase") != "network":  # 기다리는 티켓은 아래 네트워크 대기 한 칸으로 보인다
                running.append({"id": tid, "phase": p.get("phase", "worker"),
                                "model": p.get("model", (models or {}).get(tid, ""))})
        if tid in prior or ts.status not in terminal or not ts.started_at or not ts.ended_at:
            continue
        start, end = _ticket_start(ts, run_start), parse_time(ts.ended_at)
        if start and end:
            durations.append(max(0, (end - start).total_seconds()))
    finishing = st.phase == "finish" and not st.finished_at
    if st.phase in ("finish", "setup") and not st.finished_at:
        # 빈 id는 개별 티켓이 아닌 feature 전체의 보고서·PR·base 검증을 뜻한다.
        phase = "setup" if st.phase == "setup" else "checks" if st.finish.get("phase") == "checks_pending" else "finish"
        running = [{"id": "", "phase": phase, "model": "claude" if phase == "finish" else ""}]
    total = len(order)
    historical = not durations and history_median_s is not None
    average = sum(durations) / len(durations) if durations else history_median_s
    eta, pending_finish = None, False  # pending_finish: 마무리 시간을 모르는 채 티켓 일정만 센 값이다
    if finishing:
        # 티켓은 모두 끝났다. 마무리 시작은 마지막 티켓 종료다(이번 실행에서 끝난 것이 없으면 실행 시작)
        ends = [end for tid in order if (end := parse_time(st.tickets[tid].ended_at)) and run_start and end >= run_start]
        began = max(ends) if ends else run_start
        if finish_median_s is not None and began and now_t:
            left = minutes(finish_median_s - (now_t - began).total_seconds())
            eta = left * 60 if left >= 1 else None  # 마무리 중에는 0분 남음을 보이지 않는다
        historical = False
    else:
        waiting = [tid for tid in order if st.tickets[tid].status not in terminal and tid not in spent]
        if average is not None or not (waiting or spent):
            avg = average or 0
            scope = set(order)  # 범위 밖 의존은 끝난 것이다(go._skip_blocked)
            schedule = simulate_schedule(
                {tid: avg for tid in waiting}, {tid: avg - s if s < avg else MIN_RUNNING_S for tid, s in spent.items()},
                {tid: [d for d in (deps or {}).get(tid, ()) if d in scope] for tid in order},
                {tid for tid in order if st.tickets[tid].status == MERGED}, max_workers)
            pending_finish = finish_median_s is None and not st.finished_at
            added = 0 if st.finished_at else finish_median_s or 0
            eta = minutes(schedule + added) * 60
        historical = historical and eta is not None
    elapsed = int(seconds_between(st.started_at, at))
    filled = 8 * done // total if total else 0
    parts = [f"{'▓' * filled}{'░' * (8 - filled)} {st.feature} {done}/{total}"]
    for p in running:
        label = PHASE_LABELS[p["phase"]]
        model = f"({p['model']})" if p["model"] else ""
        parts.append(f"{p['id'] + ' ' if p['id'] else ''}{label} 중{model}")
    if not st.finished_at and (network := network_label(st, at)):
        parts.append(network)
    if eta is not None:
        eta_text = f"약 {eta // 60}분 남음" + (" + 마무리" if pending_finish else "")
    else:
        eta_text = "마무리 중" if finishing else "남은 시간 계산 중"
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
    st = State(**top, tickets=tickets)
    if st.push_record:  # 되돌리기 명령이 값을 읽을 곳. 항목이 없는 기록과 레포를 옮긴 기록도 실제 위치를 가리키게 한다
        st.push_record["state_file"] = str(p.resolve())
    return st


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
