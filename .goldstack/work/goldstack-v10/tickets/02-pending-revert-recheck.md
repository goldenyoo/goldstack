---
id: "02"
title: "승인 대기 중 base가 바뀌면 재검증, 통과하면 되돌리기 PR 닫기"
blocked_by: ["01"]
touches: ["src/gs/finish.py", "src/gs/revert_decision.py", "tests/test_revert_decision.py", "tests/test_protected_base.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
보호된 base에서 되돌리기 PR이 승인을 기다리는 동안 사람이 base를 고쳤을 때, 다음 `gs go`가 재검증 없이 옛 되돌리기를 병합해 정상 기능을 지우지 않게 한다.

## 완료 조건
- 되돌리기 PR이 이미 병합됐으면 재검증하지 않고 지금처럼 `reverted`로 끝낸다. PR 상태를 base 이동 판단보다 먼저 본다.
- PR이 아직 병합되지 않았고 base 끝이 검증 실패 때의 `main_head`와 같으면 지금처럼 PR을 다시 읽고 기다린다. 재검증하지 않는다.
- PR이 아직 병합되지 않았고 base 끝이 `main_head`와 다르면 최신 base를 `main-recheck`로 재검증한다. 이 재검증 전에 옛 되돌리기를 병합하지 않는다.
- 재검증이 통과하면 gs가 그 PR을 닫고 `gs/<feature>/revert` 원격 브랜치를 지운 뒤 `verified`로 끝낸다. outcome과 보고서에 재검증 통과와 닫은 PR 번호가 나온다. 다음 `gs go`가 그 PR을 다시 열지 않는다.
- 재검증이 실패하면 최신 base 위에 되돌리기를 다시 만들어 PR 브랜치를 갱신한다. 옛 되돌리기 커밋은 쓰지 않는다. 다시 만든 PR이 승인을 기다리면 지금처럼 `revert_pending`으로 멈춘다.
- PR 닫기나 브랜치 삭제가 실패하면 `verified`로 넘어가지 않거나, 넘어가도 열린 PR이 남았다는 사실을 outcome과 보고서에 적는다. 어느 쪽이든 그 PR을 병합하지 않고, 다음 `gs go`가 닫기를 다시 시도한다.
- 각 단계 직후에 gs가 죽어도 다음 `gs go`가 이어 간다. 같은 PR을 두 번 닫거나 되돌리기를 두 번 넣지 않는다.
- `test_protected_base`에 시나리오 시험이 있다: 대기 중 base가 고쳐져 재검증 통과, 대기 중 base가 움직였지만 여전히 실패, base 그대로 대기, 이미 병합됨, 닫기 실패 뒤 재개.
- 01의 전이표 시험에 새 분기가 있다. 직접 push 경로의 동작은 바뀌지 않는다.

## 범위 밖
- 사람이 PR을 닫았고 base가 그대로일 때 다시 여는 지금 동작(유지).
- 재개 판단 분리(범위 밖 `finish-resume-decisions`).
- 문서(07).

## 참고
- spec §3의 1-4, `.goldstack/ideas/pending-revert-recheck-base.md`
