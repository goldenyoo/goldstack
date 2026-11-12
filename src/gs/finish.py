"""integration 보고서 → PR → 병합 확인 → base 재검증 → 필요하면 일반 revert push.

base 브랜치와 원격은 `.goldstack/config.toml`의 `git.base`·`git.remote`다(r.base, r.remote, r.base_ref).
상태 이름·로그 이름의 `main`(phase `main_failed`, `main-verify.log`)은 "base 브랜치"를 뜻하는 옛 이름이다.

병합 방식은 `git.merge_method`(merge·squash)다. 병합을 요청할 때 finish에 남기고(`merge_method`) 그 PR의
확인·revert·재개는 남긴 방식을 따른다. merge는 병합 커밋이 검증한 integration(`merge_head`)을 조상으로 갖는지,
squash는 squash 커밋(부모 하나)의 tree가 `merge_head`의 tree와 같은지로 확인한다. revert는 둘 다 그 커밋 하나다.
이 PR이 base에 들이는 merged 티켓의 closes 번호를 PR 본문과 squash 메시지에 종료 키워드로 남긴다(이 PR 뒤에도 되돌린 채인 티켓의 번호는 뺀다).
그 뒤 `sync_issues`가 issue를 base의 지금 상태에 맞춘다: 반영된 티켓의 issue는 고정 문구 댓글을 달고 닫고(앞 PR이 있어도), 되돌린 티켓의 issue는 다시 연다.
squash 커밋 본문에는 티켓별 `gs-ticket: <f>/NN` 줄을 남겨 base에서도 병합된 티켓·이 feature의 병합을 알아본다.

`git.wait_checks`면 병합 전에 PR 검사를 기다린다(`_poll_checks`). 기다릴 이름은 `git.checks`가 있으면 그 이름만이고 base 보호·rulesets는
읽지 않는다. 비었으면 보호·rulesets 필수 검사 → gh `--required` 판정 → 보고된 모든 검사다. 기능 PR·revert PR·보고서 PR이 같은 규칙을 쓴다.
통과가 아니면 병합하지 않고 PR을 열어 둔다. 기능 PR은 phase `checks_failed`(`CI 실패: <이름>`), `checks_timeout`(`CI 대기 시간 초과`),
`checks_missing`(`git.checks`의 이름이 `checks_grace_seconds`가 지나도 PR에 없음, `CI 검사 없음: <이름>`)으로, revert·보고서 PR은
`<kind>_pending`에 같은 글로 멈춘다. 다음 `gs go`가 같은 head의 검사를 새 대기 시간으로 다시 읽는다.

보호된 base(`git.direct_push = false`)에는 아무것도 직접 push하지 않는다. revert는 `gs/<f>/revert`, 병합 뒤 최종
보고서는 `gs/<f>/report` 브랜치의 PR로 올려 같은 병합 방식(`wait_checks`면 그 PR의 검사도)으로 병합을 시도한다.
승인 등 보호 규칙에 막히면 PR을 열어 둔 채 phase `revert_pending`·`report_pending`("사람 승인 필요: <url>")으로
멈추고, 다음 `gs go`가 그 PR을 다시 읽어 병합됐으면 이어 간다. feature PR이 막히면 `merge_pending`이다.
revert PR을 기다리는 동안 base가 움직였으면 옛 revert를 병합하지 않고 최신 base를 재검증한다(`main-recheck`). 통과하면 gs가 그 PR을 닫고
브랜치를 지운 뒤 verified다(`revert_closing`이 닫기가 남았다는 뜻이고 다음 `gs go`가 재검증 없이 이어 간다). 실패하면 최신 base 위에 revert를
다시 만들어 같은 브랜치를 갱신한다.

base 검증이 처음 실패했고 마지막으로 통과한 integration 커밋(`verified_head`)과 병합 커밋의 차이가 `.goldstack/`뿐이면 revert 전에 한 번 다시 검증한다(`main-retry`).
phase `main_retry`를 남기고 임시 worktree를 치운 뒤 처음부터 다시 읽으니 끊겨서 다음 `gs go`가 잇는 길과 같다. 통과하면 verified이고 outcome에 flaky를 적으며, 실패하면 revert한다.

첫 base 검증 차례(`next_step`이 `VERIFY_MAIN`을 고른 자리)에 받아 온 base 끝이 병합 커밋 그대로이고 `verified_head`와 병합 커밋의 차이가
보고서와 이 feature의 아이디어 파일(`findings.paths`)뿐이면 base 검증을 돌리지 않는다(`_same_as_verified`, `_verify_final`과 같은 기준).
`main-verify.log`에 "integration과 같은 코드(<verified_head>), 건너뜀"을 쓰고 검증을 통과했을 때와 같이 verified로 남긴다. base 끝이 움직였거나,
그 밖의 파일(다른 `.goldstack/` 파일, config 포함)이 다르거나, `verified_head`가 없으면(옛 state) 지금처럼 검증한다. 재시도·재검증,
`main_failed`·`main_retry`, revert가 있거나 올린 상태, 외부 revert에는 적용하지 않는다(이미 확인한 실패를 덮지 않는다). 지난 검증 결과(`main_head`)가
남았으면 준비 실패로 phase가 `base_unverified`가 된 뒤에도 마찬가지다. 끊긴 뒤 다음 `gs go`도 같은 길을 지난다.

verified·reverted의 마무리 순서: integration에 보고서 커밋 → base에 보고서 커밋(직접 push·보고서 PR) → base를
integration에 합침. 합친 뒤에는 report.md를 다시 쓰지 않아 base판과 같다. 그래서 다음 PR이 report.md에서 충돌하지 않는다.

보고서 커밋에는 보고만 high·medium 지적의 아이디어 파일(findings.py)이 함께 들어간다. 첫 보고서 커밋에 들어가 보통
feature PR로 base에 간다. base에 없으면(revert가 지움, 파일을 쓰기 전의 gs가 연 PR) base 보고서 커밋이 더한다.

모든 push는 `git.push`로 실행 시작 때의 push 설정과 대조한다. 다르면 push하지 않고 `git.PushSettingsChanged`로 멈춘다.
보고서 push의 "최선" 처리도 이것은 삼키지 않는다.

finish 상태를 외부 작업마다 저장한다. 병합 후 중단된 실행은 같은 PR을 다시 병합하지 않고
base 검증/revert를 이어 간다. 호출 worktree의 base 브랜치는 건드리지 않는다.
병합 뒤 무엇을 할지는 `revert_decision.next_step`이 정하고 `_postmerge`는 사실을 읽어 그 답을 실행한다.
integration 전체 검증 실패(integration·integration-final·integration-recheck)로 not_merged가 되면 실패한 검증 단계를 남겨 보고서가 로그·후보 티켓을 붙이고 병합된 티켓의 이유에 그 단계를 적는다.

마무리를 멈춘 git 오류는 어느 단계에서 났든 `run`이 finish.error에 남긴다(`_note_failure`). 준비·보고서·PR 단계(`_publish` 등)도 같다.
결함 수집(feedback.finish_anomaly)이 이 글로 gs 결함과 환경 오류를 가른다. push 설정 변경은 go.go가 남긴다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
from dataclasses import replace
from pathlib import Path
from urllib.parse import quote

from . import clean, doctor, feedback, findings, git, metrics, report, review, revert_decision, setup, state, verify
from .feature import WORK

# 이 phase로 마무리가 끝나면 최종 report.md를 base에도 남긴다(spec 2-6).
BASE_REPORT_PHASES = ("verified", "reverted")
# CI를 기다리거나 기다리다 멈춘 phase. checks_missing: `git.checks`에 적은 검사가 유예 뒤에도 PR에 없다.
CHECK_PHASES = ("checks_pending", "checks_failed", "checks_timeout", "checks_missing")
# 보호된 base에서 gs의 revert·보고서 PR이 사람을 기다린다. 다음 gs go가 그 PR을 다시 읽는다.
PENDING_PHASES = ("revert_pending", "report_pending")
# gs go가 새 worker보다 먼저 마무리를 회복하는 phase. revert_closing: 재검증을 통과했고 revert PR 닫기가 남았다. main_retry: 첫 base 검증이 실패했고 코드가 같아 재시도가 남았다.
RESUME_PHASES = (*CHECK_PHASES, "merge_requested", "merge_pending", "merged", "main_failed", "main_retry", "base_unverified",
                 "revert_closing", *PENDING_PHASES)
# 마무리 결과(verified·reverted)가 아직 정해지지 않은 phase. report_pending은 결과가 report_result에 정해져 있다.
UNSETTLED_PHASES = tuple(phase for phase in RESUME_PHASES if phase != "report_pending")
REVERT_LINE = re.compile(r"^This reverts commit ([0-9a-f]{40,64})", re.M)  # git revert의 기본 메시지
CHECK_INTERVAL = 10
MAX_FINISH_ERRORS = 20  # state.finish_errors에 남길 서로 다른 오류 수. 넘으면 오래된 것부터 잊는다


def _save(r, **fields) -> None:
    r.st.finish.update(fields)
    r.save()


def _clear_error(r) -> None:
    """성공했으니 지난 거부·일시 오류는 끝난 일이다. 보고서 Merge Danger에 남기지 않는다."""
    if r.st.finish.pop("error", None) is not None:
        r.save()


def _note_failure(r, e: Exception) -> None:
    """마무리를 멈춘 오류를 남긴다. `error`는 보고서 Merge Danger와 결함 수집이 읽는다.

    verified·reverted는 결과가 이미 정해졌으니 outcome을 그대로 둔다(다음 마무리의 `_clear_error`가 error만 지운다).
    다른 phase는 `integration 검증 중` 같은 옛 글이 결과로 남지 않게 outcome도 바꾼다.
    `finish_errors`에도 적는다. 새 마무리가 finish를 비워도 결함 수집이 같은 오류를 알아본다.
    """
    text = str(e)
    e.gs_noted = True  # 이번 실행이 처리한 예외다. `_noted`가 원인 사슬에서 이 표시를 찾는다
    if text not in r.st.finish_errors:
        r.st.finish_errors = [*r.st.finish_errors, text][-MAX_FINISH_ERRORS:]
    fields = {} if r.st.finish.get("phase") in BASE_REPORT_PHASES else {"outcome": f"{feedback.FINISH_FAILED}: {e}"}
    _save(r, error=text, **fields)


def _noted(r, e: BaseException | None) -> bool:
    """e가 이번 실행에서 `_note_failure`가 처리한 오류이거나 그것을 처리하다 난 오류인가. 뒤따른 보고서 갱신 실패로 원인을 덮지 않는다.

    글자가 아니라 예외 객체로 본다. 재개 때 `finish.error`에 같은 글자가 남아 있어도 이번 실행이 처리하지 않았으면 다시 남긴다.
    """
    while e is not None:
        if getattr(e, "gs_noted", False):
            return True
        e = e.__context__
    return False


def _gh(r, *args: str, deadline: float | None = None) -> str:
    repository = git.github_repo(r.repo, r.remote)
    timeout = None if deadline is None else deadline - time.monotonic()
    if timeout is not None and timeout <= 0:
        raise subprocess.TimeoutExpired(["gh", "pr", *args], 0)
    try:
        cp = subprocess.run([os.environ.get("GS_GH", "gh"), "pr", *args, "--repo", repository], cwd=r.repo,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except OSError as e:
        raise git.GitError(f"gh pr {args[0]}: {e}") from e
    if cp.returncode:
        raise git.GitError(f"gh pr {args[0]}: {(cp.stderr or cp.stdout).strip()}")
    return cp.stdout.strip()


def _view(r, url: str | None = None, *, deadline: float | None = None) -> dict:
    try:
        options = {"deadline": deadline} if deadline is not None else {}
        value = json.loads(_gh(r, "view", url or r.st.finish["url"], "--json",
                               "state,mergeCommit,headRefOid,baseRefName,reviewDecision", **options))
        if not isinstance(value, dict):
            raise ValueError("PR 객체가 아니다")
        return value
    except ValueError as e:
        raise git.GitError(f"gh pr view 응답 오류: {e}") from e


def _checks(r, *, required: bool, deadline: float, url: str | None = None) -> list[dict]:
    """gh가 필수 여부를 판정한다. 검사 없음만 빈 목록이고 API·인증 오류는 실패다."""
    try:
        raw = _gh(r, "checks", url or r.st.finish["url"], "--json", "name,bucket",
                  *(["--required"] if required else []), deadline=deadline)
    except git.GitError as e:
        if str(e).startswith(("gh pr checks: no checks reported on ",
                              "gh pr checks: no required checks reported on ")):
            return []
        raise
    try:
        checks = json.loads(raw)
        if not isinstance(checks, list) or any(
                not isinstance(c, dict) or not isinstance(c.get("name"), str)
                or c.get("bucket") not in ("pass", "fail", "pending", "skipping", "cancel") for c in checks):
            raise ValueError("검사 목록이 아니다")
        return sorted(checks, key=lambda c: (c["name"], c["bucket"]))
    except ValueError as e:
        raise git.GitError(f"gh pr checks 응답 오류: {e}") from e


def _required_checks(r, deadline: float) -> set[str]:
    """base 보호·rulesets의 필수 이름을 읽는다. 한쪽이라도 조회 불가면 gh 판정을 쓴다."""
    repository = git.github_repo(r.repo, r.remote)
    branch = quote(r.base, safe="")
    names = set()
    for endpoint, parse in ((f"branches/{branch}/protection", doctor._classic),
                            (f"rules/branches/{branch}", doctor._rules)):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(["gh", "api"], 0)
        try:
            cp = subprocess.run([os.environ.get("GS_GH", "gh"), "api", f"repos/{repository}/{endpoint}"],
                                cwd=r.repo, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                timeout=min(20, remaining))
            if cp.returncode:
                return set()  # 부분 목록을 전체 필수 검사로 취급하지 않는다.
            names.update(parse(json.loads(cp.stdout))[2] or [])
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return set()
    return names


def _poll_checks(r, url: str, head: str, on_poll) -> tuple[str, list[str]]:
    """PR url의 검사를 끝날 때까지 읽는다. ("pass"|"fail"|"timeout"|"missing", 이름).
    이름은 "fail"이면 실패·취소한 검사, "missing"이면 유예(`checks_grace_seconds`)가 지나도 PR에 없는 `git.checks` 이름(적은 순서)이다.

    기다릴 검사: `git.checks`가 있으면 그 이름만 기다리고 base 보호·rulesets는 읽지 않는다. 없으면 보호·rulesets 필수 검사,
    그것도 없으면 gh `--required` 판정, 그것도 비면 보고된 모든 검사다. 기능 PR과 `_side_pr`(revert·보고서 PR)이 함께 쓴다.
    재실행에는 새 대기 시간을 주고 검사를 다시 읽는다. PR이 닫히거나 head가 바뀌면 GitError."""
    started = time.monotonic()
    deadline = started + r.cfg.timeouts.checks_minutes * 60
    grace = started + r.cfg.timeouts.checks_grace_seconds
    named = r.cfg.git.checks
    try:
        required_names = set(named) or _required_checks(r, deadline)
    except subprocess.TimeoutExpired:
        return "timeout", []
    previous = None
    number = url.rstrip("/").rsplit("/", 1)[-1]
    symbols = {"pass": "✓", "skipping": "✓", "pending": "…", "fail": "✗", "cancel": "✗"}
    while True:
        missing: list[str] = []
        try:
            if required_names:
                reported = _checks(r, url=url, required=False, deadline=deadline)
                checks = [c for c in reported if c["name"] in required_names]
                seen = {c["name"] for c in checks}
                missing = [name for name in (named or sorted(required_names)) if name not in seen]
                checks += [{"name": name, "bucket": "pending"} for name in missing]
                checks.sort(key=lambda c: (c["name"], c["bucket"]))
            else:
                checks = (_checks(r, url=url, required=True, deadline=deadline)
                          or _checks(r, url=url, required=False, deadline=deadline))
            # checks는 현재 PR을 읽으므로 조회 뒤 head를 대조한다. 병합도 --match-head-commit으로 고정한다.
            view = _view(r, url, deadline=deadline)
        except subprocess.TimeoutExpired:
            return "timeout", []
        if view.get("state") != "OPEN" or view.get("headRefOid") != head:
            raise git.GitError("CI 대기 중 PR 상태 또는 head가 바뀌었다. 다음 gs go에서 다시 확인한다")
        if checks != previous:
            detail = ", ".join(f"{c['name']} {symbols[c['bucket']]}" for c in checks) or "검사 없음"
            print(f"■ PR #{number}: CI 검사 대기 중({detail})", flush=True)
            previous = checks
        on_poll(checks)  # 변화가 없어도 진행 바의 경과 시간·heartbeat는 갱신한다.
        failed = [c["name"] for c in checks if c["bucket"] in ("fail", "cancel")]
        if failed:
            return "fail", failed
        if checks and all(c["bucket"] in ("pass", "skipping") for c in checks):
            return "pass", []
        now = time.monotonic()
        # 적은 이름이 PR에 없으면 설정 오류일 수 있다. 시간 초과까지 기다리지 않고 유예 뒤 병합 없이 멈춘다.
        # 보호·rulesets의 필수 이름은 지금처럼 끝까지 기다린다(missing은 pending으로 보인다).
        if named and missing and now >= grace:
            print(f"■ PR #{number}: CI 검사 없음({', '.join(missing)}) → 병합 안 함", flush=True)
            return "missing", missing
        if not checks and now >= grace:
            print(f"■ PR #{number}: 검사 없음 → 병합", flush=True)
            return "pass", []
        remaining = deadline - now
        if remaining <= 0:
            return "timeout", []
        early = not checks or bool(named and missing)  # 유예가 끝나는 때에 맞춰 다시 읽는다
        time.sleep(min(CHECK_INTERVAL, remaining, grace - now) if early else min(CHECK_INTERVAL, remaining))


def _checks_outcome(status: str, names: list[str]) -> str:
    """`_poll_checks`가 병합하지 않고 끝난 결과의 outcome 글(기능 PR과 `_side_pr`이 같은 글을 쓴다)."""
    if status == "fail":
        return f"CI 실패: {', '.join(names)}"
    if status == "missing":
        return f"CI 검사 없음: {', '.join(names)}"
    return "CI 대기 시간 초과"


@metrics.stage("checks")
def _wait_checks(r) -> bool:
    """보고서까지 검증한 head만 기다린다. 통과가 아니면 PR을 열어 둔 채 결과별 phase로 멈추고 다음 gs go가 다시 읽는다."""
    _save(r, phase="checks_pending", outcome="CI 검사 대기 중")
    status, names = _poll_checks(r, r.st.finish["url"], r.st.finish["merge_head"], lambda c: _save(r, checks=c))
    if status != "pass":
        phase = {"fail": "checks_failed", "missing": "checks_missing"}.get(status, "checks_timeout")
        _save(r, phase=phase, outcome=_checks_outcome(status, names))
        return False
    _save(r, phase="merge_requested", outcome="CI 검사 통과, 병합 대기")
    return True


def _refresh_check_head(r, view: dict) -> bool:
    """사람이 고친 PR은 그 head 자체를 다시 검증한다. 보고서 커밋으로 CI를 다시 시작하지 않는다."""
    head = view.get("headRefOid")
    if head == r.st.finish["merge_head"]:
        return True
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise git.GitError("CI 재개할 PR head를 확인할 수 없다")
    git.run(r.repo, "fetch", "-q", r.remote, head)
    _restore_integration(r, head)
    r.ihead = head
    ok = _verify(r, r.iwt, "integration-recheck")
    if not ok:
        _restore_integration(r, head)
        _save(r, integration_ok=False, failed_verify="integration-recheck", phase="not_merged",
              outcome="integration 검증 실패 → 병합 안 함")
        return False
    _save(r, head=head, merge_head=head, integration_ok=True)
    return True


def _ancestor(cwd: Path, a: str, b: str) -> bool:
    return git.run(cwd, "merge-base", "--is-ancestor", a, b, check=False).returncode == 0


def _revert_of(cwd: Path, sha: str, *revs: str) -> str:
    """revs에서 sha를 되돌린 커밋(git revert의 기본 메시지로 찾는다). 없으면 빈 문자열."""
    return git.out(cwd, "log", "-1", "--format=%H", "--fixed-strings", f"--grep=This reverts commit {sha}", *revs)


def _trailers(r, rev: str) -> set[str]:
    """rev까지의 integration 병합·base squash에서 이 feature의 정확한 티켓 id."""
    return git.ticket_trailers(r.repo, r.name, rev, base_ref=r.base_ref)


def _feature_merge(r, sha: str) -> bool:
    """sha가 이 feature의 티켓을 base에 들인 병합 커밋(merge) 또는 squash 커밋인가."""
    if sha == r.st.finish.get("merge_sha"):
        return True
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]
    if len(parents) == 1:
        # squash 커밋은 부모가 하나이고 본문에 티켓별 gs-ticket 줄이 있다. integration의 티켓 병합은 늘 부모가 둘이다.
        return bool(git.ticket_trailers(r.repo, r.name, "--no-walk", sha, base_ref=r.base_ref))
    return len(parents) > 1 and bool(git.ticket_trailers(r.repo, r.name, f"{parents[0]}..{parents[1]}"))


def _undone_reverts(r) -> list[tuple[str, str]]:
    """원격 base에 있는, 이 feature의 병합을 되돌린 revert 중 integration·base 어디서도 다시 되돌리지 않은 것.
    [(revert, 되돌린 병합)], 오래된 것부터."""
    found = []
    for c in reversed(git.out(r.repo, "log", "--format=%H", "--grep=^This reverts commit ", r.base_ref).split()):
        m = re.search(r"^This reverts commit ([0-9a-f]{40,64})", git.out(r.repo, "log", "-1", "--format=%B", c), re.M)
        if m and _feature_merge(r, m.group(1)) and not _revert_of(r.repo, c, r.base_ref, f"gs/{r.name}/integration"):
            found.append((c, m.group(1)))
    return found


def merge_base(r) -> None:
    """원격 base(r.base_ref)를 integration에 합친다.

    base가 이 feature의 병합을 revert했으면 그냥 합칠 때 integration이 revert까지 따라가 feature 코드가 조용히
    사라진다(gs-ticket 트레일러는 남아 티켓은 merged로 보인다). 그래서 원격 base 위에 그 revert를 되돌린
    커밋(revert의 revert)을 만들어 합친다. 다음 PR이 feature 코드를 다시 들인다.

    squash PR의 병합을 확인하기 전(merge_requested·merge_pending)에는 합치지 않는다. 그사이 PR이 squash로
    병합됐으면 squash 커밋을 아직 몰라(merge_sha 없음) 옛 base를 merge-base로 합치다 충돌할 수 있다. 확인 뒤
    run이 다시 부른다(그때는 _absorb_squash가 squash 커밋을 표시한다). 병합 대기 중인 PR head도 바꾸지 않는다.
    """
    f = r.st.finish
    if f.get("phase") in CHECK_PHASES:
        return  # 실패 기록·base 병합으로 CI를 기다리는 PR head를 바꾸지 않는다.
    if (f.get("merge_method") == "squash" and f.get("phase") in ("merge_requested", "merge_pending")
            and not f.get("merge_sha")):
        return
    if not _restore_reverts(r):
        _merge(r, r.base_ref)


@metrics.stage("restore-reverts", finishing_only=True)
def _restore_reverts(r) -> bool:
    """base에 있는 이 feature 병합의 revert를 되돌린 커밋을 integration에 합친다. 합쳤으면 True(그 base까지 합친 것이다)."""
    _absorb_squash(r)
    reverts = _undone_reverts(r)
    if not reverts:
        return False
    with tempfile.TemporaryDirectory(prefix="gs-restore-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), r.base_ref)
        try:
            done = []
            for c, merge in reverts:
                res = git.run(wt, "revert", "--no-edit", c, check=False)
                if res.returncode:
                    git.run(wt, "revert", "--abort", check=False)
                    raise git.GitError(f"{r.base}의 revert {c}(병합 {merge}를 되돌림)를 다시 되돌리다 충돌했다. "
                                       f"feature 코드를 손으로 되살려라: {(res.stdout + res.stderr).strip()}")
                done.append({"revert": c, "merge": merge, "commit": git.sha(wt, "HEAD")})
            _merge(r, done[-1]["commit"])
        finally:
            git.remove_worktree(r.repo, wt)
    _save(r, reintroduced=r.st.finish.get("reintroduced", []) + done)
    for d in done:
        print(f"■ {r.base}가 이 feature의 병합 {d['merge'][:8]}을 되돌렸다(revert {d['revert'][:8]}). "
              f"integration에서 그 revert를 다시 되돌렸다({d['commit'][:8]})", flush=True)
    return True


def _absorb_squash(r) -> None:
    """base에 든 이 PR의 squash 커밋을 integration에 '이미 병합됨'으로 남긴다.

    squash 커밋은 merge_head를 조상으로 갖지 않아 integration과 base의 merge-base가 옛 base에 머문다. 그 뒤
    integration의 보고서가 바뀌면(마무리 실패 기록 등) base를 합칠 때 report.md가 양쪽에서 따로 추가돼 충돌한다.
    squash 커밋은 merge_head에 base의 변경을 얹은 것이므로 merge_head를 기준으로 합친다(tree가 같으면 integration 그대로).
    """
    f = r.st.finish
    sha, head = f.get("merge_sha"), f.get("merge_head")
    if (f.get("merge_method") != "squash" or not sha or not head or not _ancestor(r.repo, sha, r.base_ref)
            or _ancestor(r.iwt, sha, "HEAD") or not _ancestor(r.iwt, head, "HEAD")):
        return
    res = git.run(r.iwt, "merge-tree", "--write-tree", f"--merge-base={head}", "HEAD", sha, check=False)
    if res.returncode:
        return  # 충돌(또는 옛 git). 아래 일반 병합이 충돌로 알린다
    tree = res.stdout.split()[0]
    commit = git.out(r.iwt, "commit-tree", tree, "-p", "HEAD", "-p", sha,
                     "-m", f"gs: {r.base}의 squash 병합 {sha[:8]}을 gs/{r.name}/integration에 표시")
    git.run(r.iwt, "merge", "-q", "--ff-only", commit)


def _merge(r, rev: str) -> None:
    res = git.run(r.iwt, "merge", "--no-edit", rev, check=False)
    if res.returncode:
        git.run(r.iwt, "merge", "--abort", check=False)
        raise git.GitError(f"{r.base_ref}를 gs/{r.name}/integration에 합치다 충돌했다: {res.stdout.strip()}")


@metrics.stage("verify")
def _verify(r, wt: Path, label: str) -> bool:
    """명령과 실제 출력·종료 코드를 보존한다. 검증이 worktree를 바꾸면 통과로 인정하지 않는다.
    종료 코드 줄은 verify.run이 쓴다. 시간을 넘기면 그 줄 바로 앞이 `시간 초과: <N>분` 줄이고 실패다. 끊김(Result.interrupted)도 여느 실패와 같다: 끊겼다고 다시 돌리는 것은 티켓 검증뿐이다.
    지난 gs가 남긴 검증은 이번 gs go가 시작할 때 이미 끝냈다(verify.stop_stale). 로그 경로가 그 표지다.
    integration worktree에서 통과하면 그 커밋을 `verified_head`로 남긴다. 첫 base 검증 전에 `_same_as_verified`가, base 검증이 실패했을 때
    `_code_same`이 병합 커밋과 비교한다.
    판별(verify 머리말)은 실행 중인 config `[verify]`로 하고, 판별·전체 재실행 전에 같은 트리 규칙(`same`)으로 트리를 확인한다."""
    log = r.rundir / "finish" / f"{label}-verify.log"
    head = git.sha(wt, "HEAD")
    branch = git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout

    def same() -> bool:
        return (git.sha(wt, "HEAD") == head and setup.is_clean(wt)
                and git.run(wt, "symbolic-ref", "-q", "HEAD", check=False).stdout == branch)

    print(f"■ {label} 검증: {r.feat.spec.verify}", flush=True)
    with log.open("w", encoding="utf-8") as stream:
        stream.write(f"$ {r.feat.spec.verify}\nHEAD: {head}\n")
        res = verify.run(r.feat.spec, wt, stream, r.cfg.verify, same)
        if res.timed_out:
            print(f"■ {label} 검증 시간 초과({res.minutes}분): 프로세스 그룹을 끝냈다", flush=True)
            metrics.validation(r, label, r.feat.spec.verify, head, res)
            return False
        changed = not same()
        if changed:
            stream.write("검증 중 worktree가 바뀌었다. 검증 실패로 처리한다.\n")
        elif res.ok:
            verify.flaky(res, label, stream)
    metrics.validation(r, label, r.feat.spec.verify, head, res, changed)
    ok = res.ok and not changed
    if ok and wt == r.iwt:
        _save(r, verified_head=head)
    return ok


def _report_paths(r) -> set[str]:
    """검증을 다시 돌리지 않아도 되는 차이: 이 feature의 보고서와 아이디어 파일. `_verify_final`과 `_same_as_verified`가 함께 쓴다."""
    return {f"{WORK}/{r.name}/report.md", *findings.paths(r)}


def _verify_final(r, verified_head: str) -> bool:
    """통과한 integration과 보고서·이 feature의 아이디어 파일만 다르면 최종 검증 결과를 재사용한다."""
    changed = git.run(r.iwt, "diff", "--no-renames", "--name-only", "-z", verified_head, "HEAD").stdout
    if set(changed.split("\0")) - {""} <= _report_paths(r) and setup.is_clean(r.iwt):
        message = "integration-final: 보고서만 바뀜, 건너뜀"
        (r.rundir / "finish" / "integration-final-verify.log").write_text(message + "\n", encoding="utf-8")
        print(f"■ {message}", flush=True)
        return True
    return _verify(r, r.iwt, "integration-final")


@metrics.stage("restore-integration")
def _restore_integration(r, head: str) -> None:
    git.run(r.iwt, "merge", "--abort", check=False)
    git.run(r.iwt, "checkout", "--force", f"gs/{r.name}/integration")
    git.run(r.iwt, "reset", "--hard", head)
    setup.clean(r.iwt, "-fd")


@metrics.stage("report")
def _commit_report(r, summary: str) -> Path:
    path = report.write(r, summary)
    rel = str(path.relative_to(r.iwt))
    rels = [rel, *findings.write(r)]
    git.run(r.iwt, "add", "--", rel)
    if git.run(r.iwt, "diff", "--cached", "--quiet", "--", *rels, check=False).returncode:
        # 보고서·아이디어 파일 외의 staged 파일을 이 커밋에 넣지 않는다.
        git.run(r.iwt, "commit", "-m", f"gs: {r.name} 최종 보고서", "--only", "--", *rels)
    return path


@metrics.stage("push")
def _push(r) -> None:
    git.push(r.iwt, r.remote, r.st.push_record, f"HEAD:refs/heads/gs/{r.name}/integration", flags=("-u",))


def _closing_numbers(r, tids=None) -> list[int]:
    allowed = set(r.feat.tickets) if tids is None else set(tids)
    return sorted({number for tid, ticket in r.feat.tickets.items()
                   if tid in allowed and tid in r.st.tickets and r.st.tickets[tid].status == state.MERGED
                   for number in ticket.closes})


def _restoring(r, head: str) -> list[dict]:
    """head에 들었고 base에는 아직 없는 되살림(`_restore_reverts`의 기록)."""
    return [x for x in r.st.finish.get("reintroduced", [])
            if _ancestor(r.repo, x["commit"], head) and not _revert_of(r.repo, x["revert"], r.base_ref)]


def _restored_tickets(r, restoring: list[dict]) -> set[str]:
    return {tid for x in restoring for tid in _trailers(r, f"{x['merge']}^..{x['merge']}")}


def _closing_lines(r, tids, head: str) -> str:
    """tids 중 head의 병합이 닫아도 되는 issue의 종료 키워드. PR 본문과 squash 메시지가 같이 쓴다.

    앞서 base에 들어가 지금도 있는 티켓은 뺀다. 넣으면 그 뒤 다시 열린 issue를 이 PR의 병합이 또 닫는다.
    이 PR 뒤에도 base에서 되돌린 채인 티켓의 issue도 뺀다. 같은 issue를 닫는 다른 티켓이 있어도 그렇다(`_issue_plan`과 같다).
    개별 티켓의 revert는 `_restore_reverts`가 되살리지 않아 그 표시만 이력에 남는다. 되살리는 티켓을 여기서 놓쳐도 병합 뒤 `sync_issues`가 닫는다."""
    if not _closing_numbers(r, tids):
        return ""
    base = _base_tickets(r)
    merge = r.st.finish.get("merge_sha")  # 이 PR이 이미 병합됐으면 그 티켓은 키워드를 그대로 둔다
    landed = {tid for tid, (kept, commit) in base.items() if kept and commit != merge}
    back = _restored_tickets(r, _restoring(r, head))
    reverted = {number for tid, (kept, _) in base.items() if not kept and tid not in back and tid in r.feat.tickets
                for number in r.feat.tickets[tid].closes}
    return "\n".join(f"Closes #{number}" for number in _closing_numbers(r, set(tids) - landed) if number not in reverted)


def _pr_body(r, path: Path) -> Path:
    """이 PR이 base에 들이는 티켓의 종료 키워드(`_closing_lines`)를 보고서 길이 제한 밖에 보존한다."""
    head = git.sha(r.iwt, "HEAD")
    closing = _closing_lines(r, _trailers(r, head), head)
    if not closing:
        return path
    suffix = "\n\n" + closing
    body = path.read_text(encoding="utf-8")[:report.MAX_BODY - len(suffix)] + suffix
    target = r.rundir / "finish" / "pr-body.md"
    target.write_text(body, encoding="utf-8")
    return target


def _base_tickets(r) -> dict[str, tuple[bool, str]]:
    """원격 base 이력에서 티켓마다 (지금 들어 있는가, 그렇게 만든 base 커밋)을 정한다. 마지막으로 바뀐 티켓이 뒤에 온다.

    gs-ticket 표시는 revert 뒤에도 이력에 남아 표시만으로는 반영을 알 수 없다. 그래서 표시와 `This reverts commit` 줄을
    base에 들어온 순서대로 적용한다. revert의 revert는 되살림이고, 병합을 되돌리면 그 가지가 들인 티켓이 함께 빠진다.
    base 커밋은 첫 부모 줄의 커밋이다(PR 병합 커밋, squash 커밋, 직접 push).
    """
    fields = git.run(r.repo, "log", "--topo-order", "--reverse", "--format=%H%x00%P%x00%B%x00", r.base_ref).stdout.split("\0")
    commits = {sha.strip(): (parents.split(), body)
               for sha, parents, body in zip(fields[::3], fields[1::3], fields[2::3])}
    marker = f"gs-ticket: {r.name}/"

    def changes(sha: str) -> dict[str, bool]:
        """sha 자신이 티켓을 어떻게 바꾸는가. 병합이 들인 가지는 가지의 커밋이 저마다 바꾼다."""
        body = commits[sha][1]
        found: dict[str, bool] = {}
        for target in REVERT_LINE.findall(body):
            if target in commits:
                found.update((tid, not kept) for tid, kept in brought(target).items())
        if marker in body:  # 어느 커밋의 표시를 셀지는 ticket_trailers의 규칙을 따른다(worker 일반 커밋은 세지 않는다)
            found.update(dict.fromkeys(git.ticket_trailers(r.repo, r.name, "--no-walk", sha, base_ref=r.base_ref), True))
        return found

    def brought(sha: str) -> dict[str, bool]:
        """sha를 되돌리면 뒤집힐 변화: sha 자신과, 병합이면 그 가지."""
        parents = commits[sha][0]
        found: dict[str, bool] = {}
        if len(parents) > 1:
            for commit in git.out(r.repo, "rev-list", "--topo-order", "--reverse", f"{parents[0]}..{parents[1]}").split():
                found.update(changes(commit))
        found.update(changes(sha))
        return found

    chain, sha = [], git.sha(r.repo, r.base_ref)
    while sha in commits:
        chain.append(sha)
        sha = next(iter(commits[sha][0]), "")
    chain.reverse()
    owner: dict[str, str] = {}  # 커밋 → 그 커밋을 base에 들인 첫 부모 줄의 커밋
    for head in chain:
        stack = [head]
        while stack:
            sha = stack.pop()
            if sha in commits and sha not in owner:
                owner[sha] = head
                stack.extend(commits[sha][0])
    rank = {head: position for position, head in enumerate(chain)}
    status: dict[str, tuple[bool, str]] = {}
    for sha in sorted(commits, key=lambda commit: rank[owner[commit]]):  # 안정 정렬: 한 줄의 커밋 안에서는 log의 순서(부모 먼저)다
        for tid, kept in changes(sha).items():
            status.pop(tid, None)
            status[tid] = (kept, owner[sha])
    return status


def _issue_plan(r) -> dict[int, tuple[str, str]]:
    """{issue: ("close"|"reopen", 근거 base 커밋)}. 같은 issue의 티켓 중 하나라도 되돌렸으면 다시 연다.

    결과가 정해지지 않은 PR의 티켓은 base에 보여도 아직 닫지 않는다(검증 실패로 되돌릴 수 있다). 끝나면 _run이 다시 부른다."""
    f = r.st.finish
    waiting = _trailers(r, f["merge_head"]) if f.get("phase") in UNSETTLED_PHASES and f.get("merge_head") else set()
    close: dict[int, str] = {}
    reopen: dict[int, str] = {}
    for tid, (kept, commit) in _base_tickets(r).items():
        if tid not in r.feat.tickets:
            continue
        if not kept:
            reopen.update(dict.fromkeys(r.feat.tickets[tid].closes, commit))
        elif tid not in waiting:
            close.update(dict.fromkeys(_closing_numbers(r, [tid]), commit))
    return {**{n: ("close", c) for n, c in close.items()}, **{n: ("reopen", c) for n, c in reopen.items()}}


def _fixed_version(r, commit: str) -> str:
    """commit의 `pyproject.toml` 버전. 실행 중인 gs는 설치본이라 고친 버전이 아니다. 없거나 형식이 다르면 feature 이름."""
    shown = git.run(r.repo, "show", f"{commit}:pyproject.toml", check=False).stdout
    try:
        version = tomllib.loads(shown)["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError):
        return r.name
    return version if isinstance(version, str) and re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+_-]*", version) else r.name


def _apply_issue(r, target: str, number: int, action: str, commit: str) -> None:
    """지금 상태를 읽어 할 일만 한다. 댓글은 고정 문구뿐이고, 같은 문구가 이미 있으면 달지 않는다(지난 응답을 못 받았어도).

    닫기는 언제나 completed다. not planned는 사람이 치는 `gh issue close --reason "not planned"`로만 한다."""
    view = json.loads(feedback._gh(r.repo, target, "issue", "view", str(number), "--json", "state,comments"))
    if view["state"] not in ("OPEN", "CLOSED"):
        raise ValueError("issue 상태를 모른다")
    if action == "reopen":
        if view["state"] == "CLOSED":
            feedback._gh(r.repo, target, "issue", "reopen", str(number))
        return
    comment = f"{_fixed_version(r, commit)}에서 고침 ({commit})"
    if comment not in [c["body"].strip() for c in view["comments"]]:
        feedback._gh(r.repo, target, "issue", "comment", str(number), "--body", comment)
    if view["state"] == "OPEN":
        feedback._gh(r.repo, target, "issue", "close", str(number), "--reason", "completed")


def sync_issues(r) -> None:
    """티켓 `closes`의 issue를 base의 지금 상태에 맞춘다. 실패는 finish와 보고서에만 남고 병합·결과를 바꾸지 않는다.

    끝낸 일은 finish.issues에 (할 일, 근거 커밋)으로 남겨 base가 바뀌기 전에는 gh를 다시 부르지 않는다. 사람이 그 뒤에 issue를
    열거나 닫아도 되돌리지 않는다. 실패한 일은 다음 gs go가 다시 시도한다."""
    if not any(ticket.closes for ticket in r.feat.tickets.values()):
        return
    f = r.st.finish
    try:
        plan = _issue_plan(r)
        target = git.github_repo(r.repo, r.remote)
    except (git.GitError, OSError) as e:
        _save(r, issues_error=str(e))
        print(f"■ 경고: issue 상태를 맞추지 못했다. 다음 gs go가 다시 시도한다: {e}", flush=True)
        return
    f.pop("issues_error", None)
    issues = dict(f.get("issues", {}))
    for number, (action, commit) in sorted(plan.items()):
        done = {"action": action, "commit": commit, "ok": True}
        if issues.get(str(number)) == done:
            continue
        close = action == "close"
        try:
            _apply_issue(r, target, number, action, commit)
            print(f"■ issue #{number} {'닫음' if close else '다시 엶'}", flush=True)
        except (git.GitError, OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired):
            done["ok"] = False
            print(f"■ 경고: issue #{number} {'닫기' if close else '다시 열기'} 실패(gh). 다음 gs go가 다시 시도한다", flush=True)
        issues[str(number)] = done
        _save(r, issues=issues)


@metrics.stage("publish")
def _publish(r, path: Path) -> str:
    path = _pr_body(r, path)
    branch = f"gs/{r.name}/integration"
    url = _gh(r, "list", "--head", branch, "--base", r.base, "--state", "open", "--json", "url", "--jq", ".[0].url")
    if url:
        _gh(r, "edit", url, "--body-file", str(path.resolve()))
    else:
        created = _gh(r, "create", "--base", r.base, "--head", branch, "--title", f"{r.name}: gs go",
                      "--body-file", str(path.resolve()))
        url = created.splitlines()[-1] if created else ""
    if not url:
        raise git.GitError("PR URL이 비었다")
    _save(r, url=url)
    return url


def _squash_message(r) -> tuple[str, str]:
    """새 티켓·되살린 티켓과 revert의 revert 식별을 squash 커밋에도 보존한다."""
    f = r.st.finish
    number = re.search(r"/(\d+)/?$", f["url"])
    title = f"{r.name}: gs go" + (f" (#{number.group(1)})" if number else "")
    restoring = _restoring(r, f["merge_head"])
    new = (_trailers(r, f["merge_head"]) - _trailers(r, r.base_ref)) | _restored_tickets(r, restoring)
    restored = [f"This reverts commit {x['revert']}." for x in restoring]
    rank = {tid: i for i, tid in enumerate(r.feat.tickets)}
    tids = sorted(new, key=lambda tid: (rank.get(tid, len(rank)), tid))
    listing = [f"{tid} {r.feat.tickets[tid].title}" if tid in r.feat.tickets else tid for tid in tids]
    trailers = [f"gs-ticket: {r.name}/{tid}" for tid in tids]
    sections = ["\n".join(listing), "\n".join(trailers)]
    if closing := _closing_lines(r, tids, f["merge_head"]):
        sections.append(closing)
    if restored:
        sections.append("\n".join(dict.fromkeys(restored)))
    return title, "\n\n".join(sections)


@metrics.stage("merge-pr")
def _merge_pr(r) -> None:
    f = r.st.finish
    if f.get("merge_method", "merge") == "squash":
        subject, body = _squash_message(r)
        _gh(r, "merge", f["url"], "--squash", "--match-head-commit", f["merge_head"], "--subject", subject, "--body", body)
    else:
        _gh(r, "merge", f["url"], "--merge", "--match-head-commit", f["merge_head"])


def _check_merge(r) -> None:
    """병합 커밋이 검증한 integration(merge_head)을 들였는가. merge: 조상 관계, squash: 부모 하나·같은 tree."""
    f = r.st.finish
    merge, head = f["merge_sha"], f["merge_head"]
    if f.get("merge_method", "merge") != "squash":
        if not _ancestor(r.repo, head, merge):
            raise git.GitError("병합 커밋에 검증한 integration이 포함되지 않았다")
        return
    parents = git.out(r.repo, "rev-list", "--parents", "-n", "1", merge).split()[1:]
    if len(parents) != 1:
        raise git.GitError(f"squash 병합인데 병합 커밋 {merge}의 부모가 {len(parents)}개다")
    if git.out(r.repo, "rev-parse", f"{merge}^{{tree}}") != git.out(r.repo, "rev-parse", f"{head}^{{tree}}"):
        raise git.GitError(f"squash 커밋 {merge}의 tree가 검증한 integration {head}의 tree와 다르다"
                           f"(PR 병합 사이에 {r.base}가 움직였을 수 있다). 검증하지 않은 내용이 {r.base}에 들어갔으니 "
                           f"사람이 {r.base}를 확인하라")


def _needs_human(view: dict, error: str) -> bool:
    """병합이 승인 등 보호 규칙에 막혔는가. 큐 대기(명령은 성공)는 아니다."""
    if view.get("reviewDecision") in ("REVIEW_REQUIRED", "CHANGES_REQUESTED"):
        return True
    return bool(error and re.search(r"review|approv|base branch policy|protected branch", error, re.I))


@metrics.stage("confirm-merge")
def _confirm(r, view: dict, error: str = "") -> bool:
    if view.get("state") == "CLOSED":
        # 사람이 병합하지 않고 닫았다. 대기 상태를 풀어 다음 gs go가 새 PR을 열게 한다.
        _save(r, phase="closed", outcome=f"PR {r.st.finish['url']}이 병합되지 않고 닫혔다 → 병합 안 함. "
                                         "다음 gs go가 새 PR을 연다")
        return False
    if view.get("state") != "MERGED":
        if _needs_human(view, error):
            _save(r, phase="merge_pending", outcome=f"사람 승인 필요: {r.st.finish['url']}. {r.base} 검증은 미실행")
        else:
            _save(r, phase="merge_pending", outcome=f"병합 명령 뒤 PR이 아직 MERGED가 아니다. {r.base} 검증은 미실행")
        return False
    commit = view.get("mergeCommit")
    sha = commit.get("oid", "") if isinstance(commit, dict) else ""
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha) or view.get("baseRefName") != r.base:
        raise git.GitError(f"병합된 PR의 {r.base} 대상·병합 커밋을 확인할 수 없다")
    if view.get("headRefOid") != r.st.finish["merge_head"]:
        raise git.GitError("병합된 PR head가 검증한 integration과 다르다")
    _clear_error(r)
    _save(r, merge_sha=sha, phase="merged", outcome=f"PR 병합 확인, {r.base} 검증 대기")
    return True


def _side_merge(r, url: str, sha: str) -> None:
    """gs가 base에 넣을 커밋 sha 하나짜리 PR을 이 마무리의 병합 방식으로 병합한다. squash 커밋도 sha의 메시지를 쓴다
    (revert의 `This reverts commit <병합>` 줄이 base에 남아 merge_base가 알아본다)."""
    if (r.st.finish.get("merge_method") or r.cfg.git.merge_method) == "squash":
        subject = git.out(r.repo, "log", "-1", "--format=%s", sha)
        body = git.out(r.repo, "log", "-1", "--format=%b", sha)
        _gh(r, "merge", url, "--squash", "--match-head-commit", sha, "--subject", subject, "--body", body)
    else:
        _gh(r, "merge", url, "--merge", "--match-head-commit", sha)


def _find_side_pr(r, branch: str, sha: str) -> str:
    """branch의 열린 PR. 없으면 이 sha로 이미 병합된 PR(지난 생성 응답을 못 받은 PR을 사람이 병합했을 수 있다)."""
    return (_gh(r, "list", "--head", branch, "--base", r.base, "--state", "open", "--json", "url", "--jq", ".[0].url")
            or _gh(r, "list", "--head", branch, "--base", r.base, "--state", "merged", "--json", "url,headRefOid",
                   "--jq", f'[.[] | select(.headRefOid == "{sha}")][0].url // ""'))


def _side_pr(r, kind: str, sha: str, title: str, body: str) -> bool:
    """보호된 base(direct_push = false)에 넣을 gs 커밋 sha를 `gs/<f>/<kind>` PR로 올려 병합을 시도한다.

    병합을 확인하면 True(`<kind>_merge`에 병합 커밋). 승인·검사 등에 막히면 PR을 열어 둔 채 phase
    `<kind>_pending`과 outcome을 남기고 False. 지난 실행이 연 같은 head의 PR은 다시 읽는다(병합됐으면 이어 간다).
    사람이 닫았으면 base에 넣어야 하는 커밋이라 다시 연다. base에는 아무것도 push하지 않는다.

    브랜치를 올린 뒤에는 PR 생성 응답이 실패하거나 비어도 GitHub에는 PR이 생겼을 수 있다. `<kind>_pr`을 모르는 채
    `<kind>_pending`으로 멈추고, 다음 실행이 이 브랜치의 PR을 찾아 이어 간다."""
    f = r.st.finish
    branch = f"gs/{r.name}/{kind}"
    url = f.get(f"{kind}_pr") if f.get(f"{kind}_head") == sha else None
    view = _view(r, url) if url else {}
    if view.get("state") not in ("OPEN", "MERGED"):
        # gs 전용 브랜치라 덮어쓴다(옛 시도의 커밋). base 브랜치가 아니다.
        git.push(r.repo, r.remote, r.st.push_record, f"{sha}:refs/heads/{branch}", flags=("--force",))
        f.pop(f"{kind}_pr", None)  # 옛 시도의 PR이다
        # 여기서 끊겨도(오류·중단) 다음 gs go가 이 phase로 재개해 브랜치의 PR을 찾는다.
        _save(r, phase=f"{kind}_pending", outcome=f"{kind} PR 확인 대기: {branch}", **{f"{kind}_head": sha})
        try:
            url = _find_side_pr(r, branch, sha)
            if not url:
                created = _gh(r, "create", "--base", r.base, "--head", branch, "--title", title, "--body", body)
                url = created.splitlines()[-1] if created else ""
            if not url:
                raise git.GitError(f"{branch} PR URL이 비었다")
        except (git.GitError, OSError) as e:
            _save(r, error=str(e), outcome=f"{kind} PR 확인 실패: {branch} ({e})")
            print(f"■ 경고: {kind} PR을 확인하지 못했다. 다음 gs go가 {branch}의 PR을 찾는다: {e}", flush=True)
            return False
        _save(r, **{f"{kind}_pr": url})
        print(f"■ {r.base}에 직접 push하지 않는다: {kind} PR {url}", flush=True)
        view = _view(r, url)
    refused = ""
    if view.get("state") == "OPEN":
        if r.cfg.git.wait_checks:
            status, names = _poll_checks(r, url, sha, lambda c: _save(r, **{f"{kind}_checks": c}))
            if status != "pass":
                _save(r, phase=f"{kind}_pending", outcome=f"{kind} PR {_checks_outcome(status, names)}: {url}")
                return False
        try:
            _side_merge(r, url, sha)
        except git.GitError as e:
            refused = str(e)
            _save(r, error=refused)
        view = _view(r, url)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
    if view.get("state") != "MERGED":
        why = "사람 승인 필요" if _needs_human(view, refused) else f"{kind} PR 병합 대기"
        _save(r, phase=f"{kind}_pending", outcome=f"{why}: {url}")
        return False
    commit = view.get("mergeCommit")
    oid = commit.get("oid", "") if isinstance(commit, dict) else ""
    if (not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40,64}", oid) or view.get("baseRefName") != r.base
            or view.get("headRefOid") != sha):
        raise git.GitError(f"병합된 {kind} PR {url}의 {r.base} 대상·head·병합 커밋을 확인할 수 없다")
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    if not _ancestor(r.repo, oid, r.base_ref):
        raise git.GitError(f"{kind} PR {url}의 병합 커밋 {oid}가 {r.base_ref}에 없다")
    _clear_error(r)
    _save(r, **{f"{kind}_merge": oid})
    return True


def _revert_pr(r, sha: str) -> bool:
    """revert sha를 PR로 base에 넣는다. revert 경로라 늘 False(_postmerge와 같다)."""
    f = r.st.finish
    body = (f"gs: {r.base} 검증이 실패해 PR {f.get('url', '')}의 병합 커밋 {f['merge_sha']}를 되돌린다.\n\n"
            f"{git.out(r.repo, 'log', '-1', '--format=%B', sha)}")
    if _side_pr(r, "revert", sha, f"{r.name}: {r.base} 검증 실패 → 병합 되돌림", body):
        _save(r, phase="reverted",
              outcome=f"{r.base} 검증 실패 → revert {sha}를 PR {f['revert_pr']}로 {r.base}에 병합함")
    return False


def _read_revert_pr(r, head: str) -> dict:
    """지난 실행이 head로 올린 revert 브랜치의 PR을 읽는다. url을 모르면 브랜치에서 찾아 남긴다. 없으면 빈 dict."""
    url = r.st.finish.get("revert_pr") or _find_side_pr(r, f"gs/{r.name}/revert", head)
    if not url:
        return {}
    _save(r, revert_pr=url)
    return _view(r, url)


def _reread_revert_pr(r, view: dict) -> bool:
    """지난 실행이 올린 revert PR로 이어 간다. 브랜치를 올리고 revert_head를 남기기 전에 끊긴 뒤 병합됐으면 PR head가 revert_sha다."""
    f = r.st.finish
    sha = f.get("revert_sha")
    head = sha if sha and view.get("headRefOid") == sha else f["revert_head"]
    _save(r, revert_sha=head, revert_head=head)
    return _revert_pr(r, head)


def _close_revert_pr(r) -> bool:
    """재검증을 통과해 쓰지 않는 revert PR을 닫고 `gs/<f>/revert` 원격 브랜치를 지운 뒤 verified로 끝낸다.

    부르기 전에 phase `revert_closing`을 남긴다. 끊기거나 실패하면 다음 gs go가 재검증 없이 여기로 돌아온다. 할 일은 PR·브랜치의 지금
    상태를 읽어 정하므로 같은 PR을 두 번 닫지 않는다. 재검증 도중이나 닫기를 기다리는 동안 사람이 병합했으면 그 PR로 reverted다.
    실패하면 phase 그대로 False다. 이 phase에서는 PR을 병합하지 않는다."""
    f = r.st.finish
    head, branch = f["revert_head"], f"gs/{r.name}/revert"
    closed = False
    try:
        view = _read_revert_pr(r, head)
        if view.get("state") != "MERGED":
            if view.get("state") == "OPEN":
                _gh(r, "close", f["revert_pr"], "--comment", f"gs: 최신 {r.base} 재검증을 통과해 되돌리지 않는다.")
                print(f"■ 최신 {r.base} 재검증 통과: revert PR {f['revert_pr']}을 닫았다", flush=True)
            closed = True
            git.check_push(r.repo, r.remote, r.st.push_record)  # 실행 시작 때와 다른 주소에는 묻지도 지우지도 않는다
            if git.out(r.repo, "ls-remote", "--heads", r.remote, f"refs/heads/{branch}"):
                git.push(r.repo, r.remote, r.st.push_record, "--delete", branch)
    except git.PushSettingsChanged:
        raise
    except (git.GitError, OSError) as e:
        where = f.get("revert_pr") or branch
        _save(r, error=str(e), outcome=f"최신 {r.base} 재검증 통과, " + (
            f"revert PR은 닫혔지만 {branch}를 지우지 못했다. 다음 gs go가 다시 지운다: {e}" if closed else
            f"revert PR {where}을 닫지 못했다(열린 채 남음, 병합하지 않음). 다음 gs go가 다시 닫는다: {e}"))
        print(f"■ 경고: {f['outcome']}", flush=True)
        return False
    if view.get("state") == "MERGED":
        return _reread_revert_pr(r, view)
    url = f.get("revert_pr", "")
    number = url.rstrip("/").rsplit("/", 1)[-1]
    f.pop("revert_sha", None)
    f.pop("revert_head", None)
    _save(r, phase="verified", outcome=f"{r.base} 검증 실패 뒤 {r.base}가 바뀌었고 최신 {r.base} 재검증 통과 → revert하지 않음, "
          + (f"revert PR #{number} 닫힘" if url else "닫을 revert PR 없음") + f"(쓰지 않은 revert {head})")
    return True


def _prepare_base(r, wt: Path) -> str | None:
    """임시 base worktree를 준비하고 검증할 끝 커밋을 돌려준다. setup이 실패하면 None(끝 커밋을 읽지 않는다)."""
    if r.cfg.worktree.setup.strip():
        r.st.phase = "setup"
        r.save()
        try:
            print(f"■ {r.base} 준비 중", flush=True)
            prepared = setup.run(r.cfg, wt, r.rundir / "finish" / "setup.log").ok
        finally:
            r.st.phase = "finish"
            r.save()
        if not prepared:
            return None
        setup.remember(wt)
    return git.sha(wt, "HEAD")


def _code_same(r) -> bool:
    """마지막으로 통과한 integration 커밋과 병합 커밋의 차이가 `.goldstack/`뿐인가. 그 커밋을 모르거나(옛 state) 못 읽으면 아니라고 본다."""
    f = r.st.finish
    passed = f.get("verified_head")
    if not passed:
        return False
    res = git.run(r.repo, "diff", "--no-renames", "--name-only", "-z", passed, f["merge_sha"], check=False)
    return res.returncode == 0 and all(path.startswith(".goldstack/") for path in res.stdout.split("\0") if path)


def _same_as_verified(r, tip: str) -> bool:
    """받아 온 base 끝 tip이 병합 커밋 그대로이고, 마지막으로 통과한 integration 커밋과 병합 커밋의 차이가 보고서·이 feature의 아이디어 파일뿐인가.

    그러면 첫 base 검증은 integration에서 통과한 코드를 다시 돌리는 것이다(`revert_decision.SKIP_MAIN`). `.goldstack/` 전체를 허용하는
    `_code_same`보다 좁다: config 같은 다른 `.goldstack/` 파일이 달라도 검증한다. 그 커밋을 모르거나(옛 state) 못 읽으면 아니라고 본다."""
    f = r.st.finish
    passed, merge = f.get("verified_head"), f["merge_sha"]
    if not passed or tip != merge:
        return False
    res = git.run(r.repo, "diff", "--no-renames", "--name-only", "-z", passed, merge, check=False)
    return res.returncode == 0 and set(res.stdout.split("\0")) - {""} <= _report_paths(r)


@metrics.stage("postmerge")
def _postmerge(r) -> bool:
    """사실을 읽어 `revert_decision.next_step`에 묻고 답한 단계를 실행한다. 판단 규칙은 그 함수에 있다.

    재시도를 남겼으면(`MARK_RETRY`) 처음부터 한 번 더 읽는다. 다음 `gs go`가 잇는 길과 같아 같은 준비 절차로 돌고, 첫 검증이 도는 동안 움직인 base와 남이 한 revert도 본다.
    `next_step`은 phase `main_retry`에서 다시 `MARK_RETRY`를 답하지 않는다.
    첫 검증 차례에 base가 integration에서 통과한 코드 그대로면(`SKIP_MAIN`) 검증하지 않고 `main-verify.log`에 건너뜀을 남긴 뒤 verified다."""
    done = _read_and_step(r)
    return _read_and_step(r) if done is None else done


def _read_and_step(r) -> bool | None:
    """`_postmerge`의 한 번. 재시도를 남겼고 아직 돌리지 않았으면 None."""
    f = r.st.finish
    sha, pushed = f.get("revert_sha"), f.get("revert_head")
    facts = revert_decision.Facts(phase=f["phase"], direct_push=r.cfg.git.direct_push, has_revert=bool(sha),
                                  revert_head_matches=pushed == sha, revert_pushed=bool(pushed),
                                  checked_before=bool(f.get("main_head")))
    step = revert_decision.next_step(facts)
    if step == revert_decision.ALREADY_VERIFIED:
        return True
    if step == revert_decision.ALREADY_REVERTED:
        return False
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    merge = f["merge_sha"]
    if not _ancestor(r.repo, merge, r.base_ref):
        raise git.GitError(f"병합 커밋 {merge}가 {r.base_ref}에 없다")
    _check_merge(r)
    tip = git.sha(r.repo, r.base_ref)
    theirs = _revert_of(r.repo, merge, f"{merge}..{r.base_ref}")
    facts = replace(facts, revert_in_base=bool(sha) and _ancestor(r.repo, sha, r.base_ref), external_revert=bool(theirs),
                    base_moved=f.get("main_head") != tip, same_as_verified=_same_as_verified(r, tip))
    step = revert_decision.next_step(facts)
    view = {}
    if step == revert_decision.READ_REVERT_PR:
        view = _read_revert_pr(r, pushed)
        facts = replace(facts, revert_pr_merged=view.get("state") == "MERGED")
        step = revert_decision.next_step(facts)
    if step == revert_decision.READ_REVERT_PARENT:
        facts = replace(facts, revert_parent_is_tip=git.sha(r.repo, f"{sha}^") == tip)
        step = revert_decision.next_step(facts)
    if step == revert_decision.CLOSE_REVERT_PR:
        return _close_revert_pr(r)
    if step == revert_decision.REREAD_REVERT_PR:
        return _reread_revert_pr(r, view)
    if step == revert_decision.OPEN_REVERT_PR:
        return _revert_pr(r, sha)
    if step == revert_decision.RECORD_PUSHED_REVERT:
        _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
        return False
    if step == revert_decision.RECORD_EXTERNAL_REVERT:
        # 이 revert를 report가 revert PR의 커밋으로 적지 않게 PR 기록을 비운다. 이미 되돌렸으니 재검증도 닫기도 없이 끝낸다.
        unused = f.pop("revert_pr", None) or (f"gs/{r.name}/revert" if pushed else "")
        f.pop("revert_head", None)
        _save(r, phase="reverted", revert_sha=theirs,
              outcome=f"{r.base}에서 이미 병합 커밋을 되돌렸다(revert {theirs}, gs가 아닌 다른 곳). gs는 revert를 push하지 않음"
              + (f". 쓰지 않은 revert PR {unused}은 닫지 않았다. 사람이 닫아라" if unused else ""))
        return False
    if step == revert_decision.PUSH_REVERT:
        git.push(r.repo, r.remote, r.st.push_record, f"{sha}:refs/heads/{r.base}")
        _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
        return False
    with tempfile.TemporaryDirectory(prefix="gs-main-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), tip)
        try:
            main_head = _prepare_base(r, wt)
            # 받아 온 끝이 이미 움직였으면 재검증한다. setup이 HEAD를 옮겨도 "그대로"로 되돌리지 않는다.
            facts = replace(facts, base_ready=main_head is not None,
                            base_moved=facts.base_moved or f.get("main_head") != main_head)
            step = revert_decision.next_step(facts)
            if step == revert_decision.KEEP_RETRY:
                _save(r, outcome="base 미검증(준비 실패)")
                return False
            if step == revert_decision.RECORD_UNVERIFIED:
                _save(r, phase="base_unverified", main_ok=None, outcome="base 미검증(준비 실패)")
                return False
            if step == revert_decision.SKIP_MAIN:
                # 통과한 integration과 같은 코드다. 검증한 것처럼 남긴다(main_ok·main_head·outcome이 통과 때와 같다).
                message = f"integration과 같은 코드({f['verified_head']}), 건너뜀"
                (r.rundir / "finish" / "main-verify.log").write_text(message + "\n", encoding="utf-8")
                print(f"■ main 검증: {message}", flush=True)
                _save(r, main_ok=True, main_head=main_head, phase="verified", outcome=f"integration·{r.base} 검증 통과, PR 병합 완료")
                return True
            label = {revert_decision.VERIFY_MAIN: "main", revert_decision.RETRY_MAIN: "main-retry",
                     revert_decision.RECHECK_MAIN: "main-recheck"}.get(step)
            ok = bool(label) and _verify(r, wt, label)
            step = revert_decision.next_step(replace(facts, main_ok=ok, code_same=not ok and _code_same(r)))
            # 결과와 다음 phase를 한 번에 저장한다. main_head만 남기고 끊기면 다음 실행이 base가 그대로라고 믿고 옛 revert를 병합한다.
            if step == revert_decision.MARK_RETRY:
                _save(r, main_ok=ok, main_head=main_head, phase="main_retry", outcome=f"{r.base} 검증 실패, 코드가 같아 다시 검증 중")
                return None
            if step == revert_decision.RECORD_FLAKY:
                _save(r, main_ok=ok, main_head=main_head, phase="verified",
                      outcome=f"integration·{r.base} 검증 통과, PR 병합 완료. flaky: main 재시도 1번 만에 통과")
                return True
            if step == revert_decision.CLOSE_REVERT_PR:
                _save(r, main_ok=ok, main_head=main_head, phase="revert_closing",
                      outcome=f"최신 {r.base} 재검증 통과, revert PR 닫는 중")
                return _close_revert_pr(r)
            if step == revert_decision.RECORD_VERIFIED:
                stale = f.pop("revert_sha", None)
                _save(r, main_ok=ok, main_head=main_head, phase="verified",
                      outcome=f"integration·{r.base} 검증 통과, PR 병합 완료" if not stale else
                      f"{r.base} 검증 실패 뒤 {r.base}가 바뀌었고 최신 {r.base} 검증 통과 → revert하지 않음(쓰지 않은 revert {stale})")
                return True
            f.pop("revert_sha", None)  # 옛 base 위에 만든 revert는 쓰지 않는다
            _save(r, main_ok=ok, main_head=main_head, phase="main_failed", outcome=f"{r.base} 검증 실패, 병합 커밋 revert 중")
            # 검증이 파일·HEAD를 바꿨더라도 받아 온 base의 정확한 끝에서 revert한다.
            git.run(wt, "checkout", "--detach", "--force", main_head)
            git.run(wt, "clean", "-fd")
            # merge는 첫 부모(base)를 유지(-m 1), squash 커밋은 부모가 하나라 -m 없이 그 커밋 하나를 되돌린다.
            parents = git.out(wt, "rev-list", "--parents", "-n", "1", merge).split()[1:]
            git.run(wt, "revert", "--no-edit", *(["-m", "1"] if len(parents) > 1 else []), merge)
            sha = git.sha(wt, "HEAD")
            _save(r, revert_sha=sha)  # push 실패·중단 때 재사용할 커밋
            if step == revert_decision.MAKE_REVERT_PR:
                if pushed:
                    # 맨 앞에서 읽은 뒤 setup·재검증이 도는 동안 사람이 옛 PR을 병합했을 수 있다. 브랜치를 덮어쓰면 그 병합을 놓치고 두 번째 revert PR을 연다.
                    view = _read_revert_pr(r, pushed)
                    step = revert_decision.next_step(replace(facts, main_ok=ok, revert_pr_merged=view.get("state") == "MERGED"))
                if step == revert_decision.REREAD_REVERT_PR:
                    return _reread_revert_pr(r, view)
                return _revert_pr(r, sha)
            # 절대로 force하지 않는다. 거부되면(base가 움직임) 다음 실행이 최신 base 위에서 다시 만든다.
            git.push(wt, r.remote, r.st.push_record, f"HEAD:refs/heads/{r.base}")
            _save(r, phase="reverted", outcome=f"{r.base} 검증 실패 → revert {sha}를 {r.base}에 push함")
            return False
        finally:
            git.remove_worktree(r.repo, wt)


def _update(r, summary: str) -> None:
    path = _commit_report(r, summary)
    _save(r, head=git.sha(r.iwt, "HEAD"))
    _push(r)
    if r.st.finish.get("url"):
        _gh(r, "edit", r.st.finish["url"], "--body-file", str(_pr_body(r, path).resolve()))


def _report_commit(r, rel: str, text: bytes, *, push: bool = True) -> str:
    """원격 base의 최신 끝 위에 report.md를 바꾸고 base에 없는 아이디어 파일을 더한 커밋을 만들어 일반 push한다
    (push=False면 만들기만). base에 이미 같으면 빈 문자열."""
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    with tempfile.TemporaryDirectory(prefix="gs-report-", dir=r.rundir) as tmp:
        wt = Path(tmp) / "base"
        git.run(r.repo, "worktree", "add", "--detach", str(wt), r.base_ref)
        try:
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text)
            rels = [rel, *findings.copy_to_base(r, wt)]
            git.run(wt, "add", "--", rel)
            if git.run(wt, "diff", "--cached", "--quiet", "--", *rels, check=False).returncode == 0:
                return ""
            git.run(wt, "commit", "-q", "-m", f"gs: {r.name} 최종 보고서(병합 후)", "--only", "--", *rels)
            if push:
                # 절대로 force하지 않는다. 거부되면(base가 움직임) 부른 쪽이 최신 base 위에서 다시 만든다.
                git.push(wt, r.remote, r.st.push_record, f"HEAD:refs/heads/{r.base}")
            return git.sha(wt, "HEAD")
        finally:
            git.remove_worktree(r.repo, wt)


@metrics.stage("report-to-base")
def _report_to_base(r) -> None:
    """integration의 최종 report.md를 base에도 남긴다. 거부되면 최신 base 위에서 한 번 더.
    그래도 실패하면 경고뿐이다(실행 결과·종료 코드는 그대로, 다음 gs go도 재시도하지 않는다).
    시도를 마치면 base_report_tried를 남긴다. 그 전에 끊긴 실행은 다음 재개가 처음으로 시도한다."""
    rel = f"{WORK}/{r.name}/report.md"
    if not r.cfg.git.direct_push:
        _report_pr(r, rel)
        return
    error: Exception | None = None
    for _ in range(2):
        try:
            sha = _report_commit(r, rel, (r.iwt / rel).read_bytes())
        except git.PushSettingsChanged:
            raise  # 시도한 것으로 남기지 않는다. 되돌린 뒤 다음 gs go가 처음으로 시도한다
        except Exception as e:  # noqa: BLE001 — 보고서 push는 최선. 병합·검증 결과를 바꾸지 않는다
            error = e
            continue
        _save(r, base_report_tried=True, **({"base_report": sha} if sha else {}))
        if sha:
            print(f"■ 최종 보고서를 {r.base}에 push했다({sha[:8]})", flush=True)
        return
    _save(r, base_report_tried=True)
    print(f"■ 경고: 최종 보고서를 {r.base}에 push하지 못했다(두 번 시도). 실행 결과는 그대로다: {error}", flush=True)


def _report_side_pr(r, sha: str) -> None:
    """보고서 커밋 sha를 PR로 base에 넣는다. 병합되면 기다리던 phase(verified·reverted)와 outcome으로 돌아간다."""
    f = r.st.finish
    body = f"gs: {r.name} 마무리 뒤 최종 보고서 `{WORK}/{r.name}/report.md`를 {r.base}에 남긴다(PR {f.get('url', '')})."
    if not _side_pr(r, "report", sha, f"gs: {r.name} 최종 보고서(병합 후)", body):
        return
    result = f.pop("report_result", {})
    _save(r, phase=result.get("phase", f["phase"]), outcome=result.get("outcome", f.get("outcome", "")),
          base_report_tried=True, base_report=sha)
    print(f"■ 최종 보고서를 PR {f['report_pr']}로 {r.base}에 병합했다({sha[:8]})", flush=True)


def _report_pr(r, rel: str) -> None:
    """보호된 base: 최종 report.md를 `gs/<f>/report` PR로 올린다. 승인에 막히면 phase report_pending으로 멈춘다.
    브랜치를 올리기 전 오류는 direct push 때처럼 경고뿐이다(base_report_tried). 올린 뒤 오류(PR 생성 응답·검사·병합
    조회 등)는 미병합 PR이 남았을 수 있으니 report_pending으로 멈춰 다음 gs go가 그 PR을 찾아 다시 읽게 한다."""
    f = r.st.finish
    sha = ""
    try:
        sha = _report_commit(r, rel, (r.iwt / rel).read_bytes(), push=False)
        if not sha:
            _save(r, base_report_tried=True)
            return
        _save(r, report_result={"phase": f["phase"], "outcome": f.get("outcome", "")})
        _report_side_pr(r, sha)
    except git.PushSettingsChanged:
        raise  # 시도한 것으로 남기지 않는다. 되돌린 뒤 다음 gs go가 처음으로 시도한다
    except Exception as e:  # noqa: BLE001 — 보고서는 최선. 병합·검증 결과를 바꾸지 않는다
        if sha and f.get("report_head") == sha and "report_result" in f:  # report_head는 브랜치를 올린 뒤에 남긴다
            # report_result는 남긴다. 다음 gs go가 PR 병합을 확인하면 기다리던 phase·outcome으로 돌아간다.
            where = f.get("report_pr") or f"gs/{r.name}/report"
            _save(r, error=str(e), phase="report_pending", outcome=f"report PR 확인 실패: {where} ({e})")
            print(f"■ 경고: 최종 보고서 PR {where}을 확인하지 못했다. 다음 gs go가 다시 읽는다: {e}", flush=True)
            return
        result = f.pop("report_result", {})
        _save(r, base_report_tried=True, phase=result.get("phase", f["phase"]),
              outcome=result.get("outcome", f.get("outcome", "")))
        print(f"■ 경고: 최종 보고서 PR을 {r.base}에 병합하지 못했다. 실행 결과는 그대로다: {e}", flush=True)


@metrics.stage("sync-integration")
def _merge_base_keep_report(r) -> None:
    """base(보고서 커밋 포함)를 integration에 합쳐 push한다. report.md를 다시 쓰지 않아 base판과 어긋나지 않는다."""
    git.run(r.repo, "fetch", "-q", r.remote, r.base)
    merge_base(r)
    _save(r, head=git.sha(r.iwt, "HEAD"))
    _push(r)


def _landed(r, commit: str, prev: dict) -> bool:
    """commit이 base에 들어갔는가. squash로 병합한 PR의 커밋은 base의 조상이 되지 않으니 그 PR head에 들었는지로 본다."""
    if _ancestor(r.repo, commit, r.base_ref):
        return True
    sha, head = prev.get("merge_sha"), prev.get("merge_head")
    return bool(prev.get("merge_method") == "squash" and sha and head and _ancestor(r.repo, commit, head)
                and _ancestor(r.repo, sha, r.base_ref))


@metrics.stage("total")
def run(r, *, cleanup: bool = True) -> tuple[str | None, bool]:
    """마무리 한 번. git 오류는 state에 남기고 그대로 올린다(go.go가 받는다). OSError 등 그 밖의 예외는 `cli.main`까지 가서 내부 예외로 수집된다."""
    try:
        return _run(r, cleanup)
    except git.PushSettingsChanged:
        raise
    except git.GitError as e:
        if not _noted(r, e):
            _note_failure(r, e)
        raise


def _run(r, cleanup: bool) -> tuple[str | None, bool]:
    directory = r.rundir / "finish"
    directory.mkdir(parents=True, exist_ok=True)
    f = r.st.finish
    sync_issues(r)
    # 외부 병합 후 재개. 최종 보고서 갱신 전이면 merge_head가 integration의 끝이다.
    anchor = f.get("head") or f.get("merge_head")
    # 정리 후 integration은 base에서 다시 만들 수 있다. 최종 integration 보고서 커밋은
    # base에 직접 들어가지 않지만, 병합된 PR head(merge)나 squash 커밋(squash)은 base의 조상이라 재개 기준으로 쓸 수 있다.
    if f.get("phase") in BASE_REPORT_PHASES and anchor and not _ancestor(r.iwt, anchor, "HEAD"):
        anchor = next((x for x in (f.get("merge_head"), f.get("merge_sha")) if x and _ancestor(r.iwt, x, "HEAD")),
                      f.get("merge_head"))
    # 새 티켓 병합만 본다(늘 부모가 둘). base에서 합쳐 온 squash 커밋(부모 하나)도 gs-ticket 줄을 갖는다.
    resume = bool(anchor and git.run(r.iwt, "merge-base", "--is-ancestor", anchor, "HEAD", check=False).returncode == 0
                  and not git.ticket_trailers(r.iwt, r.name, f"{anchor}..HEAD", merges_only=True))
    if resume and f.get("phase") == "report_pending":
        # 보고서 PR만 남았다. integration 보고서는 PR에 올린 그대로 둔다(base 보고서의 마무리 줄과 같게).
        try:
            _report_side_pr(r, f["report_head"])
        except git.PushSettingsChanged:
            raise
        except (git.GitError, OSError) as e:
            _note_failure(r, e)  # report_pending 그대로. 다음 gs go가 다시 읽는다
            raise git.GitError(str(e)) from e
        if f["phase"] in PENDING_PHASES:
            return f.get("url"), False
        _merge_base_keep_report(r)
        if cleanup:
            clean.integration(r)
        return f.get("url"), f["phase"] == "verified"
    if resume and f.get("phase") in (*RESUME_PHASES, *BASE_REPORT_PHASES):
        # summarize가 돌려준 것과 같게(파일 끝 줄바꿈 제외). 재개가 보고서를 바꾸면 base의 보고서와 어긋난다.
        summary = (directory / "summary.md").read_text(encoding="utf-8").strip()
    else:
        prev = r.st.finish
        r.st.finish = {}
        f = r.st.finish
        # 아직 base에 들어가지 않은 되살림과 닫힌 이전 PR은 새 PR 보고서에도 남긴다.
        again = [x for x in prev.get("reintroduced", []) if not _landed(r, x["commit"], prev)]
        if again:
            f["reintroduced"] = again
        if prev.get("phase") == "closed":
            f["closed_pr"] = prev.get("url", "")
        f.update({key: prev[key] for key in ("issues", "issues_error") if key in prev})  # issue는 PR이 바뀌어도 같다
        _save(r, phase="preparing", outcome="integration 검증 중")
        ok = _verify(r, r.iwt, "integration")
        verified_head = git.sha(r.iwt, "HEAD") if ok else ""
        _save(r, integration_ok=ok)
        # verify가 남긴 변경은 보고서 커밋에 섞이지 않게 한다(gs 전용 worktree).
        if not ok:
            _restore_integration(r, r.ihead)
        summary = report.summarize(r, review.CallWait(r.st, r.save))
        path = _commit_report(r, summary)
        _push(r)
        _publish(r, path)
        # 통과한 integration에서 보고서 외의 파일도 바뀌었으면 실제 PR head를 다시 검증한다.
        candidate = git.sha(r.iwt, "HEAD")
        final_ok = _verify_final(r, verified_head) if ok else False
        if not final_ok:
            _restore_integration(r, candidate)
        _save(r, integration_ok=final_ok)
        merged = any(r.st.tickets[tid].status == state.MERGED for tid in r.order)
        if not merged or not final_ok:
            if not final_ok:
                _save(r, failed_verify="integration-final" if ok else "integration")
            _save(r, phase="not_merged", outcome="merged 티켓 없음 → 병합 안 함" if not merged else "integration 검증 실패 → 병합 안 함")
            _update(r, summary)
            return f.get("url"), False
        _save(r, merge_head=git.sha(r.iwt, "HEAD"), merge_method=r.cfg.git.merge_method, phase="merge_requested")
    try:
        if f["phase"] in (*CHECK_PHASES, "merge_requested", "merge_pending"):
            # 지난 merge 명령이 응답 전에 끝났을 수도 있어 먼저 읽는다.
            view = _view(r)
            if view.get("state") not in ("MERGED", "CLOSED"):
                if r.cfg.git.wait_checks or f["phase"] in CHECK_PHASES:
                    if not _refresh_check_head(r, view):
                        if f["phase"] == "not_merged":
                            _update(r, summary)  # 티켓 이유가 새 failed_verify를 따르게 보고서를 다시 쓴다
                        return f.get("url"), False
                    if r.cfg.git.wait_checks and not _wait_checks(r):
                        return f.get("url"), False
                refused = ""
                try:
                    _merge_pr(r)
                except git.GitError as e:
                    refused = str(e)
                    _save(r, error=refused)
                view = _view(r)  # 명령 성공/큐 진입을 실제 병합으로 착각하지 않는다
            else:
                refused = ""
            if not _confirm(r, view, refused):
                if f["phase"] != "closed":
                    # 큐에 들어간 head를 보고서 커밋으로 바꾸지 않는다.
                    return f.get("url"), False
        ok = f["phase"] != "closed" and _postmerge(r)
    except git.PushSettingsChanged:
        raise  # _update도 push에서 멈춘다. 보낼 수 없는 보고서 커밋을 만들지 않는다
    except (git.GitError, OSError) as e:
        _note_failure(r, e)
        if f["phase"] not in (*CHECK_PHASES, "merge_requested", "merge_pending"):
            _update(r, summary)
        raise git.GitError(str(e)) from e
    final = f["phase"] in BASE_REPORT_PHASES
    if final:
        _clear_error(r)
    if final and not f.get("base_report_tried"):
        # 지난 실행이 이미 시도했으면 다시 하지 않는다(실패했어도 재시도 없음, spec 2-6). 새 마무리는 finish를 비운다.
        # 보고서를 먼저 쓰고 base에 넣은 뒤 base를 합친다. 양쪽 report.md가 같아 합칠 때도, 다음 PR도 충돌하지 않는다.
        # revert를 되돌리는 일만 그 앞에 한다. 보고서에 그 커밋을 남기고, base에 보고서 커밋이 없어 report.md가 충돌하지 않는다.
        git.run(r.repo, "fetch", "-q", r.remote, r.base)
        _restore_reverts(r)
        sync_issues(r)  # 결과가 정해졌다. 실패도 보고서에 남도록 보고서 앞에서 한다
        _update(r, summary)
        _report_to_base(r)
        if f["phase"] in PENDING_PHASES:
            return f.get("url"), False  # 보고서가 base에 들어간 뒤 다음 gs go가 합친다
        _merge_base_keep_report(r)
    elif final and all(r.st.tickets[tid].status == state.MERGED for tid in r.order):
        _merge_base_keep_report(r)  # 할 일이 없었다. base에 넣은 보고서를 그대로 둔다
    else:
        # base를 포함한 integration에 보고서를 쓴다. 다음 go가 보고서만 다시 병합하지 않는다. 끝난 마무리에
        # 이번 실행의 실패한 티켓이 더해지는 경우도 여기다(integration이 base 보고서 커밋을 품어 충돌하지 않는다).
        git.run(r.repo, "fetch", "-q", r.remote, r.base)
        merge_base(r)
        _update(r, summary)
    if cleanup:
        clean.integration(r)
    return f.get("url"), ok and f["phase"] not in PENDING_PHASES
