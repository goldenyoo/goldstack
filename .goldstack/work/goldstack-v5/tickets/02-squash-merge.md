---
id: "02"
title: "squash 병합: tree 비교 확인, 그 커밋 하나 revert, 메시지"
blocked_by: ["01"]
model: claude
reviewer: codex
second_reviewer: agy
touches: ["src/gs/finish.py", "tests/test_squash.py"]
---
## 목표
`git.merge_method = "squash"`인 저장소에서 gs가 PR을 squash로 병합하고, 병합 확인·base 검증·revert·재개가 merge 방식과 같은 안전성으로 동작하게 한다.

## 완료 조건
- squash면 `gh pr merge --squash --match-head-commit <merge_head>`에 제목 `<feature>: gs go (#<PR>)`, 본문에 티켓 목록(`NN 제목`)과 티켓별 `gs-ticket: <f>/NN` 줄(spec 2-2).
- 병합 확인: PR이 MERGED, base가 맞고, `mergeCommit`의 tree가 `merge_head`의 tree와 같다(조상 관계 대신). 다르면 오류로 멈춘다(시험: 같은 tree, 다른 tree).
- base 검증 실패 시 revert: squash 커밋 하나를 `git revert`(`-m` 없이). 이미 누가 되돌렸는지 찾기·되살림(`_undone_reverts`·`_feature_merge`) 판단이 squash 커밋에서도 맞다(시험: 실패 → revert push, 이미 되돌림, 재개).
- 중단 뒤 재개(`merge_requested`·`merge_pending`·`merged`·`main_failed`)가 squash에서도 같은 결과(시험).
- merge 방식의 기존 시험은 그대로 통과(기본값 merge).
- v3의 최종 보고서 base push가 squash 뒤에도 동작한다(시험).

## 범위 밖
- rebase 병합(spec 1-2)
- CI 대기 03, 보호된 base 04

## 참고
- spec §3 1-2, 2-2, §6 병합·revert가 기대는 조상 관계와 trailer
