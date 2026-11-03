"""`gs go`: 시작할 수 있는 티켓을 max_workers개까지 동시에 worker에 맡기고 integration에 모아 PR을 연다.

병렬 실행(04). 병합·검증은 한 번에 하나씩. 실패·멈춤은 같은 모델로 한 번 재시도한다(07).
worker가 성공하면 병합 전에 다른 계열이 그 티켓 diff를 리뷰하고, 고칠 지적이 있으면 같은 모델로 수정 worker를
한 번 띄운다(06, review.py). 재리뷰는 없고 verify만 돈다. PR 병합(08)은 뒤 티켓.
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

from . import adapters, failure, git, graph, herdr, review, state, worker
from .check import check
from .feature import Feature, Ticket

MAIN = "main"
BASE = "origin/main"  # PR 대상. 로컬 main은 뒤처지거나 앞설 수 있어 쓰지 않는다
CONFLICT = "conflict"


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
            _stop_previous(tid, ts)
            ts.attempts = max(0, ts.attempts - 1)
            ts.status = state.PENDING
    for tid in r.order:
        ts = st.ticket(tid)
        if ts.status != state.MERGED:  # 실패·건너뜀은 이번 실행에서 다시 한다
            if ts.status in (state.FAILED, state.SKIPPED):
                ts.failures, ts.failure_summary, ts.reason = 0, "", ""
            ts.status, ts.pane, ts.started_at, ts.ended_at = state.PENDING, "", "", ""
    st.pid, st.only, st.started_at, st.finished_at = os.getpid(), r.only, state.now(), ""
    r.st = st
    state.save(r.rundir, st)


def _stop_previous(tid: str, ts: state.TicketState) -> None:
    """gs만 죽고 worker는 살아 남았을 수 있다. 새 시도를 시작하기 전에 지난 worker를 끝낸다.

    worker는 명령줄의 run.sh 경로(시도마다 다르다)로 찾는다. 찾아서 끝냈고 herdr pane에서 돌았으면 그 pane도 닫는다.
    """
    if not ts.log:
        return
    try:
        if not worker.kill_script(Path(ts.log).parent / "run.sh"):
            return
    except Exception as e:  # noqa: BLE001 — 최선. 새 시도는 실행 디렉터리가 따로라 결과가 섞이지는 않는다
        say(f"[{tid}] 경고: 지난 실행의 worker를 끝내지 못했다: {_err(e)}")
        return
    say(f"[{tid}] 지난 실행의 worker가 아직 돌고 있어 끝냈다")
    if ts.pane.startswith("pane ") and herdr.available():
        try:
            herdr.pane_close(herdr.session(), ts.pane.split(" ", 1)[1])
        except herdr.HerdrError:
            pass


def _err(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


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
    last_activity: float = field(default_factory=time.monotonic)
    last_log: tuple[int, int] | None = None
    last_head: str = ""
    fix: bool = False  # 리뷰 지적을 고치는 수정 worker(06). 끝나면 리뷰 없이 병합·검증으로 간다

    def idle(self, repo: Path) -> float:
        """로그 출력 또는 브랜치 커밋이 바뀌면 유휴 시계를 다시 시작한다."""
        try:
            stat = self.proc.job.log.stat()
            log = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            log = None
        head = git.sha(repo, self.branch)
        if log != self.last_log or head != (self.last_head or self.base):
            self.last_activity = time.monotonic()
        self.last_log, self.last_head = log, head
        return time.monotonic() - self.last_activity


def _idle_seconds(r: Run) -> float:
    """시험은 이 시간만 짧게 바꿔 실제 worker의 멈춤을 확인할 수 있다."""
    return r.feat.spec.idle_minutes * 60


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
    try:
        while True:
            _skip_blocked(r)
            while len(active) < cap:
                ready = [tid for tid in _frontier(r) if tid not in active]
                if not ready:
                    break
                a = _start(r, r.feat.tickets[ready[0]], runner)
                if a is None:  # 띄우지 못했다(그 티켓만 실패). 막힌 티켓을 다시 고른다
                    _skip_blocked(r)
                else:
                    active[a.t.id] = a
            if not active:
                return
            tid, code, error = _wait_any(r, active, runner)
            a = active.pop(tid)
            if error and not a.fix:  # 이 worker를 확인하다 오류가 났다. 이 티켓만 실패시킨다
                a.proc.stop()
                a.proc.finish(False)
                _fail(r, a.t, error)
                continue
            try:
                nxt = _finish(r, a, code, others=sorted(active), runner=runner, error=error)
                if nxt is not None:  # 수정 worker를 띄웠다. 끝나면 다시 _finish로 온다
                    active[tid] = nxt
            except (git.GitError, OSError) as e:
                # 브랜치 삭제·검증 실행 오류도 이 티켓의 실패로 한정한다.
                a.proc.stop()
                _reset_integration(r, r.ihead)
                _fail(r, a.t, f"worker 결과 처리 중 오류: {_err(e)}")
    finally:
        # 예상 못 한 오류로 루프를 떠나도 띄운 worker를 남기지 않는다.
        for a in active.values():
            say(f"[{a.t.id}] gs가 멈춰 worker를 끝낸다")
            a.proc.stop()


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


def _wait_any(r: Run, active: dict[str, Active], runner) -> tuple[str, int | None, str]:
    """돌고 있는 worker 중 하나가 끝날 때까지 기다린다. 동시에 끝났으면 r.order 앞쪽부터.

    (티켓, 종료 코드, 오류). 확인 중 오류(실행기·어댑터 판정의 예외)는 그 티켓의 오류로 돌려준다.
    """
    while True:
        result = timed_out = None
        for tid in r.order:
            if tid in active:
                try:
                    code = active[tid].proc.poll()
                    if code is None and active[tid].idle(r.repo) >= _idle_seconds(r):
                        timed_out = timed_out or (
                            tid, None, f"시간 초과: {r.feat.spec.idle_minutes}분 동안 로그 출력·새 커밋 없음")
                except Exception as e:  # noqa: BLE001 — 한 worker의 오류로 코디네이터가 멈추지 않게
                    result = result or (tid, None, f"worker 확인 중 오류: {_err(e)}")
                else:
                    if code is not None:
                        result = result or (tid, code, "")
        # 끝난 티켓이 계속 들어와도 뒤쪽 worker의 활동·시간 초과를 빠뜨리지 않는다.
        if timed_out or result:
            return timed_out or result
        time.sleep(worker.poll_interval(runner))


def _start(r: Run, t: Ticket, runner) -> Active | None:
    """최신 integration 끝에서 티켓 브랜치를 새로 만들고 worker를 띄운다. 띄우지 못하면 실패로 적고 None.

    어떤 오류든(git, herdr, 파일, 어댑터 준비) 이 티켓만 실패시킨다. 이미 띄운 worker가 있으면 끝낸다.
    """
    proc = None
    try:
        ts = r.st.ticket(t.id)
        summary = ""
        if ts.failure_summary:
            path = Path(ts.failure_summary)
            if not path.exists():  # 요약 호출 중 코디네이터가 죽었으면 새 호출로 마무리한다
                failure.summarize(r.repo, path.with_name("failure.log"))
            summary = path.read_text(encoding="utf-8")
        # 실패·중단 worktree는 지우지 않는다. 실행 디렉터리 번호로 브랜치와 경로도 새로 고른다.
        while True:
            rundir = worker.attempt_dir((r.rundir / t.id).resolve())
            rundir.mkdir(parents=True)
            suffix = "" if rundir.name == "1" else f"-retry-{int(rundir.name) - 1}"
            branch = ticket_branch(r.name, t.id) + suffix
            wt = r.rundir / "wt" / (t.id + suffix)
            if not wt.exists() and not git.branch_exists(r.repo, branch):
                break
        base = r.ihead
        job = worker.Job(ticket=t, worktree=wt.resolve(), rundir=rundir)
        _set(r, t.id, status=state.RUNNING, attempts=r.st.ticket(t.id).attempts + 1, branch=branch, pane="",
             worktree=str(job.worktree), log=str(job.log), started_at=state.now(), ended_at="", reason="",
             review={})
        git.ensure_worktree(r.repo, wt, branch, start=base)
        worker.write_brief(job, r.feat.spec, r.name, branch, summary)
        adapter = adapters.for_model(t.model)
        adapter.prepare(job.input)  # agy: 차단 장치가 걸리지 않으면 여기서 거부한다
        worker.write_script(job, adapter)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}", adapter)
        _set(r, t.id, pane=proc.where)
    except adapters.AdapterError as e:
        _fail(r, t, str(e))
        return None
    except Exception as e:  # noqa: BLE001 — 한 티켓의 오류로 코디네이터가 멈추지 않게
        if proc is not None:
            proc.stop()
        _fail(r, t, f"worker를 띄우지 못했다: {_err(e)}")
        return None
    say(f"[{t.id}] 시작: {t.title} ({adapter.name}, {proc.where}, 로그 {job.log})")
    return Active(t, proc, branch, wt, base)


def _finish(r: Run, a: Active, code: int | None, others: list[str] = (), runner=None,
            error: str = "") -> Active | None:
    """끝난 worker 하나를 확인하고, 리뷰한 뒤, 최신 integration을 티켓 브랜치에 합쳐 보고 integration에 병합·검증한다.

    others는 아직 돌고 있는 다른 worker다. integration이 바뀌었을 때 누구 짓인지 가리는 데 쓴다.
    고칠 리뷰 지적이 있으면 수정 worker를 띄워 그 Active를 돌려준다(아니면 None). 수정 worker가 끝나면(a.fix)
    리뷰 없이 병합·검증으로 간다. error는 수정 worker를 확인하다 난 오류(시간 초과 등)다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    commits = git.count(r.repo, f"{a.base}..{branch}")
    note = a.proc.note
    who = "수정 worker" if a.fix else "worker"
    say(f"[{t.id}] {who} 끝: " + (error if error else f"종료 코드 {code}") + f", 새 커밋 {commits}"
        + (f" ({note})" if note else ""))

    def fail(reason: str) -> None:
        a.proc.finish(False)
        _fail(r, t, reason)

    # worker가 integration을 건드렸으면(커밋, 미커밋 변경, 브랜치 이동) 되돌린다. 돌던 worker가 이것 하나뿐이면
    # 이 worker 짓이라 실패로 친다. 여럿이 돌았으면 누구 짓인지 모르니 되돌리기만 하고 경고한다.
    if _reset_integration(r, r.ihead):
        if not others:
            return fail("worker가 integration worktree를 바꿨다(되돌림)")
        say(f"[{t.id}] 경고: integration worktree가 바뀌어 되돌렸다. 함께 돌던 worker({', '.join([t.id, *others])}) 중 "
            "누구 짓인지 모른다")
    if a.fix:
        _end_fix(r, a, code, commits, error)
    else:
        if code != 0:
            why = f"worker 종료 코드 {code}" if code >= 0 else "worker 실행기가 사라졌다"
            return fail(why + (f" ({note})" if note else ""))
        if commits == 0:
            return fail("커밋 없음")
        if not git.is_clean(wt):
            say(f"[{t.id}] 경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")
        try:
            todo = _review(r, a)
        except review.Refused as e:
            return fail(str(e))
        if todo:
            a.proc.finish(True)  # 구현 worker는 성공했다
            nxt = _start_fix(r, a, todo, runner)
            if nxt is not None:
                return nxt

    # 그 사이 다른 티켓이 병합됐을 수 있다. 최신 integration 끝을 티켓 브랜치에 먼저 합쳐 본다.
    if not _catch_up(r, a):
        return fail(CONFLICT)

    # 병합은 커밋하지 않고 두고 검증한다. 통과해야만 gs-ticket 표시를 붙여 커밋한다.
    # 중간에 죽으면 표시 없는 미완 병합만 남고, 다음 실행이 그것을 버리고 티켓을 다시 한다.
    res = git.run(r.iwt, "merge", "--no-ff", "--no-commit", branch, check=False)
    if res.returncode:
        (a.proc.job.rundir / "merge.log").write_text(res.stdout + res.stderr, encoding="utf-8")
        _reset_integration(r, r.ihead)
        return fail("integration 병합 충돌")
    merged = _merge_state(r)  # 검증할 것: 병합 결과 트리
    ok, log = _verify(r, t)
    if not ok:
        _reset_integration(r, r.ihead)
        return fail(f"검증 실패(로그 {log})")
    # 검증하는 동안 다른 worker가 integration(index, HEAD, 병합 상태)을 바꿨으면 검증한 것과 커밋할 것이 다르다
    expected = (r.ihead, f"refs/heads/{integration_branch(r.name)}")
    if _merge_state(r) != merged or merged[:2] != expected or not all(merged):
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 검증한 것과 커밋할 것이 다르다")
    # 커밋은 검증한 트리로 직접 만들고, 브랜치는 r.ihead에 있을 때만 옮긴다(그 사이 바뀌어도 섞이지 않게)
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    new = git.out(r.iwt, "commit-tree", merged[3], "-p", r.ihead, "-p", merged[2], "-m", msg)
    moved = git.run(r.iwt, "update-ref", "-m", f"gs: merge {t.id}", merged[1], new, r.ihead, check=False)
    if moved.returncode:
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 브랜치가 움직였다")
    git.run(r.iwt, "reset", "-q", "--hard", new)  # 병합 상태와 검증이 남긴 파일은 버린다
    git.run(r.iwt, "clean", "-q", "-fd")
    r.ihead = new
    a.proc.finish(True)
    _set(r, t.id, status=state.MERGED, ended_at=state.now())
    say(f"[{t.id}] 검증 통과 → integration 병합")
    return None


def _review(r: Run, a: Active) -> list[dict]:
    """다른 계열이 이 티켓 diff(최신 integration과의 merge-base 기준)를 리뷰한다. 고칠 지적을 돌려준다.

    병합·검증처럼 루프 안에서 하나씩 돈다(다른 worker는 그동안 각자 돈다). 오래 걸리는 수정은 worker로 따로 띄운다.
    """
    t = a.t
    say(f"[{t.id}] 리뷰: {t.reviewer}")
    rec = review.run(repo=r.repo, worktree=a.wt.resolve(), rdir=a.proc.job.rundir / "review", base=r.ihead,
                     branch=a.branch, ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(), model=t.model,
                     reviewer=t.reviewer)
    _set(r, t.id, review=rec)
    say(f"[{t.id}] 리뷰 끝: {review.counts(rec)}" + (f" — {rec['note']}" if rec["note"] else ""))
    return review.fixes(rec)


def _start_fix(r: Run, a: Active, todo: list[dict], runner) -> Active | None:
    """같은 구현 모델로 수정 worker를 한 번 띄운다(같은 브랜치·worktree, 지적 첨부). 띄우지 못하면 None.

    띄우지 못해도 티켓은 실패가 아니다: 지적을 고치지 못한 채 남기고 리뷰한 구현을 병합·검증한다.
    """
    t = a.t
    job = worker.Job(ticket=t, worktree=a.wt.resolve(), rundir=a.proc.job.rundir / "fix")
    proc = None
    try:
        job.rundir.mkdir(parents=True)
        worker.write_brief(job, r.feat.spec, r.name, a.branch)
        with job.brief.open("a", encoding="utf-8") as f:
            f.write(review.fix_brief(todo))
        adapter = adapters.for_model(t.model)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        base = git.sha(r.repo, a.branch)
        _set(r, t.id, log=str(job.log), pane="")  # 재실행 때 살아 남은 수정 worker를 run.sh로 찾게
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:fix", adapter)
        _set(r, t.id, pane=proc.where)
    except Exception as e:  # noqa: BLE001 — 수정은 덤이다. 리뷰한 구현은 그대로 병합한다
        if proc is not None:
            proc.stop()
        _note_fix(r, t, f"수정 worker를 띄우지 못했다: {_err(e)}")
        return None
    say(f"[{t.id}] 수정 worker 시작: 지적 {len(todo)}개 ({adapter.name}, {proc.where}, 로그 {job.log})")
    return Active(t, proc, a.branch, a.wt, base, fix=True)


def _note_fix(r: Run, t: Ticket, msg: str) -> None:
    rec = r.st.ticket(t.id).review
    rec["fix"] = msg
    _set(r, t.id, review=rec)
    say(f"[{t.id}] {msg}")


def _end_fix(r: Run, a: Active, code: int | None, commits: int, error: str) -> None:
    """수정 worker가 끝났다. 성공이면 지적을 고친 것으로 적는다(재리뷰 없음).

    실패(종료 코드, 시간 초과, 커밋 없음, 리뷰한 커밋을 지움)면 수정 커밋을 버리고 리뷰한 구현으로 되돌린다.
    어느 쪽이든 티켓은 병합·검증으로 간다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    kept = git.run(r.repo, "merge-base", "--is-ancestor", a.base, branch, check=False).returncode == 0
    why = error or ("" if code == 0 else f"종료 코드 {code}") or ("" if kept else "리뷰한 커밋을 지웠다") \
        or ("" if commits else "커밋 없음")
    if error:
        a.proc.stop()
    if not why:
        if not git.is_clean(wt):
            say(f"[{t.id}] 경고: 수정 worker가 커밋 안 된 변경을 남겼다(병합에 들어가지 않는다)")
        rec = r.st.ticket(t.id).review
        for f in review.fixes(rec):
            f["fixed"] = True
        _note_fix(r, t, f"수정 커밋 {commits}개(재리뷰 없음, verify만 돈다)")
        return
    a.proc.finish(False)  # 들여다볼 수 있게 pane을 남긴다
    git.run(wt, "merge", "--abort", check=False)
    git.run(wt, "checkout", "-q", "-f", branch)
    git.run(wt, "reset", "-q", "--hard", a.base)
    _note_fix(r, t, f"수정 worker 실패({why}): 수정을 버리고 리뷰한 구현을 병합·검증한다. fix 지적은 남는다")


def _merge_state(r: Run) -> tuple[str, str, str, str]:
    """(HEAD, HEAD가 가리키는 브랜치, MERGE_HEAD, index 트리). 읽지 못한 값은 빈 문자열(그러면 비교에서 다르다)."""
    def get(*args: str) -> str:
        cp = git.run(r.iwt, *args, check=False)
        return cp.stdout.strip() if cp.returncode == 0 else ""
    return (get("rev-parse", "-q", "--verify", "HEAD"), get("symbolic-ref", "-q", "HEAD"),
            get("rev-parse", "-q", "--verify", "MERGE_HEAD"), get("write-tree"))


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
    (a.proc.job.rundir / "merge.log").write_text(
        f"최신 integration: {r.ihead}\n충돌 파일: {detail}\n{res.stdout}{res.stderr}", encoding="utf-8")
    say(f"[{a.t.id}] 최신 integration({r.ihead[:8]})과 충돌: {detail}")
    return False


def _fail(r: Run, t: Ticket, reason: str) -> bool:
    ts = r.st.ticket(t.id)
    paths = list(ts.failed_worktrees)
    if ts.worktree and Path(ts.worktree).exists() and ts.worktree not in paths:
        paths.append(ts.worktree)
    failures = ts.failures + 1
    # 시작 준비 단계에서 실패했더라도 증거를 쓸 디렉터리는 확보한다.
    directory = Path(ts.log).parent if ts.log else worker.attempt_dir(r.rundir / t.id)
    directory.mkdir(parents=True, exist_ok=True)
    log = failure.record(directory, reason, [directory / "worker.log", directory / "verify.log", directory / "merge.log"])
    retry = failures < 2
    summary = str(log.with_name("failure-summary.md")) if retry else ts.failure_summary
    # 판단 모델 호출 전에 실패 횟수를 남긴다. 호출 도중 gs가 죽어도 재시도 횟수가 늘지 않는다.
    _set(r, t.id, status=state.PENDING if retry else state.FAILED, reason=reason, ended_at=state.now(),
         failures=failures, failed_worktrees=paths, failure_summary=summary)
    if retry:
        failure.summarize(r.repo, log)
    say(f"[{t.id}] 실패: {reason}")
    if retry:
        say(f"[{t.id}] 같은 모델({t.model})로 최신 integration에서 한 번 재시도한다")
    return False


def _verify(r: Run, t: Ticket) -> tuple[bool, Path]:
    log = Path(r.st.ticket(t.id).log).parent / "verify.log"
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
        ts = r.st.tickets[tid]
        left = len(review.remaining(ts.review))
        say(f"  {tid} {LABEL[labels[tid]]}" + (f" — {ts.reason}" if ts.reason else "")
            + (f" · 남은 리뷰 지적 {left}" if left else ""))
    if url:
        say(f"■ PR: {url}")
