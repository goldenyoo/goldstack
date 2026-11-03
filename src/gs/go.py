"""`gs go`: 티켓을 위상 순서로 하나씩 worker에 맡기고 integration에 모아 PR을 연다(최소형, 02).

순차 실행, 재시도 없음, 리뷰 없음, PR 병합 없음. 병렬(04), 리뷰(06), 재시도(07), 병합(08)은 뒤 티켓.
진행 상태는 `.work/<f>/run/state.json`에 남기고(03), 다시 실행하면 병합된 티켓은 건너뛰고 나머지를 이어 간다.
같은 feature에 `gs go`는 하나만 돈다(run/lock).
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import git, graph, herdr, state, worker
from .check import check
from .feature import Feature, Ticket

MAIN = "main"
BASE = "origin/main"  # PR 대상. 로컬 main은 뒤처지거나 앞설 수 있어 쓰지 않는다


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


def _loop(r: Run) -> None:
    say(f"■ 순서: {' '.join(r.order)}")
    say(f"■ 상태: {state.path(r.rundir)}")
    runner = worker.make_runner(r.repo, r.name)
    bad: set[str] = set()
    for tid in r.order:
        t = r.feat.tickets[tid]
        blockers = [d for d in r.g[tid] if d in bad]
        if blockers:
            _set(r, tid, status=state.SKIPPED, reason=f"막힘: {', '.join(blockers)}", ended_at=state.now())
            bad.add(tid)
            say(f"[{tid}] 건너뜀: {', '.join(blockers)} 실패")
            continue
        # 병합 여부는 integration의 gs-ticket 표시로 확인한다. state가 merged인데 표시가 없으면 다시 한다.
        if _already_merged(r, tid):
            if r.st.tickets[tid].status != state.MERGED:
                _set(r, tid, status=state.MERGED, reason="", ended_at=state.now())
            r.prior.add(tid)
            say(f"[{tid}] 이미 병합됨")
            continue
        if r.st.tickets[tid].status == state.MERGED:
            say(f"[{tid}] state는 병합이라는데 integration에 표시가 없다. 다시 한다")
        if not _one(r, t, runner):
            bad.add(tid)


def _one(r: Run, t: Ticket, runner) -> bool:
    branch = ticket_branch(r.name, t.id)
    wt = r.rundir / "wt" / t.id
    base = git.sha(r.iwt, "HEAD")
    git.remove_worktree(r.repo, wt, branch)  # 02는 이어가기가 없다: 지난 시도는 버리고 새로
    git.ensure_worktree(r.repo, wt, branch, start=base)
    job = worker.Job(ticket=t, worktree=wt.resolve(), rundir=(r.rundir / t.id).resolve())
    job.rundir.mkdir(parents=True, exist_ok=True)
    job.log.unlink(missing_ok=True)
    _set(r, t.id, status=state.RUNNING, attempts=r.st.ticket(t.id).attempts + 1, branch=branch, pane="",
         log=str(job.log), started_at=state.now(), ended_at="", reason="")
    spec = r.feat.spec
    worker.write_brief(job, spec, r.name, branch)
    try:
        cmd = worker.worker_command(t)
    except ValueError as e:
        return _fail(r, t, str(e))
    worker.write_script(job, cmd)
    def started(where: str) -> None:
        _set(r, t.id, pane=where)
        say(f"[{t.id}] 시작: {t.title} ({where}, 로그 {job.log})")

    code = worker.run(job, runner, f"gs:{r.name}:{t.id}", on_start=started)
    commits = git.count(r.repo, f"{base}..{branch}")
    say(f"[{t.id}] worker 끝: 종료 코드 {code}, 새 커밋 {commits}")
    # worker가 integration을 건드렸으면(커밋, 미커밋 변경, 브랜치 이동) 되돌리고 실패로 친다
    if _reset_integration(r, base):
        runner.finish(False)
        return _fail(r, t, "worker가 integration worktree를 바꿨다(되돌림)")
    if code != 0:
        runner.finish(False)
        return _fail(r, t, f"worker 종료 코드 {code}" if code >= 0 else "worker 실행기가 사라졌다")
    if commits == 0:
        runner.finish(False)
        return _fail(r, t, "커밋 없음")
    if not git.is_clean(wt):
        say(f"[{t.id}] 경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")

    # 병합은 커밋하지 않고 두고 검증한다. 통과해야만 gs-ticket 표시를 붙여 커밋한다.
    # 중간에 죽으면 표시 없는 미완 병합만 남고, 다음 실행이 그것을 버리고 티켓을 다시 한다.
    res = git.run(r.iwt, "merge", "--no-ff", "--no-commit", branch, check=False)
    if res.returncode:
        _reset_integration(r, base)
        runner.finish(False)
        return _fail(r, t, "integration 병합 충돌")
    ok, log = _verify(r, t)
    if not ok:
        _reset_integration(r, base)
        runner.finish(False)
        return _fail(r, t, f"검증 실패(로그 {log})")
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    git.run(r.iwt, "commit", "-q", "--no-verify", "-m", msg)  # index만 커밋한다
    _reset_integration(r)  # 검증이 남긴 파일은 버린다
    runner.finish(True)
    _set(r, t.id, status=state.MERGED, ended_at=state.now())
    say(f"[{t.id}] 검증 통과 → integration 병합")
    return True


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
    return (f"`gs go {r.name}`" + (f" --only {','.join(r.only)}" if r.only else "") + " 결과(최소 엔진, 02).\n\n"
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
