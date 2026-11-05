---
id: "03"
title: "닫힌 issue 재발 확인"
blocked_by: ["02"]
touches: ["src/gs/feedback.py", "tests/test_feedback_send.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
닫힌 issue가 재발했을 때 이전 기록과 잇는다.

## 완료 조건
- `gs feedback`의 재발 확인이 닫힌 issue도 본다. 티켓 02의 `<버전>에서 고침` 댓글을 읽어 고친 버전을 안다.
- 지금 gs가 고친 버전보다 새로우면 그 issue를 다시 열고 횟수 댓글을 단다. 옛 gs면 issue를 건드리지 않고 업데이트를 안내한다. 버전을 모르면 새 issue다.
- `max_per_day`와 가리기가 그대로 적용된다. 시험: 세 경우.

## 범위 밖
- 열린 issue 재발은 지금 그대로다.

## 참고
- spec 2-21
