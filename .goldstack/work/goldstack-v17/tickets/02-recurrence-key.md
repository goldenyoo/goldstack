---
id: "02"
title: "버전 없는 재발 키로 이전 issue 찾기"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_format.py", "tests/test_feedback_send.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
새 gs에서 재발한 결함이 이전 issue와 이어지게 한다. 기존 지문은 그대로 둔다.

## 완료 조건
- 재발 키는 단계 + 오류 종류 + `파일:함수`의 해시다. 버전과 줄 번호는 들어가지 않는다. 버전이나 줄 번호만 다르면 키가 같고, 단계·오류 종류·파일·함수 중 하나가 다르면 키가 다르다는 시험이 있다.
- 지문은 지금과 같은 값이다. `test_each_input_changes_the_fingerprint`가 그대로 통과한다.
- issue 본문에 `- 재발 키: <키>` 줄이 있다.
- `send`가 지문으로 찾지 못하면 재발 키로 찾는다. 같은 키의 열린 issue에는 횟수 댓글을 단다. 같은 키의 닫힌 issue는 지금 규칙대로 초안 버전이 고친 버전보다 새로우면 다시 열고 댓글을 달고, 같거나 옛 버전이면 업데이트를 안내한다. 각 경우를 가짜 `gh`로 시험한다.
- 키 줄이 없는 옛 issue는 지금처럼 지문으로만 찾는다.
- 수동 피드백(`record_manual`)은 지금과 같게 동작한다.

## 범위 밖
- 옛 issue에 키를 덧붙이지 않는다. 문서는 티켓 06이 맡는다.

## 참고
- spec §2, 결정 2-4, 2-5, §6. 아이디어 `goldstack-v15-03-1`, `goldstack-v15-03-6`.
