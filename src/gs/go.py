"""`gs go`: 시작할 수 있는 티켓을 max_workers개까지 동시에 worker에 맡기고 integration에 모아 PR을 연다.

병렬 실행(04). 병합·검증은 한 번에 하나씩. 재시도 없음, 리뷰 없음, PR 병합 없음:
리뷰(06), 재시도·충돌 후 재실행(07), 병합(08)은 뒤 티켓.
진행 상태는 `.work/<f>/run/state.json`에 남기고(03), 다시 실행하면 병합된 티켓은 건너뛰고 나머지를 이어 간다.
같은 feature에 `gs go`는 하나만 돈다(run/lock).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import git, graph, herdr, state, worker
from .check import check
from .feature import Feature, Ticket

MAIN = "main"
BASE = "origin/main"  # PR 대상. 로컬 main은 뒤처지거나 앞설 수 있어 쓰지 않는다
CONFLICT = "conflict"  # 최신 integration과 충돌한 티켓의 실패 이유(07이 이것을 보고 다시 한다)


def integration_branch(feature: str) -> str:
    return f"gs/{feature}/integration"


def ticket_branch(feature: str, tid: str) -> str:
    return f"gs/{feature}/{tid}"


def trailer(feature: str, tid: str) -> str:
    """integration 병합 커밋에 남기는 표시. 이걸로 '이미 병합됨'을 안다."""
    return f"gs-ticket: {feature}/{tid}"


@dataclass
class Run:
    repo: Path
    feat: Feature
    only: list[str] | None
    st: state.State | None = None  # 상태의 원천. 요약·PR 본문도 이것을 읽는다
    g: dict[str, list[str]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    prior: set[str] = field(default_factory=set)  # 이번 실행 전에 이미 병합돼 있던 티켓(표시용)
    ihead: str = ""  # gs가 아는 integration 끝. 병합할 때만 움직인다

    @property
    def name(self) -> str:
        return self.feat.name

    @property
    def rundir(self) -> Path:
        return self.feat.root / "run"

    @property
    def iwt(self) -> Path:
        return self.rundir / "wt" / "integration"


def say(msg: str) -> None:
    print(msg, flush=True)


def go(repo: Path, name: str, only: list[str] | None = None) -> int:
    feat, _ = check(repo, name, only)
    for p in feat.problems:
        print(p, file=sys.stderr)
    if feat.errors:
        print(f"gs go: 검사 오류 {len(feat.errors)}개. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    r = Run(repo, feat, only)
    lock = state.Lock(r.rundir)
    try:
        lock.acquire()
    except state.Locked as e:
        print(f"gs go: {e}. 같은 feature에 gs go는 하나만 돈다. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    try:
        try:
            git.run(repo, "fetch", "-q", "origin", MAIN)
            _require_committed(repo, name)
            _begin(r)
            _prepare_integration(r)
            _loop(r)
            url = _publish(r)
        except git.GitError as e:
            print(f"gs go: git 오류: {e}", file=sys.stderr)
            return 1
        except herdr.HerdrError as e:
            print(f"gs go: herdr 오류: {e}", file=sys.stderr)
            return 1
        finally:
            if r.st is not None:
                r.st.finished_at = state.now()
                state.save(r.rundir, r.st)
    finally:
        lock.release()
    _summary(r, url)
    return 0 if all(r.st.tickets[tid].status == state.MERGED for tid in r.order) else 1


def _begin(r: Run) -> None:
    """state.json을 읽어 이번 실행을 시작한다. 지난 실행이 죽어 running으로 남은 티켓은 실패로 세지 않는다."""
    st = state.load(r.rundir, r.name)
    r.g = _graph(r)
    r.order = graph.topo_order(r.g)
    for tid, ts in sorted(st.tickets.items()):
        if ts.status == state.RUNNING:
            say(f"[{tid}] 지난 실행이 중간에 끝나 running으로 남았다. 실패로 세지 않고 새로 시작한다")
            ts.attempts = max(0, ts.attempts - 1)
            ts.status = state.PENDING
    for tid in r.order:
        ts = st.ticket(tid)
        if ts.status != state.MERGED:  # 실패·건너뜀은 이번 실행에서 다시 한다
            ts.status, ts.reason, ts.pane, ts.started_at, ts.ended_at = state.PENDING, "", "", "", ""
    st.pid, st.only, st.started_at, st.finished_at = os.getpid(), r.only, state.now(), ""
    r.st = st
    state.save(r.rundir, st)


def _set(r: Run, tid: str, **fields) -> None:
    """티켓 상태를 바꾸고 바로 state.json에 쓴다."""
    ts = r.st.ticket(tid)
    for k, v in fields.items():
        setattr(ts, k, v)
    state.save(r.rundir, r.st)


def _require_committed(repo: Path, name: str) -> None:
    rel = f".work/{name}"
    if git.out(repo, "status", "--porcelain", "--", rel) or git.run(repo, "diff", "--quiet", BASE, "--", rel,
                                                                     check=False).returncode:
        raise git.GitError(f"{rel}가 {BASE}와 다르다. worker는 {BASE} 기준으로 일하므로 먼저 커밋하고 push하라")


def _reset_integration(r: Run, to: str = "HEAD") -> bool:
    """integration worktree는 gs만 쓴다. 남은 병합·변경을 버리고 to로 되돌린다. 무언가 버렸으면 True."""
    dirty = not git.is_clean(r.iwt)
    if git.run(r.iwt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
        git.run(r.iwt, "merge", "--abort", check=False)
        dirty = True
    moved = git.sha(r.iwt, "HEAD") != git.sha(r.iwt, to)
    git.run(r.iwt, "reset", "-q", "--hard", to)
    git.run(r.iwt, "clean", "-q", "-fd")
    return dirty or moved


def _prepare_integration(r: Run) -> None:
    branch = integration_branch(r.name)
    git.ensure_worktree(r.repo, r.iwt, branch, start=BASE)
    if _reset_integration(r):
        say("■ integration worktree에 남은 병합·변경을 버렸다(지난 실행이 중간에 끝난 흔적)")
    # 앞 wave가 main에 병합된 뒤라면 origin/main을 받아 둔다. 보통 fast-forward라 force push가 필요 없다.
    res = git.run(r.iwt, "merge", "--no-edit", BASE, check=False)
    if res.returncode:
        git.run(r.iwt, "merge", "--abort", check=False)
        raise git.GitError(f"{BASE}를 {branch}에 합치다 충돌했다: {res.stdout.strip()}")
    say(f"■ integration: {branch} @ {git.sha(r.iwt, 'HEAD')[:8]} ({r.iwt})")


def _graph(r: Run) -> dict[str, list[str]]:
    g = {t.id: t.blocked_by for t in r.feat.tickets.values()}
    if r.only is not None:
        g, _, _ = graph.subgraph(g, r.only)
    return g


def _already_merged(r: Run, tid: str) -> bool:
    return bool(git.out(r.iwt, "log", "-1", "--format=%H", "--fixed-strings", f"--grep={trailer(r.name, tid)}"))


@dataclass
class Active:
    """지금 돌고 있는 worker 하나."""
    t: Ticket
    proc: worker.Proc
    branch: str
    wt: Path
    base: str  # worker를 띄울 때의 integration 끝


def _loop(r: Run) -> None:
    """frontier에서 max_workers개까지 띄우고, 하나 끝날 때마다 병합·검증한 뒤 frontier를 다시 계산해 채운다.

    루프는 스레드 하나다. worker는 각자 pane·프로세스에서 돌고, 병합과 검증은 이 루프 안에서 하나씩 한다(직렬).
    """
    cap = max(1, r.feat.spec.max_workers)
    say(f"■ 순서: {' '.join(r.order)}")
    say(f"■ 동시 worker: 최대 {cap}")
    say(f"■ 상태: {state.path(r.rundir)}")
    # 병합 여부는 integration의 gs-ticket 표시로 확인한다. state가 merged인데 표시가 없으면 다시 한다.
    for tid in r.order:
        if _already_merged(r, tid):
            if r.st.tickets[tid].status != state.MERGED:
                _set(r, tid, status=state.MERGED, reason="", ended_at=state.now())
            r.prior.add(tid)
            say(f"[{tid}] 이미 병합됨")
        elif r.st.tickets[tid].status == state.MERGED:
            say(f"[{tid}] state는 병합이라는데 integration에 표시가 없다. 다시 한다")
            _set(r, tid, status=state.PENDING)
    r.ihead = git.sha(r.iwt, "HEAD")
    runner = worker.make_runner(r.repo, r.name)
    active: dict[str, Active] = {}
    while True:
        _skip_blocked(r)
        while len(active) < cap:
            ready = [tid for tid in _frontier(r) if tid not in active]
            if not ready:
                break
            a = _start(r, r.feat.tickets[ready[0]], runner)
            if a is None:  # 띄우기 전에 실패했다. 막힌 티켓을 다시 고른다
                _skip_blocked(r)
            else:
                active[a.t.id] = a
        if not active:
            return
        tid, code = _wait_any(r, active, runner)
        a = active.pop(tid)
        _finish(r, a, code, others=sorted(active))


def _frontier(r: Run) -> list[str]:
    """state에서 다시 계산한 frontier: 대기 중이고 막는 티켓이 모두 병합된 것. r.order 순."""
    st = r.st.tickets
    merged = [tid for tid in r.order if st[tid].status == state.MERGED]
    ready = set(graph.frontier(r.g, merged))
    return [tid for tid in r.order if tid in ready and st[tid].status == state.PENDING]


def _skip_blocked(r: Run) -> None:
    """실패·건너뜀 티켓에 막힌 대기 티켓을 건너뜀으로 적는다(줄줄이)."""
    bad = (state.FAILED, state.SKIPPED)
    for tid in r.order:  # r.order는 위상 순서라 한 번 훑으면 줄줄이 막힌 것까지 닿는다
        if r.st.tickets[tid].status != state.PENDING:
            continue
        blockers = [d for d in r.g[tid] if d in r.g and r.st.tickets[d].status in bad]  # 범위 밖 의존은 끝난 것
        if blockers:
            _set(r, tid, status=state.SKIPPED, reason=f"막힘: {', '.join(blockers)}", ended_at=state.now())
            say(f"[{tid}] 건너뜀: {', '.join(blockers)} 실패")


def _wait_any(r: Run, active: dict[str, Active], runner) -> tuple[str, int]:
    """돌고 있는 worker 중 하나가 끝날 때까지 기다린다. 동시에 끝났으면 r.order 앞쪽부터."""
    while True:
        for tid in r.order:
            if tid in active:
                code = active[tid].proc.poll()
                if code is not None:
                    return tid, code
        time.sleep(worker.poll_interval(runner))


def _start(r: Run, t: Ticket, runner) -> Active | None:
    """최신 integration 끝에서 티켓 브랜치를 새로 만들고 worker를 띄운다. 띄우지 못하면 실패로 적고 None."""
    branch = ticket_branch(r.name, t.id)
    wt = r.rundir / "wt" / t.id
    base = r.ihead
    git.remove_worktree(r.repo, wt, branch)  # 이어가기는 없다: 지난 시도는 버리고 새로
    git.ensure_worktree(r.repo, wt, branch, start=base)
    job = worker.Job(ticket=t, worktree=wt.resolve(), rundir=(r.rundir / t.id).resolve())
    job.rundir.mkdir(parents=True, exist_ok=True)
    job.log.unlink(missing_ok=True)
    _set(r, t.id, status=state.RUNNING, attempts=r.st.ticket(t.id).attempts + 1, branch=branch, pane="",
         log=str(job.log), started_at=state.now(), ended_at="", reason="")
    worker.write_brief(job, r.feat.spec, r.name, branch)
    try:
        cmd = worker.worker_command(t)
    except ValueError as e:
        _fail(r, t, str(e))
        return None
    worker.write_script(job, cmd)
    proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}")
    _set(r, t.id, pane=proc.where)
    say(f"[{t.id}] 시작: {t.title} ({proc.where}, 로그 {job.log})")
    return Active(t, proc, branch, wt, base)


def _finish(r: Run, a: Active, code: int, others: list[str] = ()) -> bool:
    """끝난 worker 하나를 확인하고, 최신 integration을 티켓 브랜치에 합쳐 본 뒤 integration에 병합·검증한다.

    others는 아직 돌고 있는 다른 worker다. integration이 바뀌었을 때 누구 짓인지 가리는 데 쓴다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    commits = git.count(r.repo, f"{a.base}..{branch}")
    say(f"[{t.id}] worker 끝: 종료 코드 {code}, 새 커밋 {commits}")

    def fail(reason: str) -> bool:
        a.proc.finish(False)
        return _fail(r, t, reason)

    # worker가 integration을 건드렸으면(커밋, 미커밋 변경, 브랜치 이동) 되돌린다. 돌던 worker가 이것 하나뿐이면
    # 이 worker 짓이라 실패로 친다. 여럿이 돌았으면 누구 짓인지 모르니 되돌리기만 하고 경고한다.
    if _reset_integration(r, r.ihead):
        if not others:
            return fail("worker가 integration worktree를 바꿨다(되돌림)")
        say(f"[{t.id}] 경고: integration worktree가 바뀌어 되돌렸다. 함께 돌던 worker({', '.join([t.id, *others])}) 중 "
            "누구 짓인지 모른다")
    if code != 0:
        return fail(f"worker 종료 코드 {code}" if code >= 0 else "worker 실행기가 사라졌다")
    if commits == 0:
        return fail("커밋 없음")
    if not git.is_clean(wt):
        say(f"[{t.id}] 경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")

    # 그 사이 다른 티켓이 병합됐을 수 있다. 최신 integration 끝을 티켓 브랜치에 먼저 합쳐 본다.
    if not _catch_up(r, a):
        return fail(CONFLICT)

    # 병합은 커밋하지 않고 두고 검증한다. 통과해야만 gs-ticket 표시를 붙여 커밋한다.
    # 중간에 죽으면 표시 없는 미완 병합만 남고, 다음 실행이 그것을 버리고 티켓을 다시 한다.
    res = git.run(r.iwt, "merge", "--no-ff", "--no-commit", branch, check=False)
    if res.returncode:
        _reset_integration(r, r.ihead)
        return fail("integration 병합 충돌")
    ok, log = _verify(r, t)
    if not ok:
        _reset_integration(r, r.ihead)
        return fail(f"검증 실패(로그 {log})")
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    git.run(r.iwt, "commit", "-q", "--no-verify", "-m", msg)  # index만 커밋한다
    _reset_integration(r)  # 검증이 남긴 파일은 버린다
    r.ihead = git.sha(r.iwt, "HEAD")
    a.proc.finish(True)
    _set(r, t.id, status=state.MERGED, ended_at=state.now())
    say(f"[{t.id}] 검증 통과 → integration 병합")
    return True


def _catch_up(r: Run, a: Active) -> bool:
    """r.ihead를 티켓 브랜치에 합친다(티켓 worktree에서). 충돌하면 병합을 취소하고 False."""
    if git.run(r.repo, "merge-base", "--is-ancestor", r.ihead, a.branch, check=False).returncode == 0:
        return True  # 이미 최신 integration 위에 있다
    res = git.run(a.wt, "merge", "--no-edit", "--no-verify", "-m",
                  f"gs: 최신 integration을 {a.t.id}에 합침", r.ihead, check=False)
    if res.returncode == 0:
        return True
    files = git.out(a.wt, "diff", "--name-only", "--diff-filter=U").split()
    git.run(a.wt, "merge", "--abort", check=False)
    detail = ", ".join(files) if files else (res.stderr or res.stdout).strip()
    say(f"[{a.t.id}] 최신 integration({r.ihead[:8]})과 충돌: {detail}")
    return False


def _fail(r: Run, t: Ticket, reason: str) -> bool:
    _set(r, t.id, status=state.FAILED, reason=reason, ended_at=state.now())
    say(f"[{t.id}] 실패: {reason}")
    return False


def _verify(r: Run, t: Ticket) -> tuple[bool, Path]:
    log = (r.rundir / t.id / "verify.log").resolve()
    say(f"[{t.id}] 검증: {r.feat.spec.verify}")
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "GS_ROLE")}
    with log.open("w", encoding="utf-8") as f:
        code = subprocess.run(["bash", "-c", r.feat.spec.verify], cwd=r.iwt, stdin=subprocess.DEVNULL,
                              stdout=f, stderr=subprocess.STDOUT, env=env).returncode
    return code == 0, log


def _gh() -> str:
    return os.environ.get("GS_GH", "gh")


def _publish(r: Run) -> str | None:
    branch = integration_branch(r.name)
    if git.count(r.repo, f"{BASE}..{branch}") == 0:
        say("■ main보다 앞선 커밋이 없어 push·PR을 건너뛴다")
        return None
    git.run(r.repo, "push", "-u", "origin", branch)  # force 아님
    body = _pr_body(r)
    found = subprocess.run([_gh(), "pr", "list", "--head", branch, "--base", MAIN, "--state", "open",
                            "--json", "url", "--jq", ".[0].url"], cwd=r.repo, capture_output=True, text=True)
    if found.returncode:
        raise git.GitError(f"gh pr list 실패: {found.stderr.strip()}")
    url = found.stdout.strip()
    if url:
        cp = subprocess.run([_gh(), "pr", "edit", url, "--body", body], cwd=r.repo, capture_output=True, text=True)
    else:
        cp = subprocess.run([_gh(), "pr", "create", "--base", MAIN, "--head", branch,
                             "--title", f"{r.name}: gs go", "--body", body], cwd=r.repo, capture_output=True,
                            text=True)
        url = cp.stdout.strip().splitlines()[-1] if cp.stdout.strip() else ""
    if cp.returncode:
        raise git.GitError(f"gh 실패: {cp.stderr.strip()}")
    return url


LABEL = {"merged": "병합", "already": "이미 병합", "failed": "실패", "skipped": "건너뜀", "pending": "대기",
         "running": "실행 중"}


def _label(r: Run, tid: str) -> str:
    status = r.st.tickets[tid].status
    return "already" if status == state.MERGED and tid in r.prior else status


def _pr_body(r: Run) -> str:
    rows = "\n".join(f"| {tid} | {r.feat.tickets[tid].title} | {LABEL[_label(r, tid)]} | {r.st.tickets[tid].reason} |"
                     for tid in r.order)
    return (f"`gs go {r.name}`" + (f" --only {','.join(r.only)}" if r.only else "") + " 결과.\n\n"
            "| 티켓 | 제목 | 결과 | 이유 |\n|---|---|---|---|\n" + rows + "\n\n"
            "08 전까지 gs는 PR을 병합하지 않는다. 리뷰 후 사람이 병합한다.\n")


def _summary(r: Run, url: str | None) -> None:
    labels = {tid: _label(r, tid) for tid in r.order}
    counts = {k: sum(v == k for v in labels.values()) for k in LABEL}
    say("■ 요약: " + ", ".join(f"{LABEL[k]} {n}" for k, n in counts.items() if n))
    for tid in r.order:
        reason = r.st.tickets[tid].reason
        say(f"  {tid} {LABEL[labels[tid]]}" + (f" — {reason}" if reason else ""))
    if url:
        say(f"■ PR: {url}")
