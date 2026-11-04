"""판정과 분리한 최선의 측정. 측정·메타데이터·저장 오류는 호출한 작업에 전파하지 않는다.

시간은 monotonic 초, worker 종료는 exit 파일 mtime이다. 설치 commit은 실행 중인 배포판의
direct_url.json에 있을 때만 읽는다(작업 대상 레포의 HEAD를 gs 설치 commit으로 쓰지 않는다).
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from importlib import metadata
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
def validation(r, label, command, sha, result, changed=False, *, tree_sha="", merge_head="") -> None:
    for nth, item in enumerate(result.samples, 1):
        r.st.metrics.setdefault("validations", []).append({
            **item, "label": label, "command": command, "sha": sha, "tree_sha": tree_sha,
            "merge_head": merge_head, "attempt": nth, "recorded_at": state.now(),
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
def archive_review(kwargs, rec) -> None:
    wait = kwargs.get("on_wait")
    if wait is None or not hasattr(wait, "st"):
        return
    with wait.lock:
        wait.st.metrics.setdefault("reviewers", []).append({
            "ticket": wait.tid, "reviewer": kwargs["reviewer"], "round": kwargs.get("nth", 0),
            **{k: rec[k] for k in ("dir", "tier", "actual_model", "effort", "seconds", "findings_count", "fix_count")
               if k in rec}})
        wait.save()


@best_effort
def begin_review_call(on_wait, reviewer, selection, rdir):
    rec = {"reviewer": reviewer, "actual_model": selection.model, "effort": selection.effort,
           "dir": str(rdir), "started_at": state.now(), "seconds": None, "result": "running"}
    if on_wait is not None and hasattr(on_wait, "st"):
        with on_wait.lock:
            on_wait.st.metrics.setdefault("review_calls", []).append({"ticket": on_wait.tid, **rec})
            rec = on_wait.st.metrics["review_calls"][-1]
    return rec


@best_effort
def end_review_call(on_wait, rec, start, result):
    if on_wait is not None and hasattr(on_wait, "st"):
        with on_wait.lock:
            rec.update(seconds=elapsed(start), result=result, ended_at=state.now())
            on_wait.save()


@contextmanager
def review_call(on_wait, reviewer, selection, rdir):
    start, rec = clock(), begin_review_call(on_wait, reviewer, selection, rdir)
    result = "error"
    try:
        yield
        result = "passed"
    finally:
        end_review_call(on_wait, rec, start, result)


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
