---
id: "02"
title: "같은 마무리 오류는 초안 하나로"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_collect.py"]
tier: medium
model: codex
reviewer: claude
second_reviewer: agy
---
## 목표
재개에서 같은 오류가 재발해도 `stuck-phase` 초안이 새로 생기지 않게 한다.

## 완료 조건
- `finish_anomaly`가 이미 수집한 오류가 재발하면 `finish-error`와 같은 초안의 횟수만 올리게 한다. `gs feedback list`에 그 오류의 줄이 하나다.
- 오류 없이 재개 phase에 갇힌 경우는 지금처럼 `stuck-phase`다. 다른 오류면 새 초안이다.
- `test_finish_error_then_stuck_on_the_next_resume`을 새 의도로 고친다. 고친 코드를 되돌리면 실패하는 것을 worker가 직접 보고 마지막 메시지에 적는다.

## 범위 밖
- 재발 키(goldstack-v17). 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 1-3, §6. 아이디어 `goldstack-v14-06-1`.
