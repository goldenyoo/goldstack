---
id: "04"
title: "2차 수정 때 앞서 resolved인 지적도 최종 커밋에서 재확인"
blocked_by: ["01"]
touches: ["src/gs/review.py", "src/gs/go.py", "tests/test_rereview.py", "tests/test_recheck_resolved.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
2차 수정이 1차 수정을 덮어써도 보고서가 그 지적을 "수정됨"으로 세는 일을 막는다.

## 완료 조건
- 2차 수정이 있었던 티켓의 2차 재리뷰는 남은 지적과 함께 앞서 resolved인 지적도 최종 커밋에서 본다. 그 지적을 낸 리뷰어도 부른다.
- 2차 수정 worker가 받는 대상은 그대로다(`fix_targets`). 수정 횟수 상한 2회도 그대로다.
- 다시 본 지적이 고쳐져 있지 않으면 `unresolved`이고, 보고서에 "미해결"로 나온다. 확인하지 못하면(재리뷰 실패, 한도) `unchecked`와 이유로 남고, 보고서에 "수정됨"으로 세지 않는다.
- 2차 수정이 없었던 티켓의 재리뷰 호출 수는 그대로다.
- 옛 `state.json`을 읽어도 깨지지 않는다.
- 시험: 1차에서 A를 고치고 2차에서 A를 되돌린 경우 A가 미해결이다. 되돌리지 않은 경우 수정됨이다. 재리뷰가 실패한 경우 확인 못 함이다. `tests/test_rereview.py`의 "1차 resolved가 유지된다"는 시험을 이 규칙에 맞게 고친다.

## 범위 밖
- 모든 티켓에서 재확인하기(spec §3 1-9).
- 3차 수정.

## 참고
- spec §3 1-9. 아이디어 `.goldstack/ideas/invalidate-stale-review-verdicts.md`.
- 동작을 바꾸면 `review.py`·`go.py`의 docstring도 고친다.
