"""`finish._postmerge`의 되돌리기 판단: 이미 읽은 사실(`Facts`) → 다음 단계 이름(`next_step`).

git·gh·파일·시각을 부르지 않는다. 사실을 읽고 단계를 실행하는 일은 `_postmerge`가 한다.

읽는 데 fetch·worktree가 들거나 읽다가 실패할 수 있는 사실은 값이 `None`(아직 안 읽음)이다. 답이 그 사실에 달렸을 때만
`next_step`이 읽기 단계(`READ_BASE`, `READ_REVERT_PARENT`, `PREPARE_BASE`)로 답하고, `_postmerge`가 읽어 채운 뒤 다시 묻는다.
그래서 끝난 마무리는 fetch하지 않고, 앞 줄에서 답이 나온 revert는 부모를 읽지 않으며, 필요 없던 재검증도 돌지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 끝난 마무리. 아무것도 읽지 않는다.
ALREADY_VERIFIED = "already_verified"
ALREADY_REVERTED = "already_reverted"
# 사실 읽기.
READ_BASE = "read_base"  # fetch, 병합 커밋 확인, revert_in_base, external_revert
READ_REVERT_PARENT = "read_revert_parent"  # revert_parent_is_tip
PREPARE_BASE = "prepare_base"  # 임시 worktree, setup, base_ready, base_moved
# 이미 있는 revert로 끝낸다.
REREAD_REVERT_PR = "reread_revert_pr"  # 지난 실행이 올린 revert 브랜치의 PR을 다시 읽는다
RECORD_PUSHED_REVERT = "record_pushed_revert"  # base에 든 revert를 reverted로 남긴다
RECORD_EXTERNAL_REVERT = "record_external_revert"  # gs가 아닌 누군가의 revert를 reverted로 남긴다
PUSH_REVERT = "push_revert"  # 만들어 둔 revert를 일반 push한다
OPEN_REVERT_PR = "open_revert_pr"  # 만들어 둔 revert를 PR로 올린다
# base를 검증하고 결과를 남긴다.
RECORD_UNVERIFIED = "record_unverified"  # setup 실패: base_unverified, revert하지 않는다
VERIFY_MAIN = "verify_main"  # 검증 로그 main
RECHECK_MAIN = "recheck_main"  # 검증 로그 main-recheck
RECORD_VERIFIED = "record_verified"
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


def next_step(f: Facts) -> str:
    """위에서 아래로 처음 맞는 줄이 답이다. 순서가 곧 우선순위다."""
    if f.phase == "verified":
        return ALREADY_VERIFIED
    if f.phase == "reverted":
        return ALREADY_REVERTED
    if f.revert_in_base is None or f.external_revert is None:
        return READ_BASE
    # 승인 대기, PR 생성 응답 오류, 병합 직후 중단. squash면 revert_sha는 base에 들지 않으니 base 확인보다 먼저 본다.
    if f.has_revert and f.revert_head_matches:
        return REREAD_REVERT_PR
    if f.has_revert and f.revert_in_base:
        return RECORD_PUSHED_REVERT
    # 같은 병합을 두 번 revert하지 않는다.
    if f.external_revert:
        return RECORD_EXTERNAL_REVERT
    if f.has_revert:
        if f.revert_parent_is_tip is None:
            return READ_REVERT_PARENT
        # revert push 직전에 중단됐고 base가 그대로다. 같은 커밋을 쓴다(두 번 revert하지 않는다).
        if f.revert_parent_is_tip:
            return PUSH_REVERT if f.direct_push else OPEN_REVERT_PR
    if f.base_ready is None:
        return PREPARE_BASE
    if not f.base_ready:
        return RECORD_UNVERIFIED
    if f.main_ok is None:
        if f.phase != "main_failed":
            return VERIFY_MAIN
        # 실패 뒤 base가 움직였다(그사이 push로 revert push가 거부됐을 수 있다). 그대로면 지난 실패를 믿고 아래로 간다.
        if f.base_moved:
            return RECHECK_MAIN
    if f.main_ok:
        return RECORD_VERIFIED
    return MAKE_REVERT_PUSH if f.direct_push else MAKE_REVERT_PR
