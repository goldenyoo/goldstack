"""`gs go`: 시작할 수 있는 티켓을 max_workers개까지 동시에 worker에 맡기고 integration에 모아 PR을 연다.

병렬 실행(04). 병합·검증은 한 번에 하나씩. 실패·멈춤은 같은 계열로 한 번 재시도한다(07).
worker가 성공하면 병합 전에 다른 계열이 그 티켓 diff를 리뷰하고, 고칠 지적이 있으면 같은 모델로 수정 worker를
띄운다(06, review.py). 티켓에 second_reviewer가 있으면 두 리뷰를 동시에 띄우고 지적을 합쳐 수정 worker는 하나다.
수정 worker가 커밋하면 지적을 낸 리뷰어가 수정 커밋을 다시 본다(재리뷰). 고쳐지지 않았거나 새로 고칠 것이 있으면 2차 수정
worker를 한 번 더 띄우고 다시 재리뷰한다. 수정은 티켓당 최대 2회고, 리뷰·재리뷰는 병합을 막지 않는다.
순서: 구현 → 리뷰 → 수정 → 재리뷰 → (2차 수정 → 재리뷰) → verify(마지막에 한 번) → 병합.
gs가 띄우는 agy 호출(worker·리뷰·수정·재리뷰·재시도)을 state에 세고 config `[agy] max_calls_per_run`에 닿으면 더 띄우지 않는다.
끝에는 보고서·PR·base 검증·revert를 한다(08). 지난 마무리가 남았으면 그것만 끝내고 멈춘다. 남은 티켓은 다음 gs go가 한다.
진행 상태는 `.goldstack/work/<f>/run/state.json`에 남기고(03), 다시 실행하면 병합된 티켓은 건너뛰고 나머지를 이어 간다.
같은 feature에 `gs go`는 하나만 돈다(run/lock).

worker는 config 등급표와 티켓 tier(기본 medium)로 모델·effort를 고른다. 첫 실패 뒤에는 한 단계 올리고 수정 worker도 그 등급을 쓴다.
worker가 일시 오류(transient.py의 판별)로 끝나면 실패로 세지 않고 등급도 올리지 않는다. 간격을 늘려 기다렸다가 같은 worktree·브랜치에서 새 시도
디렉터리로 다시 띄운다(Outage). 끊김이 이어지는 동안 새 worker·리뷰를 시작하지 않고 도는 worker는 그대로 둔다. 다시 띄운 worker가
5분 넘게 일시 오류 없이 돌거나 끝나면 회복이다. 대기 합계와 일정은 끊김마다 새로 센다(`Backoff`). 상한을 넘기거나 codex가 Reconnecting만 그만큼
이어 가거나 다른 호출이 NetworkAbort를 던지면 `중단(네트워크)`다: 돌던 worker를 끝내고, 마무리 없이 종료 코드 3으로 끝나고, 티켓마다 남긴
network_resume으로 다음 `gs go`가 같은 worktree에서 잇는다.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import adapters, clean, config, failure, finish, git, graph, herdr, notify, report, review, setup, state, transient, verify, worker
from .check import check
from .feature import Feature, Ticket, work_rel

CONFLICT = "conflict"
HEARTBEAT_SECONDS = 60  # 상태가 그대로여도 이 간격마다 state.json을 다시 쓴다(진행 바가 오래된 실행으로 보고 지우지 않게)
EXIT_NETWORK = 3  # `중단(네트워크)`의 종료 코드. 다음 gs go가 이어 간다
NETWORK_ABORT = "중단(네트워크)"
NETWORK_ABORT_LINE = f"■ {NETWORK_ABORT}: 다음 gs go가 이어 간다"


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
    net: Outage | None = None  # 지금의 네트워크 끊김. _loop가 새로 만든다: 대기 합계는 gs go마다 새로 센다

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
    aborted = False
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
                elif _resuming(r):
                    url, finished = _resume_finish(r)
                else:
                    _loop(r)
                    url, finished = _finish_run(r)
        except transient.NetworkAbort as e:
            # 마무리를 하지 않는다. 남은 일은 다음 gs go가 티켓마다 남긴 network_resume으로 잇는다.
            aborted, finished = True, False
            r.st.network["aborted"] = str(e)
            url = r.st.finish.get("url")
            say(f"■ 네트워크 중단 이유: {e}")
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
    if aborted:
        say(NETWORK_ABORT_LINE)
    if r.st is not None:
        _summary(r, url)
        if cfg.notify.telegram:
            _notify(r, url, ok)
    if aborted:
        return EXIT_NETWORK
    return 0 if ok else 1


def _resuming(r: Run) -> bool:
    """지난 마무리가 끝나지 않았다. 새 worker보다 그것을 먼저 끝낸다. verified·reverted여도 base 보고서를 아직 시도하지 않았으면 그렇다."""
    phase = r.st.finish.get("phase")
    return phase in finish.RESUME_PHASES or (phase in finish.BASE_REPORT_PHASES
                                             and not r.st.finish.get("base_report_tried"))


def _resume_finish(r: Run) -> tuple[str | None, bool]:
    """지난 마무리만 끝내고 이 실행은 멈춘다(_loop·두 번째 마무리 없음). 남은 티켓은 다음 gs go가 base를 합친
    integration 위에서 한다. 그래서 남은 티켓이 있으면 integration을 정리하지 않는다."""
    r.ihead = git.sha(r.iwt, "HEAD")
    left = _pending(r)
    result = _finish_run(r, cleanup=not left)
    if left and r.st.finish.get("phase") in finish.BASE_REPORT_PHASES:
        say(f"■ 남은 티켓 {left}개 → 다음 gs go")
    return result


def _pending(r: Run) -> int:
    """이번 범위에서 아직 시작하지 않은 티켓 수."""
    return sum(r.st.tickets[tid].status == state.PENDING for tid in r.order)


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
    st.network.pop("wait", None)
    st.network.pop("aborted", None)
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


def _worker_adapter(r: Run, t: Ticket) -> adapters.Adapter:
    """구현·수정·일시 오류 재시작에 같은 선택 규칙을 쓰고 실행마다 실제 옵션을 보존한다."""
    ts = r.st.ticket(t.id)
    tier, selection = r.cfg.tiers.worker(t.model, t.tier, failures=ts.failures)
    adapter = adapters.for_model(t.model, r.cfg.models, selection)
    # model은 진행·계열별 소요 통계가 쓰므로 계열로 유지한다. 빈 값은 CLI 사용자 기본값이다.
    chosen = getattr(adapter, "selection", None)
    ts.phases[-1].update(tier=tier, actual_model=chosen.model if chosen else "",
                         effort=chosen.effort if chosen else "")
    # 호출 경로의 다음 _set(pane) 또는 실패 저장이 이 선택도 함께 쓴다.
    return adapter


def _isolation_warning(r: Run, tid: str, adapter: adapters.Adapter) -> None:
    warning = adapter.isolation_warning
    warnings = r.st.ticket(tid).isolation_warnings
    if warning and warning not in warnings:
        _set(r, tid, isolation_warnings=[*warnings, warning])


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
    head = git.sha(r.iwt, "HEAD")
    branch = integration_branch(r.name)
    on_branch = git.run(r.iwt, "symbolic-ref", "-q", "HEAD", check=False).stdout.strip() == f"refs/heads/{branch}"
    if not on_branch:  # 검증 명령이 브랜치를 옮겼을 수 있다. 그대로 reset하면 엉뚱한 브랜치가 움직인다
        git.run(r.iwt, "checkout", "-q", "--force", branch, check=False)
    moved = not on_branch or head != git.sha(r.iwt, to)
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
            # 이미 진행한 병합·base 검증·revert·보고서의 재개 상태를 준비 실패로 덮지 않는다.
            if r.st.finish.get("phase") not in (*finish.RESUME_PHASES, *finish.BASE_REPORT_PHASES):
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
        if not setup.is_clean(wt):
            say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
            return False
        branch = ticket_branch(r.name, tid) + suffix
        if current[wt] != branch:
            # 분리 HEAD나 다른 브랜치의 커밋은 이 worktree만 가리킬 수 있다. 지우면 잃으니 남긴다.
            say(f"[{tid}] 경고: 남긴 worktree의 브랜치가 {branch}가 아니라 정리하지 않는다: {wt}")
            return False
        setup.discard_artifacts(wt)
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
            if not setup.is_clean(wt):
                if ts.worktree not in ts.kept_worktrees:
                    _set(r, tid, kept_worktrees=[*ts.kept_worktrees, ts.worktree])
                say(f"[{tid}] 경고: 남긴 worktree: {wt} (미커밋 변경)")
                return
        if wt and wt in current:
            # 검사 뒤 생긴 변경도 git이 지키도록 --force는 쓰지 않는다.
            setup.discard_artifacts(wt)
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
    fix: int = 0  # 리뷰 지적을 고치는 수정 worker면 그 회차(1 | 2), 구현 worker면 0. 끝나면 재리뷰로 간다
    watch: transient.ReconnectWatch | None = None  # codex worker만
    started: float = field(default_factory=time.monotonic)
    held_at: float = 0.0  # 네트워크 대기에 들어간 시각
    parked: bool = False  # 끝났지만 끊김 때문에 리뷰를 미뤘다. 돌아오면 끝 줄을 다시 찍지 않는다

    def quiet_seconds(self) -> float:
        """일시 오류 없이 돈 시간. 시작 이후 마지막 Reconnecting부터 잰다. Reconnecting 뒤 다른 이벤트가 아직 없으면 0이다."""
        if self.watch is None:
            return time.monotonic() - self.started
        try:
            self.watch.poll()  # _wait_any의 sleep 동안 쓰인 로그까지 본다
        except OSError:  # 못 읽으면 회복으로 보지 않는다. 티켓 오류로 다루는 것은 바로 뒤 _wait_any다
            return 0.0
        if self.watch.since is not None:
            return 0.0
        return time.monotonic() - max(self.started, self.watch.last or 0.0)

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


@dataclass
class Outage:
    """네트워크 끊김 하나. 끊김 = 기다리는 worker나 회복을 확인하는 worker가 있는 동안(active). 그동안 새 worker·리뷰를 시작하지 않는다."""
    backoff: transient.Backoff = field(default_factory=transient.Backoff)
    waiting: dict[str, Active] = field(default_factory=dict)  # 일시 오류로 끝나 다시 띄우기를 기다린다
    parked: dict[str, Active] = field(default_factory=dict)  # 성공으로 끝났지만 리뷰를 미뤘다. 회복하면 active로 돌아간다
    probes: set[str] = field(default_factory=set)  # 다시 띄운 worker. 이것으로 회복을 안다
    due: float | None = None  # waiting을 다시 띄울 시각(time.monotonic)
    wait_started: float = 0.0

    @property
    def active(self) -> bool:
        return bool(self.waiting or self.probes)


def _idle_seconds(r: Run) -> float:
    """시험은 이 시간만 짧게 바꿔 실제 worker의 멈춤을 확인할 수 있다."""
    return r.feat.spec.idle_minutes * 60


def _network_limit_seconds(r: Run) -> float:
    return r.cfg.timeouts.network_wait_minutes * transient.minute_seconds()


def _watch(adapter: adapters.Adapter, job: worker.Job) -> transient.ReconnectWatch | None:
    """codex는 끊겨도 죽지 않고 Reconnecting을 찍으며 기다린다. 다른 계열은 끝날 때 판별한다."""
    return transient.ReconnectWatch(job.log) if adapter.name == "codex" else None


def _loop(r: Run) -> None:
    """frontier에서 max_workers개까지 띄우고, 하나 끝날 때마다 병합·검증한 뒤 frontier를 다시 계산해 채운다.

    루프는 스레드 하나다. worker는 각자 pane·프로세스에서 돌고, 병합과 검증은 이 루프 안에서 하나씩 한다(직렬).
    네트워크 끊김 동안에는 새 worker를 띄우지 않고 끝난 worker만 처리한다. 대기는 sleep이 아니라 이 루프의 시계다(_net_tick).
    """
    cap = max(1, r.feat.spec.max_workers)
    say(f"■ 순서: {' '.join(r.order)}")
    say(f"■ 동시 worker: 최대 {cap}")
    say(f"■ 상태: {state.path(r.rundir)}")
    r.ihead = git.sha(r.iwt, "HEAD")
    r.net = Outage()
    runner = worker.make_runner(r.repo, r.name)
    active: dict[str, Active] = {}
    try:
        while True:
            _skip_blocked(r)
            _net_tick(r, active, runner)
            while not r.net.active and len(active) < cap:
                ready = [tid for tid in _frontier(r) if tid not in active]
                if not ready:
                    break
                a = _start(r, r.feat.tickets[ready[0]], runner)
                if a is None:  # 띄우지 못했다(그 티켓만 실패). 막힌 티켓을 다시 고른다
                    _skip_blocked(r)
                else:
                    active[a.t.id] = a
            if not active and not r.net.active:
                return
            ended = _wait_any(r, active, runner, once=r.net.active)
            if ended is None:  # 끊김 중에는 대기 시계와 회복을 보러 돌아온다
                continue
            tid, code, error = ended
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
                if nxt is not None:  # (2차) 수정 worker를 띄웠다. 끝나면 다시 _finish로 온다
                    active[tid] = nxt
            except (git.GitError, OSError) as e:
                # 병합·검증 실행 오류는 이 티켓의 실패로 한정한다. 리뷰·재리뷰의 뜻밖의 오류는 _review·_rereview가 막는다.
                a.proc.stop()
                _reset_integration(r, r.ihead)
                _fail(r, a.t, f"worker 결과 처리 중 오류: {_err(e)}")
                active.pop(tid)
    except transient.NetworkAbort:
        _net_abort(r, active)
        active.clear()
        raise
    finally:
        # 예상 못 한 오류로 루프를 떠나도 띄운 worker를 남기지 않는다.
        for a in active.values():
            say(f"[{a.t.id}] gs가 멈춰 worker를 끝낸다")
            a.proc.stop()


def _mark_resume(r: Run, a: Active, *, done: bool = False) -> None:
    """이 worker를 다음에 같은 worktree에서 잇도록 state에 남긴다. done이면 worker는 끝났고 리뷰부터 하면 된다."""
    r.st.ticket(a.t.id).network_resume = {
        "branch": a.branch, "worktree": str(a.wt.resolve()), "base": a.base, "fix": a.fix, "done": done,
        "rundir": str(a.proc.job.rundir)}
    r.save()


def _net_publish(r: Run) -> None:
    """지금의 대기를 state에 쓴다(진행 바·gs status가 읽는다)."""
    n = r.net
    wait = {}
    if n.active:
        due_at = state.after(n.due - time.monotonic()) if n.due is not None else ""
        wait = {"count": n.backoff.count, "due_at": due_at}
    r.st.network["wait"] = wait
    r.save()


def _net_add_waited(r: Run, seconds: float) -> None:
    r.st.network["waited_seconds"] = round(r.st.network.get("waited_seconds", 0) + seconds, 1)


def _net_hold(r: Run, a: Active, why: str) -> None:
    """worker가 일시 오류로 끝났다. 실패로 세지 않고 다시 띄울 때까지 세워 둔다. 상한을 다 썼으면 NetworkAbort."""
    n, tid = r.net, a.t.id
    ts = r.st.ticket(tid)
    a.proc.finish(True)  # 다음 시도는 새 pane이다. 증거는 시도 디렉터리에 남는다
    n.probes.discard(tid)
    n.waiting[tid] = a
    a.held_at = time.monotonic()
    ts.transient_errors += 1
    r.st.network["errors"] = r.st.network.get("errors", 0) + 1
    ts.reason = f"네트워크 대기: {why}"
    state.begin_phase(ts, "network", "")
    _mark_resume(r, a)
    if n.due is None:  # 다른 worker가 이미 잡아 둔 대기가 있으면 거기에 함께 탄다
        delay = n.backoff.next(r.cfg.timeouts.network_wait_minutes)
        if delay is None:
            raise transient.NetworkAbort(
                f"대기 합계가 상한 {r.cfg.timeouts.network_wait_minutes}분을 넘었다(timeouts.network_wait_minutes)")
        n.due, n.wait_started = time.monotonic() + delay, time.monotonic()
    _net_publish(r)
    say(f"[{tid}] 일시 오류({why}): 실패로 세지 않는다. {state.network_label(r.st, state.now())}")


def _net_park(r: Run, a: Active) -> bool:
    """끊김 중에 끝난 성공 worker의 리뷰를 회복 뒤로 미룬다. 미뤘으면 True."""
    if not r.net.active:
        return False
    r.net.parked[a.t.id] = a
    a.parked = True
    state.begin_phase(r.st.ticket(a.t.id), "network", "")
    _mark_resume(r, a, done=True)
    say(f"[{a.t.id}] 네트워크 대기 중이라 리뷰를 회복 뒤로 미룬다")
    return True


def _net_tick(r: Run, active: dict[str, Active], runner) -> None:
    """끊김의 시계: 회복을 판단하고, 때가 된 worker를 다시 띄우고, 끊김이 끝나면 미룬 리뷰를 돌려놓는다."""
    n = r.net
    if not n.active and not n.parked:
        return
    now = time.monotonic()
    changed = False
    # 다시 띄운 worker가 일시 오류로 끝나면 _net_hold가 probes에서 뺀다. 그 밖의 이유로 없어졌으면 끝난 것이다.
    healed = bool(n.probes - active.keys()) or any(
        active[tid].quiet_seconds() >= transient.RECOVERY_MINUTES * transient.minute_seconds()
        for tid in n.probes & active.keys())
    if healed:
        n.probes.clear()
        if n.waiting:  # 회복했으니 함께 기다리던 worker도 지금 다시 띄운다
            n.due = now
        changed = True
    if n.waiting and n.due is not None and now >= n.due:
        _net_add_waited(r, now - n.wait_started)
        for tid in [tid for tid in r.order if tid in n.waiting]:
            a = n.waiting.pop(tid)
            ts = r.st.ticket(tid)
            ts.network_wait_seconds = round(ts.network_wait_seconds + now - a.held_at, 1)
            nxt = _resume(r, a.t, runner, ts.network_resume)
            if nxt is not None:
                active[tid] = nxt
                if not healed:
                    n.probes.add(tid)
        n.due = None
        changed = True
    if not n.active:
        if n.backoff.count:
            say("■ 네트워크 회복: 다른 티켓 시작을 재개한다")
        n.backoff = transient.Backoff()
        active.update(n.parked)
        n.parked.clear()
        changed = True
    if changed:
        _net_publish(r)


def _net_abort(r: Run, active: dict[str, Active]) -> None:
    """`중단(네트워크)`: 돌던 worker를 끝내고, 티켓은 실패로 세지 않고, 다음 gs go가 이어 갈 표시를 남긴다."""
    n = r.net
    now = time.monotonic()
    if n.waiting and n.due is not None:
        _net_add_waited(r, now - n.wait_started)
    for tid, a in {**active, **n.waiting, **n.parked}.items():
        ts = r.st.ticket(tid)
        if not ts.network_resume:
            _mark_resume(r, a)
        if tid in n.waiting:
            ts.network_wait_seconds = round(ts.network_wait_seconds + now - a.held_at, 1)
        elif tid in active and not isinstance(a.proc, worker.Finished):
            say(f"[{tid}] {NETWORK_ABORT}: worker를 끝낸다")
        a.proc.stop()
        _set(r, tid, status=state.PENDING, pane="", reason=NETWORK_ABORT, ended_at=state.now())
    n.waiting.clear()
    n.parked.clear()
    n.probes.clear()
    n.due = None
    r.st.network["wait"] = {}
    r.save()


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


def _wait_any(r: Run, active: dict[str, Active], runner, *, once: bool = False) -> tuple[str, int | None, str] | None:
    """돌고 있는 worker 중 하나가 끝날 때까지 기다린다. 동시에 끝났으면 r.order 앞쪽부터.

    (티켓, 종료 코드, 오류). 확인 중 오류(실행기·어댑터 판정의 예외)는 그 티켓의 오류로 돌려준다.
    once면 한 번만 보고 끝난 worker가 없으면 None이다(끊김 중: 루프가 대기 시계를 본다).
    codex worker가 Reconnecting만 상한 넘게 이어 가면 NetworkAbort를 올린다.
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
                    watch = active[tid].watch
                    if code is None and watch and watch.stalled_for() > _network_limit_seconds(r):
                        raise transient.NetworkAbort(
                            f"[{tid}] codex가 Reconnecting만 {r.cfg.timeouts.network_wait_minutes}분 넘게 이어 갔다")
                except transient.NetworkAbort:
                    raise
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
        if once:
            return None


def _failure_summary(r: Run, ts: state.TicketState) -> str:
    """지난 실패의 요약(재시도 brief에 붙인다). 없으면 빈 문자열."""
    if not ts.failure_summary:
        return ""
    path = Path(ts.failure_summary)
    if not path.exists():  # 요약 호출 중 코디네이터가 죽었으면 새 호출로 마무리한다
        failure.summarize(r.repo, path.with_name("failure.log"), r.cfg, _call_wait(r, ""))
    return path.read_text(encoding="utf-8")


def _resumable(r: Run, mark: dict) -> bool:
    """network_resume이 가리키는 worktree가 그 브랜치로 그대로 있나."""
    try:
        return git.worktrees(r.repo).get(Path(mark["worktree"]).resolve()) == mark["branch"]
    except (git.GitError, OSError, KeyError):
        return False


def _resume(r: Run, t: Ticket, runner, mark: dict) -> Active | None:
    """끊긴 worker를 mark의 worktree·브랜치에서 잇는다. failures를 올리지 않는다.

    worker가 끝나 있으면(done) 프로세스 없이 리뷰부터 잇는다. 새 시도 디렉터리를 쓰므로 지난 로그는 남고 base는 처음 그대로라
    앞 시도의 커밋도 이 worker의 커밋으로 센다. 띄우지 못하면 구현은 티켓 실패, 수정은 실패한 수정으로 처리한다(수정 전 구현을 병합·검증한다).
    """
    ts = r.st.ticket(t.id)
    wt, branch, base, nth = Path(mark["worktree"]), mark["branch"], mark["base"], mark.get("fix", 0)
    last = Path(mark["rundir"])

    def stand_in(code: int, note: str = "") -> Active:
        _set(r, t.id, status=state.RUNNING, branch=branch, worktree=str(wt), pane="", reason="", ended_at="",
             started_at=state.now(), log=str(last / "worker.log"))
        return Active(t, worker.Finished(worker.Job(t, wt, last), code, note), branch, wt, base, fix=nth)

    def give_up(why: str, *, retry: bool = True) -> Active | None:
        if nth:
            say(f"[{t.id}] {_ordinal(nth)}수정 worker를 다시 띄우지 못했다: {why}")
            return stand_in(1, why)
        _fail(r, t, why, retry=retry)
        return None

    if mark.get("done"):
        say(f"[{t.id}] 지난 worker는 끝났다. 같은 worktree에서 리뷰부터 잇는다({wt})")
        return stand_in(0)
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        return give_up(f"agy 한도: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿아 worker를 다시 띄우지 않았다"
                       "(config agy.max_calls_per_run)", retry=False)
    proc = None
    try:
        if nth:
            step = "fix" if nth == 1 else f"fix{nth}"
            k = 1
            while (last.parent / f"{step}-net{k}").exists():
                k += 1
            rundir, phase, attempt = last.parent / f"{step}-net{k}", step, None
        else:
            rundir = worker.attempt_dir((r.rundir / t.id).resolve())
            phase, attempt = "worker", int(rundir.name)
        rundir.mkdir(parents=True)
        job = worker.Job(ticket=t, worktree=wt, rundir=rundir)
        state.begin_phase(ts, phase, t.model, attempt=attempt)
        _set(r, t.id, status=state.RUNNING, attempts=ts.attempts + (0 if nth else 1), branch=branch, pane="",
             worktree=str(wt), log=str(job.log), started_at=state.now(), ended_at="", reason="")
        worker.write_brief(job, r.feat.spec, r.name, branch, "" if nth else _failure_summary(r, ts), resumed=True)
        if nth:
            with job.brief.open("a", encoding="utf-8") as f:
                f.write(review.fix_brief(_todo(r, t, nth), nth))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)
        _count_agy(r, t.model)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:{rundir.name}", adapter)
        _set(r, t.id, pane=proc.where)
    except adapters.AdapterError as e:
        return give_up(str(e))
    except Exception as e:  # noqa: BLE001 — 한 티켓의 오류로 코디네이터가 멈추지 않게
        if proc is not None:
            proc.stop()
        return give_up(f"worker를 다시 띄우지 못했다: {_err(e)}")
    say(f"[{t.id}] 네트워크 끊김 뒤 같은 worktree에서 다시 시작 ({adapter.name}, {proc.where}, 로그 {job.log})")
    a = Active(t, proc, branch, wt, base, fix=nth, watch=_watch(adapter, job))
    _mark_resume(r, a)  # 이 worker도 끊기거나 gs가 죽으면 여기서 잇는다
    return a


def _start(r: Run, t: Ticket, runner) -> Active | None:
    """최신 integration 끝에서 티켓 브랜치를 새로 만들고 worker를 띄운다. 띄우지 못하면 실패로 적고 None.

    네트워크로 끊겼던 티켓(network_resume)은 같은 worktree에서 잇는다.
    어떤 오류든(git, herdr, 파일, 어댑터 준비) 이 티켓만 실패시킨다. 이미 띄운 worker가 있으면 끝낸다.
    """
    mark = r.st.ticket(t.id).network_resume
    if mark:
        if _resumable(r, mark):
            return _resume(r, t, runner, mark)
        say(f"[{t.id}] 경고: 이어 갈 worktree가 없거나 브랜치가 달라 새로 시작한다: {mark.get('worktree')}")
        _set(r, t.id, network_resume={})
    proc = None
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _fail(r, t, f"agy 한도: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿아 worker를 띄우지 않았다"
                    "(config agy.max_calls_per_run)", retry=False)
        return None
    try:
        _recheck_kept(r, t.id)
        ts = r.st.ticket(t.id)
        summary = _failure_summary(r, ts)
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
            setup.remember(wt)
            _phase(r, t.id, "worker", t.model)
        worker.write_brief(job, r.feat.spec, r.name, branch, summary)
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)  # agy: 차단 장치가 걸리지 않으면 여기서 거부한다
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)  # 종료·시간 초과·재개 여부와 무관하게 실행 전에 보존한다
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
    return Active(t, proc, branch, wt, base, watch=_watch(adapter, job))


def _finish(r: Run, a: Active, code: int | None, others: list[str] = (), runner=None,
            error: str = "") -> Active | None:
    """끝난 worker 하나를 확인하고, 리뷰한 뒤, 최신 integration을 티켓 브랜치에 합쳐 보고 integration에 병합·검증한다.

    others는 아직 돌고 있는 다른 worker다. integration이 바뀌었을 때 누구 짓인지 가리는 데 쓴다.
    고칠 리뷰 지적이 있으면 수정 worker를 띄워 그 Active를 돌려준다(아니면 None). 수정 worker가 끝나면(a.fix) 재리뷰하고,
    1차 수정 뒤에 또 고칠 것이 있으면 2차 수정 worker를 띄운다. 그 밖에는 병합·검증으로 간다.
    error는 수정 worker를 확인하다 난 오류(시간 초과 등)다.
    일시 오류로 끝났으면 실패로 세지 않고 세워 둔다(None, _net_tick이 다시 띄운다). 네트워크 끊김 중이면 리뷰·재리뷰를 미룬다.
    """
    t, wt, branch = a.t, a.wt, a.branch
    commits = git.count(r.repo, f"{a.base}..{branch}")
    note = a.proc.note
    who = "수정 worker" if a.fix else "worker"
    if not a.parked:
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
    why = _transient_end(a, code, commits, error)
    if why:
        _net_hold(r, a, why)
        return None
    if r.st.ticket(t.id).network_resume:  # 이 worker는 끊기지 않고 끝났다
        _set(r, t.id, network_resume={})
    if a.fix:
        if not error and code == 0 and commits and _net_park(r, a):  # 성공한 수정 worker는 재리뷰로 간다
            return None
        try:
            todo = _end_fix(r, a, code, commits, error)
        except transient.NetworkAbort:
            _mark_resume(r, a, done=True)
            raise
        if todo:
            a.proc.finish(True)  # 1차 수정 worker는 성공했다
            nxt = _start_fix(r, a, todo, runner, a.fix + 1)
            if nxt is not None:
                return nxt
    else:
        if code != 0:
            why = f"worker 종료 코드 {code}" if code >= 0 else "worker 실행기가 사라졌다"
            return fail(why + (f" ({note})" if note else ""))
        if commits == 0:
            return fail("커밋 없음")
        if not setup.is_clean(wt):
            say(f"[{t.id}] 경고: worktree에 커밋 안 된 변경이 남았다(병합에 들어가지 않는다)")
        if _net_park(r, a):
            return None
        try:
            todo = _review(r, a)
        except review.Refused as e:
            return fail(str(e))
        except transient.NetworkAbort:
            _mark_resume(r, a, done=True)
            raise
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
    res, log, changed = _verify(r, t)
    if not res.ok:
        _reset_integration(r, r.ihead)
        return fail(f"검증 시간 초과({res.minutes}분, 로그 {log})" if res.timed_out else f"검증 실패(로그 {log})")
    # 검증하는 동안 다른 worker가 integration(index, HEAD, 병합 상태)을 바꿨으면 검증한 것과 커밋할 것이 다르다
    expected = (r.ihead, f"refs/heads/{integration_branch(r.name)}")
    if _merge_state(r) != merged or merged[:2] != expected or not all(merged):
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 검증한 것과 커밋할 것이 다르다")
    if changed:  # 검증이 파일을 남겼다. 그 파일은 병합에 들어가지 않으니 통과를 믿을 수 없다
        _reset_integration(r, r.ihead)
        return fail(f"검증 중 worktree가 바뀌었다(로그 {log})")
    # 커밋은 검증한 트리로 직접 만들고, 브랜치는 r.ihead에 있을 때만 옮긴다(그 사이 바뀌어도 섞이지 않게)
    _phase(r, t.id, "finish", t.model)
    msg = f"Merge {t.id}: {t.title}\n\n{trailer(r.name, t.id)}\n"
    new = git.out(r.iwt, "commit-tree", merged[3], "-p", r.ihead, "-p", merged[2], "-m", msg)
    moved = git.run(r.iwt, "update-ref", "-m", f"gs: merge {t.id}", merged[1], new, r.ihead, check=False)
    if moved.returncode:
        _reset_integration(r, r.ihead)
        return fail("검증하는 동안 integration이 바뀌었다(되돌림): 브랜치가 움직였다")
    git.run(r.iwt, "reset", "-q", "--hard", new)  # 병합 상태를 끝내고 worktree를 새 커밋에 맞춘다
    setup.clean(r.iwt, "-q", "-fd")
    r.ihead = new
    a.proc.finish(True)
    _set(r, t.id, status=state.MERGED, ended_at=state.now(), reason="", network_resume={})
    say(f"[{t.id}] 검증 통과 → integration 병합")
    _cleanup_merged(r, t.id)
    return None


def _transient_end(a: Active, code: int | None, commits: int, error: str) -> str:
    """worker가 일시 오류로 끝났으면 그 이유, 아니면 빈 문자열. 판별 자체의 오류는 일시 오류가 아니라고 본다.

    종료 0이고 커밋이 있으면 성공이다. 시간 초과·확인 오류는 일시 오류가 아니다(지금처럼 실패).
    """
    if error or code is None or (code == 0 and commits):
        return ""
    try:
        return a.proc.transient_reason()
    except Exception as e:  # noqa: BLE001 — 판별은 덤이다. 평소의 실패 처리로 간다
        say(f"[{a.t.id}] 경고: 일시 오류 판별 실패: {_err(e)}")
        return ""


def _review(r: Run, a: Active) -> list[dict]:
    """다른 계열이 이 티켓 diff(최신 integration과의 merge-base 기준)를 리뷰한다. 고칠 지적을 돌려준다.

    병합·검증처럼 루프 안에서 하나씩 돈다(다른 worker는 그동안 각자 돈다). 오래 걸리는 수정은 worker로 따로 띄운다.
    second_reviewer가 있으면 두 리뷰를 동시에 띄우고, 둘 다 끝나면 fix 지적을 합쳐 돌려준다(수정 worker는 하나).
    그때는 한쪽이 거부·실패여도 다른 쪽으로 간다. 둘 다 거부면 하나일 때처럼 티켓 실패다.
    일시 오류·시간 초과는 실패가 아니다: review가 이 스레드(둘이면 그 스레드들)에서 기다렸다 다시 부른다.
    agy 리뷰는 이번 실행의 상한에 닿았으면 띄우지 않고 "건너뜀(한도)"으로 적는다.
    중단 예외(NetworkAbort)는 리뷰 실패로 적지 않고 올린다: 끊겼다는 이유로 리뷰 없이 병합하지 않는다.
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
    wait = _call_wait(r, t.id)
    jobs = [dict(repo=r.repo, worktree=a.wt.resolve(), rdir=rdir, base=r.ihead, branch=a.branch,
                 ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(), model=t.model, reviewer=who, cfg=r.cfg,
                 on_wait=wait)
            for _, who, rdir in launch]
    if len(jobs) == 1:  # 하나면 이 스레드에서 부른다(second_reviewer가 없는 티켓의 흐름 그대로)
        try:
            results: list = [review.run(**jobs[0])]
        except (review.Refused, git.GitError, transient.NetworkAbort):
            raise
        except Exception as e:  # noqa: BLE001 — 아래에서 리뷰 실패로 적는다
            results = [e]
    else:
        results = review.run_together(jobs)
    _raise_network_abort(results)
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
    return _todo(r, t, 1)


def _call_wait(r: Run, tid: str) -> review.CallWait:
    """리뷰·판단 호출의 대기를 진행 바에 보인다. 이 스레드가 그 호출을 기다리는 동안 다른 worker는 각자 돈다."""
    return review.CallWait(r.st, r.save, tid, say)


def _raise_network_abort(results: list) -> None:
    """함께 돌린 호출의 결과 중 중단 예외가 있으면 올린다. 다른 쪽 결과는 다음 gs go가 다시 받는다."""
    for res in results:
        if isinstance(res, transient.NetworkAbort):
            raise res


def _is_agy(model: str) -> bool:
    return review.family(model) == "agy"


def _agy_limit(r: Run) -> int:
    return r.cfg.agy.max_calls_per_run


def _agy_usage(r: Run) -> str:
    return f"{r.st.agy_calls}/{_agy_limit(r)}"


def _count_agy(r: Run, model: str) -> None:
    """gs가 agy를 한 번 띄운다(worker·리뷰·수정·재리뷰 각각 1회). 띄우기 직전에 센다."""
    if _is_agy(model):
        r.st.agy_calls += 1
        r.save()


def _todo(r: Run, t: Ticket, nth: int) -> list[dict]:
    """nth번째 수정 worker가 고칠 지적. 리뷰가 둘이면 지적 번호에 계열 이름을 붙인다(수정 brief에 쓴다)."""
    recs = state.reviews(r.st.ticket(t.id))
    return review.fix_targets(recs[0], nth) if len(recs) == 1 else review.labeled_fixes(recs, nth)


def _targets(r: Run, t: Ticket, nth: int) -> list[tuple[dict, list[dict]]]:
    """(리뷰 기록, 그 기록 안의 nth번째 수정 대상 지적). 대상이 없는 리뷰는 뺀다."""
    pairs = [(rec, review.fix_targets(rec, nth)) for rec in state.reviews(r.st.ticket(t.id))]
    return [(rec, found) for rec, found in pairs if found]


def _attempt_dir(a: Active) -> Path:
    """이 티켓 시도의 실행 디렉터리. 수정 worker는 그 아래 fix·fix2에서 돈다."""
    return a.proc.job.rundir.parent if a.fix else a.proc.job.rundir


def _start_fix(r: Run, a: Active, todo: list[dict], runner, nth: int = 1) -> Active | None:
    """같은 구현 모델로 nth번째 수정 worker를 띄운다(같은 브랜치·worktree, 지적 첨부). 띄우지 못하면 None.

    띄우지 못해도 티켓은 실패가 아니다: 지적을 고치지 못한 채 남기고 지금 브랜치의 구현을 병합·검증한다.
    """
    t = a.t
    if _is_agy(t.model) and state.agy_reached(r.st, _agy_limit(r)):
        _skip_fix(r, t, nth, review.REASON_LIMIT,
                  f"{_ordinal(nth)}수정 worker {review.LIMIT}: 이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다. "
                  "지금 브랜치의 구현을 병합·검증한다. 고칠 지적은 남는다")
        return None
    step = "fix" if nth == 1 else f"fix{nth}"
    _phase(r, t.id, step, t.model)
    job = worker.Job(ticket=t, worktree=a.wt.resolve(), rundir=_attempt_dir(a) / step)
    proc = None
    try:
        job.rundir.mkdir(parents=True)
        worker.write_brief(job, r.feat.spec, r.name, a.branch)
        with job.brief.open("a", encoding="utf-8") as f:
            f.write(review.fix_brief(todo, nth))
        adapter = _worker_adapter(r, t)
        adapter.prepare(job.input)
        worker.write_script(job, adapter)
        _isolation_warning(r, t.id, adapter)
        base = git.sha(r.repo, a.branch)
        _set(r, t.id, log=str(job.log), pane="")  # 재실행 때 살아 남은 수정 worker를 run.sh로 찾게
        _count_agy(r, t.model)
        proc = worker.Proc(job, runner, f"gs:{r.name}:{t.id}:{step}", adapter)
        _set(r, t.id, pane=proc.where)
    except Exception as e:  # noqa: BLE001 — 수정은 덤이다. 지금 브랜치의 구현은 그대로 병합한다
        if proc is not None:
            proc.stop()
        _skip_fix(r, t, nth, f"띄우지 못함: {_err(e)}", f"{_ordinal(nth)}수정 worker를 띄우지 못했다: {_err(e)}")
        return None
    say(f"[{t.id}] {_ordinal(nth)}수정 worker 시작: 지적 {len(todo)}개 ({adapter.name}, {proc.where}, 로그 {job.log})")
    return Active(t, proc, a.branch, a.wt, base, fix=nth, watch=_watch(adapter, job))


def _ordinal(nth: int) -> str:
    return "" if nth == 1 else f"{nth}차 "


def _skip_fix(r: Run, t: Ticket, nth: int, reason: str, msg: str) -> None:
    """수정 worker를 띄우지 못했다. 대상 지적에 이유를 남긴다. 1차 재리뷰의 unresolved는 그대로 미해결로 읽힌다."""
    for _, found in _targets(r, t, nth):
        for f in found:
            f["fix_reason"] = reason
    _note_fix(r, t, nth, msg)


def _note_fix(r: Run, t: Ticket, nth: int, msg: str) -> None:
    """수정 결과를 그 수정의 지적을 낸 리뷰 기록마다 덧붙인다(두 리뷰의 지적을 수정 worker 하나로 고친다)."""
    ts = r.st.ticket(t.id)
    for rec in [rec for rec, _ in _targets(r, t, nth)] or [ts.review]:
        _append_fix(rec, msg)
    r.save()
    say(f"[{t.id}] {msg}")


def _append_fix(rec: dict, msg: str) -> None:
    if msg in rec.get("fix", ""):  # 중단 뒤 재리뷰부터 이을 때 같은 줄을 또 적지 않는다
        return
    rec["fix"] = f"{rec['fix']} / {msg}" if rec.get("fix") else msg


def _end_fix(r: Run, a: Active, code: int | None, commits: int, error: str) -> list[dict]:
    """수정 worker가 끝났다. 성공이면 재리뷰로 가고, 2차 수정이 고칠 지적을 돌려준다(없으면 빈 목록).

    실패(종료 코드, 시간 초과, 커밋 없음, 이전 커밋을 지움)면 이번 수정 커밋만 버리고 수정 전 head로 되돌린다
    (2차 수정 실패면 1차 수정 결과는 남는다). 재리뷰는 하지 않는다. 어느 쪽이든 티켓은 병합·검증으로 간다.
    되돌리기 자체가 git 오류면 어느 트리를 병합할지 모르니 그 오류는 올린다(_loop가 티켓 실패로 처리해 다시 한다).
    돌고 있던 worker는 _finish가 이미 끝냈다.
    """
    t, wt, branch, nth = a.t, a.wt, a.branch, a.fix
    kept = git.run(r.repo, "merge-base", "--is-ancestor", a.base, branch, check=False).returncode == 0
    why = error or ("" if code == 0 else f"종료 코드 {code}") or ("" if kept else "이전 커밋을 지웠다") \
        or ("" if commits else "커밋 없음")
    if not why:
        if not setup.is_clean(wt):
            say(f"[{t.id}] 경고: 수정 worker가 커밋 안 된 변경을 남겼다(병합에 들어가지 않는다)")
        _mark_fixes(r, t, nth, review.ATTEMPTED)
        ids = ", ".join(str(f["id"]) for f in _todo(r, t, nth))
        _note_fix(r, t, nth, f"{_ordinal(nth)}수정 커밋 {commits}개(fix 지적 {ids}): 재리뷰로 확인한다")
        return _rereview(r, a)
    a.proc.finish(False)  # 들여다볼 수 있게 pane을 남긴다
    git.run(wt, "merge", "--abort", check=False)
    git.run(wt, "checkout", "-q", "-f", branch)
    git.run(wt, "reset", "-q", "--hard", a.base)
    _mark_fixes(r, t, nth, review.DISCARDED, f"수정 worker 실패: {why}")
    _note_fix(r, t, nth, f"{_ordinal(nth)}수정 worker 실패({why}): 이 수정을 버리고 수정 전 구현을 병합·검증한다. 고칠 지적은 남는다")
    return []


def _mark_fixes(r: Run, t: Ticket, nth: int, result: str, reason: str = "") -> None:
    for _, found in _targets(r, t, nth):
        for f in found:
            f["fix_attempt"], f["fix_round"] = result, nth
            if reason:
                f["fix_reason"] = reason
    r.save()


def _rereview(r: Run, a: Active) -> list[dict]:
    """지적을 낸 리뷰어들에게 수정 커밋을 다시 보게 하고, 결과를 지적에 적는다. 2차 수정이 고칠 지적을 돌려준다.

    병합·검증처럼 루프 안에서 돈다. 여기서 난 오류는 병합을 막지 않는다: 아직 결과가 없는 지적은 unchecked(재리뷰 실패)다.
    중단 예외(NetworkAbort)만 올린다. 다음 gs go가 재리뷰부터 잇는다.
    """
    t, nth = a.t, a.fix
    targets = _targets(r, t, nth)
    try:
        head = git.sha(r.repo, a.branch)
        if git.out(r.repo, "diff", "--no-ext-diff", "--name-only", f"{a.base}..{head}"):
            with _rereview_tree(r, a, head) as tree:
                _run_rereviews(r, a, targets, head, tree)
        else:  # 부를 것도 없다: 바뀐 것이 없으니 고쳐졌을 수 없다
            for rec, found in targets:
                review.mark_rereview(found, nth, review.UNRESOLVED, "", "수정 커밋의 diff가 비었다")
                _append_fix(rec, f"재리뷰 {nth}차: 수정 커밋의 diff가 비어 부르지 않았다(unresolved)")
    except transient.NetworkAbort:
        raise
    except Exception as e:  # noqa: BLE001 — verify가 병합 관문이다
        say(f"[{t.id}] 재리뷰 {nth}차 실패: {_err(e)}")
        for _, found in targets:
            review.mark_rereview([f for f in found if f.get("rereview_round") != nth], nth, review.UNCHECKED,
                                 review.REASON_FAILED, f"뜻밖의 오류 {_err(e)}")
    r.save()
    return _todo(r, t, nth + 1) if nth == 1 else []  # 수정은 티켓당 최대 2회다


@contextmanager
def _rereview_tree(r: Run, a: Active, head: str) -> Iterator[Path]:
    """재리뷰가 읽을 트리. 병합되는 것은 커밋(head)뿐이니 리뷰어도 그것만 보게 한다.

    티켓 worktree가 head 그대로면 그곳을 쓴다(setup 산출물이 있다). 미커밋 변경이 남았거나 다른 곳으로 옮겨 갔으면
    head의 임시 worktree를 쓴다: 병합되지 않을 수정을 resolved로 확인하지 않게. 티켓 worktree의 변경은 지우지 않는다.
    임시 worktree를 못 만든 오류는 _rereview가 unchecked(재리뷰 실패)로 적는다. 치우기 실패는 경고뿐이다.
    """
    if git.sha(a.wt, "HEAD") == head and setup.is_clean(a.wt):
        yield a.wt.resolve()
        return
    say(f"[{a.t.id}] 티켓 worktree가 수정 커밋과 달라 재리뷰는 커밋된 트리({head[:8]})에서 한다")
    with tempfile.TemporaryDirectory(prefix="gs-rereview-", dir=r.rundir, ignore_cleanup_errors=True) as tmp:
        tree = Path(tmp).resolve() / "wt"
        git.run(r.repo, "worktree", "add", "--detach", str(tree), head)
        try:
            yield tree
        finally:
            try:
                git.remove_worktree(r.repo, tree)
            except git.GitError as e:
                say(f"[{a.t.id}] 경고: 재리뷰 임시 worktree를 치우지 못했다: {_err(e)}")


def _run_rereviews(r: Run, a: Active, targets: list[tuple[dict, list[dict]]], head: str, tree: Path) -> None:
    """리뷰어마다 재리뷰를 띄운다. 둘 다 냈으면 run_together로 동시에. agy는 상한에 닿았으면 띄우지 않고 unchecked(한도)다."""
    t, nth = a.t, a.fix
    launch = []
    for rec, found in targets:
        who = rec["reviewer"]
        if _is_agy(who) and state.agy_reached(r.st, _agy_limit(r)):
            detail = f"이번 실행의 agy 호출이 상한 {_agy_usage(r)}에 닿았다"
            review.mark_rereview(found, nth, review.UNCHECKED, review.REASON_LIMIT, detail)
            _append_fix(rec, f"재리뷰 {nth}차 {review.LIMIT}: {detail}")
            say(f"[{t.id}] 재리뷰 {nth}차({who}) {review.LIMIT}: {detail}")
            continue
        _count_agy(r, who)
        launch.append((rec, found))
    if not launch:
        return
    names = "+".join(rec["reviewer"] for rec, _ in launch)
    _phase(r, t.id, "rereview", names)
    say(f"[{t.id}] 재리뷰 {nth}차: {names}")
    wait = _call_wait(r, t.id)
    jobs = [dict(repo=r.repo, worktree=tree, rdir=_attempt_dir(a) / f"rereview{nth}-{rec['reviewer']}",
                 base=a.base, head=head, found=found, ticket=t.path.resolve(), spec=r.feat.spec.path.resolve(),
                 reviewer=rec["reviewer"], cfg=r.cfg, nth=nth, on_wait=wait) for rec, found in launch]
    results = review.run_together(jobs, review.rereview)
    _raise_network_abort(results)
    for (rec, found), res in zip(launch, results):
        if isinstance(res, BaseException):
            res = {"dir": "", "base": a.base, "head": head, "note": f"뜻밖의 오류 {_err(res)}",
                   "failed": review.REASON_FAILED, "verdicts": {}, "findings": []}
        review.apply_rereview(rec, found, res, nth)
        msg = f"재리뷰 {nth}차: {review.rereview_counts(found, len(res['findings']))}" \
            + (f" — {res['note']}" if res["note"] else "")
        _append_fix(rec, msg)
        say(f"[{t.id}] {msg} ({rec['reviewer']})")


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
         failures=failures, failed_worktrees=paths, failure_summary=summary, network_resume={})
    if retry:
        failure.summarize(r.repo, log, r.cfg, _call_wait(r, t.id))
    say(f"[{t.id}] 실패: {reason}")
    if retry:
        say(f"[{t.id}] 같은 계열({t.model})로 최신 integration에서 한 번 재시도한다")
    return False


def _verify(r: Run, t: Ticket) -> tuple[verify.Result, Path, bool]:
    """티켓 검증은 명령과 상관없이 커밋될 트리, 곧 integration의 미완 병합에서 돈다(티켓 worktree의 커밋 안 된 파일은 못 본다).

    (결과, 로그, 트리가 바뀌었나). 트리를 보는 규칙은 `finish._verify`와 같다. 다만 미완 병합이라 index의 변경은
    더러운 것이 아니고, index가 그대로인지는 `_merge_state`로 본다."""
    log = Path(r.st.ticket(t.id).log).parent / "verify.log"
    spec = r.feat.spec
    command = spec.verify_for(t)
    before = _merge_state(r)
    say(f"[{t.id}] 검증: {command}")
    with log.open("w", encoding="utf-8") as f:
        f.write(f"$ {command}\ncwd: {r.iwt}\n")
        res = verify.run(replace(spec, verify=command), r.iwt, f)
        changed = not res.timed_out and (_merge_state(r) != before or not setup.is_clean(r.iwt, staged_ok=True))
        if changed:
            f.write("\n검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
        elif res.ok:
            verify.flaky(res, f"ticket-{t.id}", f)
    if res.timed_out:
        say(f"[{t.id}] 검증 시간 초과({res.minutes}분): 프로세스 그룹을 끝냈다")
    return res, log, changed


LABEL = {"merged": "병합", "already": "이미 병합", "failed": "실패", "skipped": "건너뜀", "pending": "대기",
         "running": "실행 중"}


def _label(r: Run, tid: str) -> str:
    status = r.st.tickets[tid].status
    return "already" if status == state.MERGED and tid in r.prior else status


def _summary(r: Run, url: str | None) -> None:
    labels = {tid: _label(r, tid) for tid in r.order}
    counts = {k: sum(v == k for v in labels.values()) for k in LABEL}
    say("■ 요약: " + ", ".join(f"{LABEL[k]} {n}" for k, n in counts.items() if n))
    say(f"■ 마무리: {_outcome(r)}")
    left = _left(r)
    say(f"■ 보고서: {work_rel(r.name)}/report.md · 남은 리뷰 지적 {left}")
    say(f"■ PR: {url or '없음'}")


def _outcome(r: Run) -> str:
    if r.st.network.get("aborted"):
        return NETWORK_ABORT
    f = r.st.finish
    return f.get("outcome", f.get("phase", "미완료"))


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
    outcome = _outcome(r)
    failed = [f"{tid} 실패: {(r.st.tickets[tid].reason.splitlines() or [''])[0]}"
              for tid in r.order if r.st.tickets[tid].status == state.FAILED]
    if failed:
        tickets += f" ({', '.join(failed)})"
    if f.get("phase") in finish.BASE_REPORT_PHASES and (left := _pending(r)):
        tickets += f" · 남은 티켓 {left}개 → 다음 gs go"
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
