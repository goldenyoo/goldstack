---
id: "01"
title: "빈 재리뷰 diff와 재개 뒤 재리뷰 상한"
blocked_by: []
touches: ["src/gs/go.py", "tests/test_review_target.py", "tests/test_recheck_resolved.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
catch-up 뒤 빈 커밋으로 해결된 지적이 뒤집히지 않게 하고, 재개해도 재리뷰가 합쳐 한 번이라는 규칙을 지킨다.

## 완료 조건
- `resolved` 지적이 있고 catch-up 뒤 `a.base..head`가 비면 그 판정이 유지되고 2차 수정 worker가 뜨지 않는다. 앞서 판정이 없는 지적의 빈 diff 처리는 지금과 같다. 재현 시험이 먼저 실패하고, 고친 뒤 통과하는 것을 worker가 직접 본다.
- `_late_commit`으로 재리뷰로 돌아가는 도중 중단됐다가 재개하면 `_review_again`을 타고 세 번째 리뷰를 부르지 않으며 대조 기록이 남는다. 재현 시험이 있다.
- `reviewed_again`이 없는 옛 state는 False로 읽는다. 시험이 있다.
- docstring을 고친다.

## 범위 밖
- 재리뷰 전용 기준 나누기(범위 밖 `rereview-diff-base`). 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 1-1, 1-2, §6. 아이디어 `goldstack-v15-04-2`, `goldstack-v15-04-5`.
