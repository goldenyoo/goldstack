"""판정과 분리한 최선의 측정. 측정·메타데이터·저장 오류는 호출한 작업에 전파하지 않는다.

시간은 monotonic 초, worker 종료는 exit 파일 mtime이다. 설치 commit은 실행 중인 배포판의
direct_url.json에 있을 때만 읽는다(작업 대상 레포의 HEAD를 gs 설치 commit으로 쓰지 않는다).

처리 대기(workers의 processing_wait_seconds): worker가 끝난 뒤 go._loop가 그 결과를 받기까지(worker_exited_at → processing_started_at).
v9부터 리뷰는 루프 밖이라 다른 티켓의 리뷰 시간은 여기 들지 않는다. 병합·검증과 실패 요약처럼 루프 안에서 도는 일을 기다린 시간이다.
결과 대기(reviewers의 result_wait_seconds): 리뷰·판단 호출이 스레드에서 돌아온 때부터 go._loop가 그 결과를 받기까지(go._resume_flow).
검증이 루프를 막으면 그동안 끝난 리뷰의 결과는 받아지지 않는다. 그 대기다. 한 호출로 나간 리뷰어(둘이면 함께)는 같은 값이고, 기록이 없는 옛 state는 보고서에 `기록 없음`이다.
받은 뒤 리뷰 자리를 기다린 시간은 여기 들지 않고 단계 `review_wait`로, 수정 worker 자리는 `fix_wait`로, 수리 worker 자리는 `repair_wait`로 남는다(state.phases).
수리(go._start_repair): worker는 workers에 phase `repair`로 남고(끊겨 이으면 디렉터리가 `repair-net<n>`이어도 같다), 수리 재리뷰는 reviewers의 round가
review.REPAIR_ROUND다. 수리 뒤 다시 한 검증은 validations의 label이 `ticket-<NN>-repair`다. 끊긴 검증은 그 label 끝에 `-끊김`이 붙는다(go._verify).
validations 한 줄은 검증 하나의 재시도 하나다. `integration_head`(검증한 integration 끝)와 `ticket_head`(병합하려던 티켓 커밋)는 다르고,
같은 티켓의 검증이 여러 번이어도 integration_head가 같을 수 있다. `ticket_attempt`는 티켓 worker 시도 번호, `retry`는 한 검증 안의 재시도 번호다.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from importlib import metadata
from pathlib import Path
from time import monotonic

from . import state


def best_effort(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:  # 측정은 실행·검증·병합의 관문이 아니다
            return None
    return wrapped


@best_effort
def clock() -> float:
    return monotonic()


@best_effort
def elapsed(start) -> float:
    return round(max(0, monotonic() - start), 6)


@best_effort
def runtime(r) -> None:
    rec = {"started_at": state.now(), "version": metadata.version("goldstack"), "install_commit": ""}
    # 로컬 경로·wheel 설치에는 VCS commit이 없을 수 있다. 버전은 그래도 남긴다.
    try:
        raw = metadata.distribution("goldstack").read_text("direct_url.json")
        rec["install_commit"] = json.loads(raw or "{}").get("vcs_info", {}).get("commit_id", "")
    except Exception:
        pass
    r.st.metrics.setdefault("runtime", []).append(rec)


@best_effort
def worker_selection(ts, tier, selection) -> None:
    ts.phases[-1].update(tier=tier, actual_model=selection.model if selection else "",
                         effort=selection.effort if selection else "")


@best_effort
def worker_started(r, job) -> None:
    ts = r.st.ticket(job.ticket.id)
    p = ts.phases[-1]
    r.st.metrics.setdefault("workers", []).append({
        "ticket": job.ticket.id, "dir": str(job.rundir), "attempt": p["attempt"], "phase": p["phase"],
        "model": p["model"], "actual_model": p.get("actual_model", ""), "effort": p.get("effort", ""),
        "tier": p.get("tier", ""), "started_at": datetime.now().astimezone().isoformat(),
        "worker_exited_at": "", "processing_started_at": ""})


@best_effort
def worker_finished(r, job) -> None:
    """루프가 끝난 worker의 결과를 받았다. 종료 시각과 처리 대기(모듈 docstring)를 적는다."""
    rows = r.st.metrics.setdefault("workers", [])
    rec = next((x for x in reversed(rows) if x["dir"] == str(job.rundir)), None)
    if rec is None:  # 옛 state에서 재개한 worker도 종료·처리 시각은 남긴다
        phase = "worker" if job.rundir.name.isdigit() else job.rundir.name.split("-net", 1)[0]
        directory = job.rundir if phase == "worker" else job.rundir.parent
        attempt = int(directory.name) if directory.name.isdigit() else None
        # 마지막 단계는 이미 review·network일 수 있다. 이 실행 디렉터리에 맞는 worker 단계만 쓴다.
        p = next((p for p in reversed(r.st.ticket(job.ticket.id).phases)
                  if p.get("phase") == phase and p.get("attempt") == attempt), {})
        rec = {"ticket": job.ticket.id, "dir": str(job.rundir), "attempt": attempt,
               "phase": phase, "model": p.get("model", job.ticket.model),
               **{k: p.get(k, "") for k in ("actual_model", "effort", "tier")},
               "started_at": "", "seconds": None, "worker_exited_at": "", "processing_started_at": ""}
        rows.append(rec)  # 실제 시작 측정이 없으므로 새로 실행한 시각·0초를 만들지 않는다
    if rec.get("processing_started_at"):
        return  # 네트워크 대기로 세워 둔 worker의 첫 처리 시각을 보존한다
    rec["processing_started_at"] = datetime.now().astimezone().isoformat()
    if job.exit_file.exists():
        rec["worker_exited_at"] = datetime.fromtimestamp(job.exit_file.stat().st_mtime).astimezone().isoformat()
        rec["processing_wait_seconds"] = state.seconds_between(rec["worker_exited_at"], rec["processing_started_at"])
        if rec.get("started_at"):
            rec["seconds"] = state.seconds_between(rec["started_at"], rec["worker_exited_at"])
    r.save()


@best_effort
def sample(samples, start, result) -> None:
    samples.append({"seconds": elapsed(start), "code": result.code, "timed_out": result.timed_out, "ok": result.ok})


@best_effort
def validation(r, label, command, integration_head, result, changed=False, *, tree_sha="", ticket_head="",
               ticket_attempt=None) -> None:
    """검증 한 번(재시도 포함)을 `validations`에 한 줄씩 남긴다.

    - `integration_head`: 검증한 worktree의 HEAD. 티켓 검증이면 미완 병합을 만들기 전 integration 끝이라
      같은 티켓의 다른 검증과 같을 수 있다. 티켓 코드가 아니다.
    - `ticket_head`: 티켓 검증에서 병합하려던 티켓 커밋(MERGE_HEAD). 마무리 검증은 비어 있다.
    - `ticket_attempt`: 그때의 티켓 worker 시도 번호(마무리 검증은 None). 검증 재시도 번호가 아니다.
    - `retry`: 이 검증 안의 재시도 번호(1부터, `verify.run` 표본 순서). 티켓 시도와 무관하다.
    옛 state는 `sha`(= integration_head), `attempt`(= retry), `merge_head`(= ticket_head)로 읽는다(report.validation_row).
    """
    for nth, item in enumerate(result.samples, 1):
        r.st.metrics.setdefault("validations", []).append({
            **item, "label": label, "command": command, "integration_head": integration_head,
            "ticket_head": ticket_head, "ticket_attempt": ticket_attempt, "tree_sha": tree_sha,
            "retry": nth, "recorded_at": state.now(),
            "tree_changed": changed, "accepted": item["ok"] and not changed,
            "result": "timeout" if item["timed_out"] else "failed" if not item["ok"] else
                      "tree_changed" if changed else "passed"})
    r.save()


@best_effort
def review_result(rec, start) -> None:
    rec.update(seconds=elapsed(start), findings_count=len(rec.get("findings", [])),
               fix_count=sum(f.get("action") == "fix" for f in rec.get("findings", [])))


@best_effort
def copy_review_counts(target, source):
    target.update({k: source[k] for k in ("seconds", "findings_count", "fix_count") if k in source})


@best_effort
def reviewer_rows(r) -> int:
    """리뷰 호출을 보내는 시점의 reviewers 길이. 그 호출이 낸 줄은 이 뒤에 붙는다(result_wait)."""
    return len(r.st.metrics.get("reviewers", []))


@best_effort
def result_wait(r, rv) -> None:
    """루프가 끝난 리뷰 호출의 결과를 받는다. 호출이 돌아온 때부터 지금까지를 이 호출이 낸 reviewers 줄에 적는다.

    호출이 넘긴 변경을 먼저 반영한 뒤(go._drain) 불러야 줄이 있다. 돌아온 시각이 없으면 적지 않는다.
    """
    at = rv.ended.get("at")
    if at is None:
        return
    wait = elapsed(at)
    tid = rv.a.t.id
    rows = r.st.metrics.get("reviewers", [])
    for row in rows[rv.rows or 0:]:
        if row.get("ticket") == tid and "result_wait_seconds" not in row:
            row["result_wait_seconds"] = wait
    r.save()


def on_state(wait, change) -> None:
    """리뷰·판단 호출이 state를 고친다(change). 루프 밖 호출이면 루프 스레드에 넘기고(wait.post), 아니면 wait의 잠금 안에서 바로 한다."""
    post = getattr(wait, "post", None)
    if post is not None:
        post(change)
        return
    with wait.lock:
        change()


@best_effort
def archive_review(kwargs, rec) -> None:
    wait = kwargs.get("on_wait")
    if wait is None or not hasattr(wait, "st"):
        return
    row = {"ticket": wait.tid, "reviewer": kwargs["reviewer"], "round": kwargs.get("nth", rec.get("round", 0)),
           **{k: rec[k] for k in ("dir", "tier", "actual_model", "effort", "seconds", "findings_count", "fix_count")
              if k in rec}}

    def change():
        wait.st.metrics.setdefault("reviewers", []).append(row)
        wait.save()
    on_state(wait, change)


@best_effort
def begin_review_call(on_wait, reviewer, selection, rdir):
    rec = {"reviewer": reviewer, "actual_model": selection.model, "effort": selection.effort,
           "dir": str(rdir), "started_at": state.now(), "seconds": None, "result": "running"}
    if on_wait is not None and hasattr(on_wait, "st"):
        rec = {"ticket": on_wait.tid, **rec}  # 이 사전이 state의 줄이 된다. 끝날 때 같은 줄을 고친다
        on_state(on_wait, lambda: on_wait.st.metrics.setdefault("review_calls", []).append(rec))
    return rec


@best_effort
def end_review_call(on_wait, rec, start, result, extra=None):
    if on_wait is not None and hasattr(on_wait, "st"):
        ended = dict(seconds=elapsed(start), result=result, ended_at=state.now(), **(extra or {}))

        def change():
            rec.update(ended)
            on_wait.save()
        on_state(on_wait, change)


class ReviewCall:
    """`review_call` 안에서 호출이 답을 읽지 못했음을 알린다(format_error). 호출 자체가 실패한 `error`와 구분한다."""

    def __init__(self, review_file: Path):
        self.review_file = review_file
        self.failed_format = False

    def format_error(self) -> None:
        self.failed_format = True


@contextmanager
def review_call(on_wait, reviewer, selection, rdir):
    """리뷰 호출 하나의 측정. 결과: passed(답을 읽었다. 고쳐서 읽은 답 포함) | format-error(호출은 끝났으나 답을 못 읽었다) | error(호출이 실패했다).

    format-error 줄에는 답을 담은 `review.txt`의 경로와 바이트 수를 남긴다(원문은 옮기지 않는다)."""
    start, rec = clock(), begin_review_call(on_wait, reviewer, selection, rdir)
    call = ReviewCall(Path(rdir) / "review.txt")
    result, extra = "error", None
    try:
        yield call
        result = "passed"
    finally:
        if call.failed_format:
            result, extra = "format-error", review_file_facts(call.review_file)
        end_review_call(on_wait, rec, start, result, extra)


def review_file_facts(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError:
        size = None  # 답 파일이 없다
    return {"review_file": str(path), "review_bytes": size}


def reviewed(fn):
    @wraps(fn)
    def wrapped(**kwargs):
        start = clock()
        rec = fn(**kwargs)  # 원래 호출의 예외·판정은 그대로다
        review_result(rec, start)
        archive_review(kwargs, rec)
        return rec
    return wrapped


@best_effort
def close_interrupted_stages(st) -> None:
    """지난 프로세스의 미완 단계는 마지막 저장까지의 하한으로 닫아 중단 기간을 제외한다."""
    for rec in st.metrics.get("finish_stages", []):
        if rec.get("seconds") is None and not rec.get("interrupted"):
            ended_at = st.updated_at or rec["started_at"]
            rec.update(ended_at=ended_at, seconds=state.seconds_between(rec["started_at"], ended_at),
                       interrupted=True)


@best_effort
def begin_stage(r, label, finishing_only=False):
    if finishing_only and r.st.phase != "finish":
        return None
    rec = {"label": label, "started_at": state.now(), "ended_at": "", "seconds": None}
    r.st.metrics.setdefault("finish_stages", []).append(rec)
    return rec


@best_effort
def end_stage(r, rec, start):
    rec.update(ended_at=state.now(), seconds=elapsed(start))
    r.save()


def stage(label, *, finishing_only=False):
    def decorate(fn):
        @wraps(fn)
        def wrapped(r, *args, **kwargs):
            start, rec = clock(), begin_stage(r, label, finishing_only)
            try:
                return fn(r, *args, **kwargs)
            finally:
                end_stage(r, rec, start)
        return wrapped
    return decorate
