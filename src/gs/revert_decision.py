"""`finish._postmerge`의 되돌리기 판단: 이미 읽은 사실(`Facts`) → 다음 단계 이름(`next_step`).

git·gh·파일·시각을 부르지 않는다. 사실을 읽고 단계를 실행하는 일은 `_postmerge`가 한다.

읽는 데 fetch·worktree·gh가 들거나 읽다가 실패할 수 있는 사실은 값이 `None`(아직 안 읽음)이다. 답이 그 사실에 달렸을 때만
`next_step`이 읽기 단계(`READ_BASE`, `READ_REVERT_PR`, `READ_REVERT_PARENT`, `PREPARE_BASE`)로 답하고, `_postmerge`가 읽어 채운 뒤
다시 묻는다. 그래서 끝난 마무리는 fetch하지 않고, 앞 줄에서 답이 나온 revert는 부모를 읽지 않으며, 필요 없던 재검증도 돌지 않는다.

revert 브랜치를 올린 적이 있으면(보호된 base) PR 상태를 base 이동보다 먼저 본다. PR 병합이 곧 base 이동이기 때문이다. 병합되지 않았고
base가 그대로면 그 PR을 기다리고, base가 움직였으면 옛 revert를 병합하지 않고 재검증한다. 통과하면 PR을 닫고(phase `revert_closing`이
"재검증 통과, 닫기가 남음"이다), 실패하면 최신 base 위에 revert를 다시 만들어 같은 브랜치를 갱신한다. 직접 push 경로는 브랜치를 올리지 않아 이 줄들을 지나지 않는다.
재검증이 도는 동안 PR이 병합될 수 있어 `_postmerge`는 그 브랜치를 덮어쓰기 직전에 PR을 다시 읽어 묻는다. 병합됐으면 검증 결과와 상관없이 그 PR로 끝난다.

첫 검증이 실패했고 코드가 같으면(`code_same`) revert 전에 한 번 다시 돌린다. `MARK_RETRY`가 phase `main_retry`("첫 실패, 재시도가 남음")를 남기고, 그 phase가 곧 "이미
재시도를 썼다"는 표시다: 재시도와 재검증의 실패는 다시 묻지 않고 revert로 간다. 끊긴 실행을 잇는 다음 `gs go`도 같은 줄을 지나므로 남이 한 revert를 먼저 보고 revert를 두 번 만들지 않는다.
실패 뒤 base가 움직였으면 같은 코드의 재시도가 아니라 재검증이고, 통과해도 flaky로 적지 않는다.

첫 검증(`VERIFY_MAIN`)을 고를 자리에서 받아 온 base 끝이 병합 커밋 그대로이고 `verified_head`와 병합 커밋의 차이가 보고서·이 feature의
아이디어 파일뿐이면(`same_as_verified`) 검증하지 않고 `SKIP_MAIN`으로 integration의 통과를 그대로 쓴다. 이 자리에서만이다: 재시도·재검증,
phase `main_failed`·`main_retry`·`revert_pending`, revert가 있거나 브랜치를 올린 상태, 외부 revert는 위 줄이 먼저 답하거나 이 줄에 오지 않는다.
`main_failed`에서 준비가 실패해 phase가 `base_unverified`로 바뀌었어도 남은 `main_head`(`checked_before`)로 알아보고 건너뛰지 않는다.
이미 확인한 실패를 덮지 않는다. `.goldstack/` 전체를 보는 `code_same`(재시도 판단)과 다른 기준이다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 끝난 마무리. 아무것도 읽지 않는다.
ALREADY_VERIFIED = "already_verified"
ALREADY_REVERTED = "already_reverted"
# 사실 읽기.
READ_BASE = "read_base"  # fetch, 병합 커밋 확인, revert_in_base, external_revert, base_moved(받아 온 끝 기준)
READ_REVERT_PR = "read_revert_pr"  # revert_pr_merged
READ_REVERT_PARENT = "read_revert_parent"  # revert_parent_is_tip
PREPARE_BASE = "prepare_base"  # 임시 worktree, setup, base_ready, base_moved(검증할 커밋 기준)
# 이미 있는 revert로 끝낸다.
REREAD_REVERT_PR = "reread_revert_pr"  # 지난 실행이 올린 revert 브랜치의 PR을 다시 읽는다
RECORD_PUSHED_REVERT = "record_pushed_revert"  # base에 든 revert를 reverted로 남긴다
RECORD_EXTERNAL_REVERT = "record_external_revert"  # gs가 아닌 누군가의 revert를 reverted로 남긴다
PUSH_REVERT = "push_revert"  # 만들어 둔 revert를 일반 push한다
OPEN_REVERT_PR = "open_revert_pr"  # 만들어 둔 revert를 PR로 올린다
# base를 검증하고 결과를 남긴다.
RECORD_UNVERIFIED = "record_unverified"  # setup 실패: base_unverified, revert하지 않는다
KEEP_RETRY = "keep_retry"  # 재시도의 setup 실패: phase main_retry를 그대로 두고 revert하지 않는다
VERIFY_MAIN = "verify_main"  # 검증 로그 main
SKIP_MAIN = "skip_main"  # integration에서 검증한 코드 그대로: 검증하지 않고 로그 main에 건너뜀을 남긴 뒤 verified
RETRY_MAIN = "retry_main"  # 검증 로그 main-retry
RECHECK_MAIN = "recheck_main"  # 검증 로그 main-recheck
MARK_RETRY = "mark_retry"  # 코드가 같은 첫 실패: phase main_retry를 남기고 worktree를 치운 뒤 처음부터 다시 읽는다
RECORD_VERIFIED = "record_verified"
RECORD_FLAKY = "record_flaky"  # 재시도 통과: verified, outcome에 flaky 표시
CLOSE_REVERT_PR = "close_revert_pr"  # 재검증을 통과해 쓰지 않는 revert PR을 닫고 브랜치를 지운 뒤 verified로 끝낸다
MAKE_REVERT_PUSH = "make_revert_push"  # base 끝 위에 revert를 새로 만들어 일반 push한다
MAKE_REVERT_PR = "make_revert_pr"  # base 끝 위에 revert를 새로 만들어 PR로 올린다


@dataclass(frozen=True)
class Facts:
    phase: str  # finish의 phase
    direct_push: bool  # git.direct_push
    has_revert: bool  # revert_sha가 있다
    revert_head_matches: bool  # revert_head가 revert_sha와 같다: 그 커밋으로 revert 브랜치를 올린 적이 있다
    revert_in_base: bool | None = None  # revert_sha가 원격 base의 조상이다
    external_revert: bool | None = None  # 병합 커밋 뒤 base에 그 병합을 되돌린 커밋이 있다
    revert_parent_is_tip: bool | None = None  # revert_sha의 부모가 원격 base의 끝이다
    base_ready: bool | None = None  # 임시 worktree의 setup이 통과했다(setup이 없으면 True)
    base_moved: bool = True  # 지난 main_head와 지금 base 끝이 다르다. 모르면 다시 검증한다
    main_ok: bool | None = None  # 이번에 돈 base 검증의 결과. 돌리지 않았으면 None
    revert_pushed: bool = False  # revert_head가 있다: revert 브랜치를 올린 적이 있어 그 PR이 남았을 수 있다
    revert_pr_merged: bool | None = None  # 그 PR이 이미 병합됐다
    code_same: bool = False  # 마지막으로 통과한 integration 커밋과 병합 커밋의 차이가 `.goldstack/`뿐이다. 모르면(옛 state, 못 읽음) 지금처럼 revert한다
    # 받아 온 base 끝이 병합 커밋 그대로이고 마지막으로 통과한 integration 커밋(`verified_head`)과 병합 커밋의 차이가 보고서·이 feature의
    # 아이디어 파일뿐이다. 모르면(옛 state, 못 읽음) 지금처럼 검증한다
    same_as_verified: bool = False
    # 지난 실행이 base 검증 결과를 남겼다(state에 main_head가 있다). 건너뛸 수 있는 phase에서는 곧 확인한 실패다: 통과는 verified·revert_closing으로
    # 가고, 준비 실패(`RECORD_UNVERIFIED`)는 phase를 base_unverified로 바꾸지만 main_head는 지우지 않는다
    checked_before: bool = False


def next_step(f: Facts) -> str:
    """위에서 아래로 처음 맞는 줄이 답이다. 순서가 곧 우선순위다."""
    if f.phase == "verified":
        return ALREADY_VERIFIED
    if f.phase == "reverted":
        return ALREADY_REVERTED
    if f.revert_in_base is None or f.external_revert is None:
        return READ_BASE
    if f.revert_pushed:
        if f.revert_pr_merged is None:
            return READ_REVERT_PR
        # 병합 직후 중단 포함. 그 병합이 base를 옮겼으니 재검증하지 않는다. squash면 revert_sha는 base에 들지 않으니 base 확인보다 먼저 본다.
        if f.revert_pr_merged:
            return REREAD_REVERT_PR
    # 재검증은 이미 통과했다. 닫기만 다시 한다.
    if f.phase == "revert_closing":
        return CLOSE_REVERT_PR
    # 승인 대기, PR 생성 응답 오류. base가 그대로면 지난 실패가 아직 맞으니 같은 PR을 기다린다.
    if f.has_revert and f.revert_head_matches and not f.base_moved:
        return REREAD_REVERT_PR
    if f.has_revert and f.revert_in_base:
        return RECORD_PUSHED_REVERT
    # 같은 병합을 두 번 revert하지 않는다.
    if f.external_revert:
        return RECORD_EXTERNAL_REVERT
    # 브랜치를 올렸으면 설정이 직접 push로 바뀌어도 그 PR을 갱신한다. 옛 revert PR을 열린 채 버려 두지 않는다.
    via_pr = not f.direct_push or f.revert_pushed
    if f.has_revert and not f.revert_head_matches:
        if f.revert_parent_is_tip is None:
            return READ_REVERT_PARENT
        # revert push 직전에 중단됐고 base가 그대로다. 같은 커밋을 쓴다(두 번 revert하지 않는다).
        if f.revert_parent_is_tip:
            return OPEN_REVERT_PR if via_pr else PUSH_REVERT
    if f.base_ready is None:
        return PREPARE_BASE
    if not f.base_ready:
        # 재시도의 준비 실패는 재시도를 쓴 것이 아니다. phase를 덮어쓰면 다음 실행이 첫 검증으로 돌아가 flaky 표시를 잃고 재시도를 한 번 더 얻는다.
        return KEEP_RETRY if f.phase == "main_retry" else RECORD_UNVERIFIED
    if f.main_ok is None:
        # 재시도 도중 끊긴 실행도 여기로 온다. 지난 실패와 같은 커밋일 때만 재시도다.
        if f.phase == "main_retry" and not f.base_moved:
            return RETRY_MAIN
        if f.phase not in ("main_failed", "main_retry") and not f.revert_pushed:
            # integration에서 검증한 코드를 다시 돌리지 않는다. 실패를 확인한 적 없고(준비 실패로 phase가 바뀐 지난 실패 포함) revert도 없을 때만이다.
            if (f.same_as_verified and f.phase in ("merged", "base_unverified") and not f.has_revert
                    and not f.checked_before):
                return SKIP_MAIN
            return VERIFY_MAIN
        # 실패 뒤 base가 움직였다(사람이 고쳤거나 그사이 push로 revert push가 거부됐다). 그대로면 지난 실패를 믿고 아래로 간다.
        if f.base_moved:
            return RECHECK_MAIN
    if f.main_ok:
        if f.revert_pushed:
            return CLOSE_REVERT_PR
        return RECORD_FLAKY if f.phase == "main_retry" and not f.base_moved else RECORD_VERIFIED
    # 재시도는 revert를 만들기 전의 첫 실패에만 한 번이다. main_failed·revert가 있으면 이미 revert로 가기로 정한 뒤다.
    if f.code_same and f.phase not in ("main_failed", "main_retry") and not f.has_revert and not f.revert_pushed:
        return MARK_RETRY
    return MAKE_REVERT_PR if via_pr else MAKE_REVERT_PUSH
