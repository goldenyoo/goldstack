"""`gs go`: 시작할 수 있는 티켓을 max_workers개까지 동시에 worker에 맡기고 integration에 모아 PR을 연다.

병렬 실행(04). 병합·검증은 한 번에 하나씩. 실패·멈춤은 같은 모델로 한 번 재시도한다(07).
worker가 성공하면 병합 전에 다른 계열이 그 티켓 diff를 리뷰하고, 고칠 지적이 있으면 같은 모델로 수정 worker를
한 번 띄운다(06, review.py). 티켓에 second_reviewer가 있으면 두 리뷰를 동시에 띄우고 지적을 합쳐 수정은 한 번이다.
gs가 띄우는 agy 호출(worker·리뷰·수정·재시도)을 state에 세고 config `[agy] max_calls_per_run`에 닿으면 더 띄우지 않는다.
재리뷰는 없고 verify만 돈다. 끝에는 보고서·PR·base 검증·revert를 한다(08).
진행 상태는 `.goldstack/work/<f>/run/state.json`에 남기고(03), 다시 실행하면 병합된 티켓은 건너뛰고 나머지를 이어 간다.
같은 feature에 `gs go`는 하나만 돈다(run/lock).
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import adapters, clean, config, failure, finish, git, graph, herdr, notify, report, review, setup, state, verify, worker
from .check import check
from .feature import Feature, Ticket, work_rel

CONFLICT = "conflict"
HEARTBEAT_SECONDS = 60  # 상태가 그대로여도 이 간격마다 state.json을 다시 쓴다(진행 바가 오래된 실행으로 보고 지우지 않게)


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
    cfg: config.Config  # 실행 시작 시 읽은 설정을 모든 모델 호출에 함께 쓴다
    st: state.State | None = None  # 상태의 원천. 요약·PR 본문도 이것을 읽는다
    g: dict[str, list[str]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    prior: set[str] = field(default_factory=set)  # 이번 실행 전에 이미 병합돼 있던 티켓(표시용)
    ihead: str = ""  # gs가 아는 integration 끝. 병합할 때만 움직인다
    saved: float = 0.0  # 마지막 save()의 time.monotonic(). heartbeat가 본다
    history_median_s: float | None = None  # 실행 시작에 한 번 읽은 다른 feature의 ETA 표본 중앙값

    @property
    def name(self) -> str:
        return self.feat.name

    @property
    def remote(self) -> str:
        return self.cfg.git.remote

    @property
    def base(self) -> str:
        """PR 대상 브랜치 이름(예: main)."""
        return self.cfg.git.base

    @property
    def base_ref(self) -> str:
        """원격의 base(예: origin/main). 로컬 base 브랜치는 뒤처지거나 앞설 수 있어 쓰지 않는다."""
        return f"{self.remote}/{self.base}"

    @property
    def rundir(self) -> Path:
        return self.feat.root / "run"

    @property
    def iwt(self) -> Path:
        return self.rundir / "wt" / "integration"

    def save(self) -> None:
        self.st.progress = state.calculate_progress(
            self.st, self.order, self.feat.spec.max_workers, prior=self.prior,
            models={tid: self.feat.tickets[tid].model for tid in self.order},
            history_median_s=self.history_median_s)
        state.save(self.rundir, self.st)
        self.saved = time.monotonic()


def say(msg: str) -> None:
    print(msg, flush=True)


def go(repo: Path, name: str, only: list[str] | None = None) -> int:
    feat, _ = check(repo, name, only)
    for p in feat.problems:
        print(p, file=sys.stderr)
    if feat.errors:
        print(f"gs go: 검사 오류 {len(feat.errors)}개. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    cfg, _ = config.load(repo)  # check가 이미 검사했다(오류면 위에서 끝났다). 경고는 check가 보였다
    r = Run(repo, feat, only, cfg)
    lock = state.Lock(r.rundir)
    try:
        lock.acquire()
    except state.Locked as e:
        print(f"gs go: {e}. 같은 feature에 gs go는 하나만 돈다. 아무것도 띄우지 않았다.", file=sys.stderr)
        return 1
    try:
        url, finished = None, False
        try:
            git.run(repo, "fetch", "-q", r.remote, r.base)
            _require_committed(r)
            _begin(r)
            if _finished_after_clean(r):
                url, finished = r.st.finish.get("url"), r.st.finish["phase"] == "verified"
                say(f"■ 이미 끝남: {r.name} ({r.st.finish['phase']})")
                clean.integration(r)  # 지난 자동 정리가 원격 삭제에서만 실패했을 수 있다
            else:
                prepared = _prepare_integration(r)
                _resume_merged(r)
                # 병합 확인·base 검증·revert를 먼저 회복한다. 새 worker가 미완료 PR의 head를 바꾸지 않게 한다.
                if not prepared:
                    finished = False
                elif r.st.finish.get("phase") in finish.RESUME_PHASES:
                    r.ihead = git.sha(r.iwt, "HEAD")
                    # 회복 뒤 새 범위를 이어 돌릴 수 있어, 마지막 마무리까지 integration을 둔다.
                    url, finished = _finish_run(r, cleanup=False)
                else:
                    finished = True
                if finished:
                    _loop(r)
                    url, finished = _finish_run(r)
        except git.GitError as e:
            print(f"gs go: git 오류: {e}", file=sys.stderr)
            finished = False
            url = r.st.finish.get("url") if r.st else None
        except herdr.HerdrError as e:
            # git 오류처럼 요약·알림까지 간다. 종료 코드는 1(finished가 False라 ok도 False).
            print(f"gs go: herdr 오류: {e}", file=sys.stderr)
            finished = False
            url = r.st.finish.get("url") if r.st else None
        finally:
            if r.st is not None:
                r.st.finished_at = state.now()
                for ts in r.st.tickets.values():
                    state.end_phase(ts, r.st.finished_at)
                r.st.phase = ""
                r.save()
    finally:
        lock.release()
    ok = finished and all(r.st.tickets[tid].status == state.MERGED for tid in r.order)
    if r.st is not None:
        _summary(r, url)
        if cfg.notify.telegram:
            _notify(r, url, ok)
    return 0 if ok else 1


def _finish_run(r: Run, *, cleanup: bool = True) -> tuple[str | None, bool]:
    r.st.phase = "finish"
    r.save()
    try:
        return finish.run(r, cleanup=cleanup)
    finally:
        r.st.phase = ""
        r.save()


def _begin(r: Run) -> None:
    """state.json을 읽어 이번 실행을 시작한다. 지난 실행이 죽어 running으로 남은 티켓은 실패로 세지 않는다."""
    st = state.load(r.rundir, r.name)
    r.g = _graph(r)
    r.order = graph.topo_order(r.g)
    for tid, ts in sorted(st.tickets.items()):
        state.end_phase(ts, st.updated_at or state.now())
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
    st.pid, st.only, st.started_at, st.finished_at, st.phase = os.getpid(), r.only, state.now(), "", ""
    st.agy_calls = 0  # 상한은 실행마다다(spec 1-9)
    r.st = st
    r.history_median_s = state.load_eta_history(r.repo, r.name)
    r.save()


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
    if ts.status != state.RUNNING:
        state.end_phase(ts, ts.ended_at or state.now())
    r.save()


def _phase(r: Run, tid: str, phase: str, model: str, *, attempt: int | None = None) -> None:
    state.begin_phase(r.st.ticket(tid), phase, model, attempt=attempt)
    r.save()


def _require_committed(r: Run) -> None:
    rel = work_rel(r.name)
    # report.md는 gs가 integration에서 쓴다. 호출 worktree의 보고서가 뒤처져도 티켓 재개를 막지 않는다.
    inputs = [f"{rel}/spec.md", f"{rel}/tickets"]
    if git.out(r.repo, "status", "--porcelain", "--", *inputs) or git.run(r.repo, "diff", "--quiet", r.base_ref, "--",
                                                                       *inputs, check=False).returncode:
        raise git.GitError(f"{rel}가 {r.base_ref}와 다르다. worker는 {r.base_ref} 기준으로 일하므로 먼저 커밋하고 push하라")


def _reset_integration(r: Run, to: str = "HEAD") -> bool:
    """integration worktree는 gs만 쓴다. 남은 병합·변경을 버리고 to로 되돌린다. 무언가 버렸으면 True."""
    dirty = not setup.is_clean(r.iwt)
    if git.run(r.iwt, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
        git.run(r.iwt, "merge", "--abort", check=False)
        dirty = True
    moved = git.sha(r.iwt, "HEAD") != git.sha(r.iwt, to)
    git.run(r.iwt, "reset", "-q", "--hard", to)
    setup.clean(r.iwt, "-q", "-fd")
    return dirty or moved


def _finished_after_clean(r: Run) -> bool:
    """정리된 완료 범위는 재생성하지 않는다. 새 티켓·남긴 worktree가 있으면 기존 재개 흐름으로 간다."""
    return bool(r.st.finish.get("phase") in finish.BASE_REPORT_PHASES and r.st.finish.get("base_report_tried")
            and not r.iwt.exists()
            and not git.out(r.repo, "for-each-ref", "--format=%(refname)", f"refs/heads/gs/{r.name}/")
            and all(r.st.tickets[tid].status == state.MERGED for tid in r.order)
            and not any(ts.kept_worktrees for ts in r.st.tickets.values()))


def _prepare_integration(r: Run) -> bool:
    branch = integration_branch(r.name)
    start = r.base_ref
    # 정리 뒤 새 wave·남긴 worktree를 처리할 때는 보존된 head로 기존 재개 판단을 유지한다.
    # 객체가 GC됐으면 base로 돌아간다. 완료 범위만의 재개는 위에서 이미 끝낸다.
    head = r.st.finish.get("head")
    if r.st.finish.get("phase") in finish.BASE_REPORT_PHASES and head:
        if git.run(r.repo, "cat-file", "-e", f"{head}^{{commit}}", check=False).returncode == 0:
            start = head
    git.ensure_worktree(r.repo, r.iwt, branch, start=start)
    if _reset_integration(r):
        say("■ integration worktree에 남은 병합·변경을 버렸다(지난 실행이 중간에 끝난 흔적)")
    # 앞 wave가 base에 병합된 뒤라면 원격 base를 받아 둔다. 보통 fast-forward라 force push가 필요 없다.
    # base가 이 feature의 병합을 revert했으면 그 revert를 되돌린 커밋까지 합친다(feature 코드를 잃지 않는다).
    finish.merge_base(r)
    say(f"■ integration: {branch} @ {git.sha(r.iwt, 'HEAD')[:8]} ({r.iwt})")
    if r.cfg.worktree.setup.strip() and not setup.marker(r.iwt).exists():
        directory = worker.attempt_dir(r.rundir / "integration")
        r.st.phase = "setup"
        r.save()
        try:
            say("■ integration 준비 중")
            res = setup.run(r.cfg, r.iwt, directory / "setup.log")
        finally:
            r.st.phase = ""
        if not res.ok:
            r.st.finish.update(phase="setup_failed", outcome="준비 실패 → 병합 안 함")
            r.save()
            report.write(r, "integration 준비 실패. setup.log를 확인하라.")
            return False
        setup.remember(r.iwt)
    return True


def _graph(r: Run) -> dict[str, list[str]]:
    g = {t.id: t.blocked_by for t in r.feat.tickets.values()}
    if r.only is not None:
        g, _, _ = graph.subgraph(g, r.only)
    return g


def _already_merged(r: Run, tid: str) -> bool:
    return bool(git.out(r.iwt, "log", "-1", "--format=%H", "--fixed-strings", f"--grep={trailer(r.name, tid)}"))


def _resume_merged(r: Run) -> None:
    """integration의 표시로 상태를 회복하고, 중단 전에 남은 성공 worktree를 정리한다."""
    for tid in dict.fromkeys([*r.order, *r.st.tickets]):
        ts = r.st.tickets[tid]
        if tid not in r.order and ts.status != state.MERGED:
            continue
        if _already_merged(r, tid):
            if ts.status != state.MERGED:
                _set(r, tid, status=state.MERGED, reason="", ended_at=state.now())
            if tid in r.order:
                r.prior.add(tid)
                say(f"[{tid}] 이미 병합됨")
            _cleanup_merged(r, tid)
        elif ts.status == state.MERGED and tid in r.order:
            say(f"[{tid}] state는 병합이라는데 integration에 표시가 없다. 다시 한다")
            _set(r, tid, status=state.PENDING, failures=0, failure_summary="")
        _recheck_kept(r, tid)
    r.save()


def _recheck_kept(r: Run, tid: str) -> None:
    """남긴 worktree 중 병합된 지금 시도의 것이 아닌 옛 경로를 다시 본다(티켓이 대기로 돌아갔거나 재시도할 때).

    경로가 없거나 미커밋 변경이 없으면 정리하고 목록에서 뺀다. 병합된 티켓의 지금 worktree는 _cleanup_merged가 본다.
    """
    ts = r.st.tickets[tid]
    current = ts.worktree if ts.status == state.MERGED else None
    keep = [p for p in ts.kept_worktrees if p == current or not _drop_kept(r, tid, Path(p))]
    if keep != ts.kept_worktrees:
        ts.kept_worktrees = keep
        r.save()


def _drop_kept(r: Run, tid: str, path: Path) -> bool:
    """남긴 옛 worktree 하나를 정리한다. 목록에서 빼도 되면 True. 정리 오류는 경고뿐이다(목록에 남긴다)."""
    try:
        if not path.exists():
            say(f"[{tid}] 남긴 worktree가 없어 목록에서 뺀다: {path}")
            return True
        wt = path.resolve()
        suffix = wt.name.removeprefix(tid)
        valid = wt.parent == (r.rundir / "wt").resolve() and wt.name.startswith(tid) and (
            suffix == "" or (suffix.startswith("-retry-") and suffix.removeprefix("-retry-").isdigit()))
        current = git.worktrees(r.repo)
        if not valid or wt not in current or wt == r.iwt.resolve():
            say(f"[{tid}] 경고: 남긴 경로가 이 티켓의 worktree가 아니라 정리하지 않는다: {path}")
            return False
        if not git.is_clean(wt):
            say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
            return False
        branch = ticket_branch(r.name, tid) + suffix
        if current[wt] != branch:
            # 분리 HEAD나 다른 브랜치의 커밋은 이 worktree만 가리킬 수 있다. 지우면 잃으니 남긴다.
            say(f"[{tid}] 경고: 남긴 worktree의 브랜치가 {branch}가 아니라 정리하지 않는다: {wt}")
            return False
        git.run(r.repo, "worktree", "remove", str(wt))  # --force 없이: 검사 뒤 생긴 변경은 git이 지킨다
        say(f"[{tid}] 남긴 worktree 정리: {wt}")
        if git.branch_exists(r.repo, branch):
            included = git.run(r.repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}",
                               f"refs/heads/{integration_branch(r.name)}", check=False)
            if included.returncode:
                say(f"[{tid}] 경고: 브랜치 끝이 integration에 포함되지 않아 남긴다: {branch}")
            else:
                git.run(r.repo, "branch", "-D", branch)
        return True
    except (git.GitError, OSError) as e:
        say(f"[{tid}] 경고: 남긴 worktree 정리 실패: {_err(e)}")
        return False


def _cleanup_merged(r: Run, tid: str) -> None:
    """성공한 시도만 정리한다. 경로·브랜치 기록은 재시작과 증거용으로 남긴다. 정리 오류는 경고뿐이다."""
    ts = r.st.tickets[tid]
    if ts.status != state.MERGED:
        return
    try:
        wt = Path(ts.worktree).resolve() if ts.worktree else None
        if wt in {Path(p).resolve() for p in ts.failed_worktrees}:
            return
        # state가 가리키더라도 integration이나 티켓 밖의 경로·브랜치는 지우지 않는다.
        prefix = ticket_branch(r.name, tid)
        suffix = ts.branch.removeprefix(prefix)
        valid = ts.branch == prefix or (ts.branch.startswith(prefix + "-retry-")
                                       and suffix.removeprefix("-retry-").isdigit())
        if (not valid or ts.branch == integration_branch(r.name) or wt == r.iwt.resolve()
                or (wt and wt != (r.rundir / "wt" / (tid + suffix)).resolve())):
            say(f"[{tid}] 경고: 정리 대상이 티켓 worktree·브랜치가 아니다: {ts.worktree}, {ts.branch}")
            return
        current = git.worktrees(r.repo)
        if wt and wt.exists():
            if wt not in current or current[wt] != ts.branch:
                say(f"[{tid}] 경고: worktree의 브랜치가 달라 정리를 건너뛴다: {wt}")
                return
            if not git.is_clean(wt):
                if ts.worktree not in ts.kept_worktrees:
                    _set(r, tid, kept_worktrees=[*ts.kept_worktrees, ts.worktree])
                say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
                return
        if wt and wt in current:
            # 검사 뒤 생긴 변경도 git이 지키도록 --force는 쓰지 않는다.
            git.run(r.repo, "worktree", "remove", str(wt))
            say(f"[{tid}] worktree 정리: {wt}")
        if ts.worktree in ts.kept_worktrees:
            _set(r, tid, kept_worktrees=[p for p in ts.kept_worktrees if p != ts.worktree])
        if git.branch_exists(r.repo, ts.branch):
            included = git.run(r.repo, "merge-base", "--is-ancestor", f"refs/heads/{ts.branch}",
                               f"refs/heads/{integration_branch(r.name)}", check=False)
            if included.returncode:
                say(f"[{tid}] 경고: 브랜치 끝이 integration에 포함되지 않아 남긴다: {ts.branch}")
                return
            git.run(r.repo, "branch", "-D", ts.branch)
    except (git.GitError, OSError) as e:
        say(f"[{tid}] 경고: worktree·브랜치 정리 실패: {_err(e)}")


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
            # 결과 처리가 끝날 때까지 정리 대상에 둔다. _finish·_fail이 예외를 내도 finally에서 거둔다.
            a = active[tid]
            if error and not a.fix:  # 이 worker를 확인하다 오류가 났다. 이 티켓만 실패시킨다
                a.proc.stop()
                a.proc.finish(False)
                _fail(r, a.t, error)
                active.pop(tid)
                continue
            try:
                nxt = _finish(r, a, code, others=sorted(t for t in active if t != tid), runner=runner, error=error)
                active.pop(tid)
                if nxt is not None:  # 수정 worker를 띄웠다. 끝나면 다시 _finish로 온다
                    active[tid] = nxt
            except (git.GitError, OSError) as e:
                # 병합·검증 실행 오류는 이 티켓의 실패로 한정한다. 리뷰 단계의 뜻밖의 오류는 _review가 막는다.
                a.proc.stop()
                _reset_integration(r, r.ihead)
                _fail(r, a.t, f"worker 결과 처리 중 오류: {_err(e)}")
                active.pop(tid)
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
        if time.monotonic() - r.saved >= HEARTBEAT_SECONDS:
            r.save()  # heartbeat: 바뀐 것이 없어도 mtime·경과 시간을 새로 쓴다
        time.sleep(worker.poll_interval(runner))


def _start(r: Run, t: Ticket, runner) -> Active | None:
    """최신 integration 끝에서 티켓 브랜치를 새로 만들고 worker를 띄운다. 띄우지 못하면 실패로 적고 None.

    어떤 오류든(git, herdr, 파일, 어댑터 준비) 이 티켓만 실패시킨다. 이미 띄운 worker가 있으면 끝낸다.
    """
    proc = None
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _fail(r, t, f"agy 한도: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿아 worker를 띄우지 않았다"
                    "(config agy.max_calls_per_run)", retry=False)
        return None
    try:
        _recheck_kept(r, t.id)
        ts = r.st.ticket(t.id)
        summary = ""
        if ts.failure_summary:
            path = Path(ts.failure_summary)
            if not path.exists():  # 요약 호출 중 코디네이터가 죽었으면 새 호출로 마무리한다
                failure.summarize(r.repo, path.with_name("failure.log"), r.cfg)
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
        started = state.now()
        preparing = bool(r.cfg.worktree.setup.strip())
        state.begin_phase(ts, "setup" if preparing else "worker", "" if preparing else t.model,
                          attempt=int(rundir.name), at=started)
        _set(r, t.id, status=state.RUNNING, attempts=r.st.ticket(t.id).attempts + 1, branch=branch, pane="",
             worktree=str(job.worktree), log=str(job.log), started_at=started, ended_at="", reason="",
             review={}, second_review={})
        git.ensure_worktree(r.repo, wt, branch, start=base)
        if preparing:
            say(f"[{t.id}] 준비 중")
            if not setup.run(r.cfg, wt, rundir / "setup.log").ok:
                _fail(r, t, "준비 실패", retry=False)
                return None
            _phase(r, t.id, "worker", t.model)
        worker.write_brief(job, r.feat.spec, r.name, branch, summary)
        adapter = adapters.for_model(t.model, r.cfg.models)
        adapter.prepare(job.input)  # agy: 차단 장치가 걸리지 않으면 여기서 거부한다
        worker.write_script(job, adapter)
        _count_agy(r, t.model)
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

    # 시간 초과·확인 오류면 worker가 아직 돌고 있다. 무엇을 판정하기 전에 먼저 끝낸다: 어느 경로로 돌아가든
    # (integration 변경 실패 포함) 살아 남아 재시도 worker와 함께 integration·브랜치를 바꾸지 못하게.
    if error or code is None:
        a.proc.stop()

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
    _phase(r, t.id, "verify", t.model)
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
    res, log = _verify(r, t)
    if not res.ok:
        _reset_integration(r, r.ihead)
        return fail(f"검증 시간 초과({res.minutes}분, 로그 {log})" if res.timed_out else f"검증 실패(로그 {log})")
    # 검증하는 동안 다른 worker가 integration(index, HEAD, 병합 상태)을 바꿨으면 검증한 것과 커밋할 것이 다르다
    expected = (r.ihead, f"refs/heads/{integration_branch(r.name)}")
    if _merge_state(r) != merged or merged[:2] != expected or not all(merged):
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 검증한 것과 커밋할 것이 다르다")
    # 커밋은 검증한 트리로 직접 만들고, 브랜치는 r.ihead에 있을 때만 옮긴다(그 사이 바뀌어도 섞이지 않게)
    _phase(r, t.id, "finish", t.model)
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    new = git.out(r.iwt, "commit-tree", merged[3], "-p", r.ihead, "-p", merged[2], "-m", msg)
    moved = git.run(r.iwt, "update-ref", "-m", f"gs: merge {t.id}", merged[1], new, r.ihead, check=False)
    if moved.returncode:
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 브랜치가 움직였다")
    git.run(r.iwt, "reset", "-q", "--hard", new)  # 병합 상태와 검증이 남긴 파일은 버린다
    setup.clean(r.iwt, "-q", "-fd")
    r.ihead = new
    a.proc.finish(True)
    _set(r, t.id, status=state.MERGED, ended_at=state.now())
    say(f"[{t.id}] 검증 통과 → integration 병합")
    _cleanup_merged(r, t.id)
    return None


def _review(r: Run, a: Active) -> list[dict]:
    """다른 계열이 이 티켓 diff(최신 integration과의 merge-base 기준)를 리뷰한다. 고칠 지적을 돌려준다.

    병합·검증처럼 루프 안에서 하나씩 돈다(다른 worker는 그동안 각자 돈다). 오래 걸리는 수정은 worker로 따로 띄운다.
    second_reviewer가 있으면 두 리뷰를 동시에 띄우고, 둘 다 끝나면 fix 지적을 합쳐 돌려준다(수정은 한 번).
    그때는 한쪽이 거부·실패·시간 초과여도 다른 쪽으로 간다. 둘 다 거부면 하나일 때처럼 티켓 실패다.
    agy 리뷰는 이번 실행의 상한에 닿았으면 띄우지 않고 "건너뜀(한도)"으로 적는다.
    """
    t = a.t
    base = a.proc.job.rundir
    slots = [("review", t.reviewer, base / "review")]
    if t.second_reviewer:
        slots.append(("second_review", t.second_reviewer, base / f"review-{t.second_reviewer}"))
    recs: dict[str, dict] = {}
    refused: list[review.Refused] = []
    launch: list[tuple[str, str, Path]] = []
    for key, who, rdir in slots:
        try:
            review.require_other_family(t.model, who)
        except review.Refused as e:
            if len(slots) == 1:
                raise  # 같은 계열은 거부(_finish가 티켓 실패로 처리)
            refused.append(e)
            recs[key] = review.record(who, str(e))
            continue
        if _is_agy(who) and state.agy_reached(r.st, _agy_limit(r)):
            recs[key] = review.record(who, f"{review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다")
            continue
        launch.append((key, who, rdir))
    if len(refused) == len(slots):
        raise refused[0]
    for _, who, _ in launch:
        _count_agy(r, who)
    names = "+".join(who for _, who, _ in launch) or "+".join(who for _, who, _ in slots)
    _phase(r, t.id, "review", names)
    say(f"[{t.id}] 리뷰: {names}")
    jobs = [dict(repo=r.repo, worktree=a.wt.resolve(), rdir=rdir, base=r.ihead, branch=a.branch,
                 ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(), model=t.model, reviewer=who, cfg=r.cfg)
            for _, who, rdir in launch]
    if len(jobs) == 1:  # 하나면 이 스레드에서 부른다(second_reviewer가 없는 티켓의 흐름 그대로)
        try:
            results: list = [review.run(**jobs[0])]
        except (review.Refused, git.GitError):
            raise
        except Exception as e:  # noqa: BLE001 — 아래에서 리뷰 실패로 적는다
            results = [e]
    else:
        results = review.run_together(jobs)
    errors = []
    for (key, who, rdir), res in zip(launch, results):
        if isinstance(res, git.GitError):
            errors.append(res)
            res = review.record(who, f"리뷰 실패(리뷰 없음, verify만으로 병합한다): git 오류 {_err(res)}", rdir)
        elif isinstance(res, BaseException):  # 리뷰는 병합을 막지 않는다(spec 2-1). 뜻밖의 오류도 리뷰 실패로 적는다
            res = review.record(who, f"리뷰 실패(리뷰 없음, verify만으로 병합한다): 뜻밖의 오류 {_err(res)}", rdir)
        recs[key] = res
    if errors and len(errors) == len(launch):
        raise errors[0]  # 띄운 리뷰가 모두 git 오류면 하나일 때처럼 이 티켓의 실패다(_finish·_loop가 처리)
    _set(r, t.id, review=recs["review"], second_review=recs.get("second_review", {}))
    ordered = [recs[key] for key, _, _ in slots]
    for rec in ordered:
        who = f"({rec['reviewer']})" if len(slots) > 1 else ""
        say(f"[{t.id}] 리뷰 끝{who}: {review.counts(rec)}" + (f" — {rec['note']}" if rec["note"] else ""))
    if len(slots) == 1:
        return review.fixes(ordered[0])
    return review.labeled_fixes(ordered)


def _is_agy(model: str) -> bool:
    return review.family(model) == "agy"


def _agy_limit(r: Run) -> int:
    return r.cfg.agy.max_calls_per_run


def _agy_usage(r: Run) -> str:
    return f"{r.st.agy_calls}/{_agy_limit(r)}"


def _count_agy(r: Run, model: str) -> None:
    """gs가 agy를 한 번 띄운다(worker·리뷰·수정 각각 1회). 띄우기 직전에 센다."""
    if _is_agy(model):
        r.st.agy_calls += 1
        r.save()


def _start_fix(r: Run, a: Active, todo: list[dict], runner) -> Active | None:
    """같은 구현 모델로 수정 worker를 한 번 띄운다(같은 브랜치·worktree, 지적 첨부). 띄우지 못하면 None.

    띄우지 못해도 티켓은 실패가 아니다: 지적을 고치지 못한 채 남기고 리뷰한 구현을 병합·검증한다.
    """
    t = a.t
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _note_fix(r, t, f"수정 worker {review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다. "
                        "리뷰한 구현을 병합·검증한다. fix 지적은 남는다")
        return None
    _phase(r, t.id, "fix", t.model)
    job = worker.Job(ticket=t, worktree=a.wt.resolve(), rundir=a.proc.job.rundir / "fix")
    proc = None
    try:
        job.rundir.mkdir(parents=True)
        worker.write_brief(job, r.feat.spec, r.name, a.branch)
        with job.brief.open("a", encoding="utf-8") as f:
            f.write(review.fix_brief(todo))
        adapter = adapters.for_model(t.model, r.cfg.models)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        base = git.sha(r.repo, a.branch)
        _set(r, t.id, log=str(job.log), pane="")  # 재실행 때 살아 남은 수정 worker를 run.sh로 찾게
        _count_agy(r, t.model)
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
    """수정 결과를 fix 지적을 낸 리뷰 기록마다 적는다(두 리뷰의 지적을 수정 한 번으로 고친다)."""
    ts = r.st.ticket(t.id)
    for rec in [rec for rec in state.reviews(ts) if review.fixes(rec)] or [ts.review]:
        rec["fix"] = msg
    r.save()
    say(f"[{t.id}] {msg}")


def _end_fix(r: Run, a: Active, code: int | None, commits: int, error: str) -> None:
    """수정 worker가 끝났다. 성공이면 fix 지적을 "수정 시도, 재리뷰 없음"으로 적는다.

    재리뷰가 없으니 커밋·종료 코드만으로 지적이 고쳐졌는지는 모른다(worker가 일부를 거절했을 수도 있다).
    그래서 고쳐졌다고 치지 않고 남은 지적으로 보고서에 남긴다.
    실패(종료 코드, 시간 초과, 커밋 없음, 리뷰한 커밋을 지움)면 수정 커밋을 버리고 리뷰한 구현으로 되돌린다.
    어느 쪽이든 티켓은 병합·검증으로 간다. 돌고 있던 worker는 _finish가 이미 끝냈다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    kept = git.run(r.repo, "merge-base", "--is-ancestor", a.base, branch, check=False).returncode == 0
    why = error or ("" if code == 0 else f"종료 코드 {code}") or ("" if kept else "리뷰한 커밋을 지웠다") \
        or ("" if commits else "커밋 없음")
    if not why:
        if not git.is_clean(wt):
            say(f"[{t.id}] 경고: 수정 worker가 커밋 안 된 변경을 남겼다(병합에 들어가지 않는다)")
        _mark_fixes(r, t, review.ATTEMPTED)
        recs = state.reviews(r.st.ticket(t.id))
        found = review.fixes(recs[0]) if len(recs) == 1 else review.labeled_fixes(recs)
        ids = ", ".join(str(f["id"]) for f in found)
        _note_fix(r, t, f"수정 커밋 {commits}개(재리뷰 없음, verify만 돈다). fix 지적 {ids}는 수정을 시도했지만 "
                        "고쳐졌는지 확인하지 않았다(남은 지적에 둔다)")
        return
    a.proc.finish(False)  # 들여다볼 수 있게 pane을 남긴다
    git.run(wt, "merge", "--abort", check=False)
    git.run(wt, "checkout", "-q", "-f", branch)
    git.run(wt, "reset", "-q", "--hard", a.base)
    _mark_fixes(r, t, review.DISCARDED)
    _note_fix(r, t, f"수정 worker 실패({why}): 수정을 버리고 리뷰한 구현을 병합·검증한다. fix 지적은 남는다")


def _mark_fixes(r: Run, t: Ticket, result: str) -> None:
    for rec in state.reviews(r.st.ticket(t.id)):
        for f in review.fixes(rec):
            f["fix_attempt"] = result
    r.save()


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


def _fail(r: Run, t: Ticket, reason: str, *, retry: bool = True) -> bool:
    """티켓 실패를 적는다. 첫 실패는 재시도한다. retry=False(다시 해도 같은 이유로 막힌다: agy 한도)면 바로 실패다."""
    ts = r.st.ticket(t.id)
    paths = list(ts.failed_worktrees)
    if ts.worktree and Path(ts.worktree).exists() and ts.worktree not in paths:
        paths.append(ts.worktree)
    failures = ts.failures + 1
    # 시작 준비 단계에서 실패했더라도 증거를 쓸 디렉터리는 확보한다.
    # ts.log는 RUNNING일 때만 이번 시도의 것이다. 시작 전에 실패했으면 지난 시도 증거를 덮지 않게 새 디렉터리를 쓴다
    directory = Path(ts.log).parent if ts.log and ts.status == state.RUNNING else worker.attempt_dir(r.rundir / t.id)
    directory.mkdir(parents=True, exist_ok=True)
    log = failure.record(directory, reason, [directory / "setup.log", directory / "worker.log",
                                            directory / "verify.log", directory / "merge.log"])
    retry = retry and failures < 2
    summary = str(log.with_name("failure-summary.md")) if retry else ts.failure_summary
    # 판단 모델 호출 전에 실패 횟수를 남긴다. 호출 도중 gs가 죽어도 재시도 횟수가 늘지 않는다.
    _set(r, t.id, status=state.PENDING if retry else state.FAILED, reason=reason, ended_at=state.now(),
         failures=failures, failed_worktrees=paths, failure_summary=summary)
    if retry:
        failure.summarize(r.repo, log, r.cfg)
    say(f"[{t.id}] 실패: {reason}")
    if retry:
        say(f"[{t.id}] 같은 모델({t.model})로 최신 integration에서 한 번 재시도한다")
    return False


def _verify(r: Run, t: Ticket) -> tuple[verify.Result, Path]:
    log = Path(r.st.ticket(t.id).log).parent / "verify.log"
    say(f"[{t.id}] 검증: {r.feat.spec.verify}")
    with log.open("w", encoding="utf-8") as f:
        res = verify.run(r.feat.spec, r.iwt, f)
    if res.timed_out:
        say(f"[{t.id}] 검증 시간 초과({res.minutes}분): 프로세스 그룹을 끝냈다")
    return res, log


LABEL = {"merged": "병합", "already": "이미 병합", "failed": "실패", "skipped": "건너뜀", "pending": "대기",
         "running": "실행 중"}


def _label(r: Run, tid: str) -> str:
    status = r.st.tickets[tid].status
    return "already" if status == state.MERGED and tid in r.prior else status


def _summary(r: Run, url: str | None) -> None:
    labels = {tid: _label(r, tid) for tid in r.order}
    counts = {k: sum(v == k for v in labels.values()) for k in LABEL}
    say("■ 요약: " + ", ".join(f"{LABEL[k]} {n}" for k, n in counts.items() if n))
    f = r.st.finish
    say(f"■ 마무리: {f.get('outcome', f.get('phase', '미완료'))}")
    left = _left(r)
    say(f"■ 보고서: {work_rel(r.name)}/report.md · 남은 리뷰 지적 {left}")
    say(f"■ PR: {url or '없음'}")


def _left(r: Run) -> int:
    """남은 리뷰 지적 수(두 리뷰 합)."""
    return sum(len(review.remaining(rec)) for tid in r.order for rec in state.reviews(r.st.tickets[tid]))


def _message(r: Run, url: str | None, ok: bool) -> str:
    """spec §4 "텔레그램" 형식. 성공은 세 줄, 실패는 한 줄."""
    merged = sum(r.st.tickets[tid].status == state.MERGED for tid in r.order)
    tickets = f"티켓 {merged}/{len(r.order)}"
    if ok:
        took = state.minutes(state.seconds_between(r.st.started_at, r.st.finished_at))
        left = _left(r)
        return (f"✅ {r.name} · {r.base} 병합\n{tickets} 병합 · {took}분 · 남은 지적 {left}\n"
                f"PR {url or '없음'}")
    f = r.st.finish
    outcome = f.get("outcome", f.get("phase", "미완료"))
    failed = [f"{tid} 실패: {(r.st.tickets[tid].reason.splitlines() or [''])[0]}"
              for tid in r.order if r.st.tickets[tid].status == state.FAILED]
    if failed:
        tickets += f" ({', '.join(failed)})"
    return f"❌ {r.name} · {outcome} · {tickets} · 보고서 {work_rel(r.name)}/report.md"


def _notify(r: Run, url: str | None, ok: bool) -> None:
    """실패해도 경고 한 줄만. 종료 코드·보고서는 바꾸지 않는다."""
    token = ""
    try:
        env = config.read_local_env(r.repo)
        token = env.get("TG_TOKEN", "")
        missing = [key for key in ("TG_TOKEN", "TG_CHAT_ID") if not env.get(key)]
        if missing:
            error = f"알림을 보내지 않았다: .goldstack/local.env에 {', '.join(missing)} 값이 없다"
        else:
            sent, error = notify.send(token, env["TG_CHAT_ID"], _message(r, url, ok))
            if sent:
                return
            error = f"알림 전송 실패: {error}"
    except Exception as e:  # noqa: BLE001 — local.env를 못 읽어도 실행 결과는 그대로다
        error = f"알림 실패: {notify.mask(f'{type(e).__name__}: {e}', token)}"
    print(f"경고: 텔레그램 {error}", file=sys.stderr)
