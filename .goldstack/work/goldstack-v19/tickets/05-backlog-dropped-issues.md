---
id: "05"
title: "dropped 아이디어의 열린 issue를 후보에 보인다"
blocked_by: []
touches: ["src/gs/backlog.py", "tests/test_backlog.py"]
tier: small
model: codex
reviewer: claude
second_reviewer: agy
---
## 목표
dropped로 바꾼 아이디어에 연결된 열린 issue가 목록에서 사라지지 않게 한다.

## 완료 조건
- 기본 `gs backlog`의 issue 후보에 `#14 (dropped: <slug>)` 모양으로 나온다. taken·open 아이디어에 연결된 번호는 지금처럼 숨긴다.
- `tests/test_backlog.py`를 새 의도로 고친다. 닫힌 issue는 나오지 않는다.

## 범위 밖
- issue를 자동으로 닫지 않는다. 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 1-6, §6. 아이디어 `goldstack-v15-01-1`.
