---
id: "04"
title: "이미 끝남 경로의 issue 실패를 끝 출력에 보인다"
blocked_by: ["01"]
touches: ["src/gs/go.py", "tests/test_issue_close.py"]
tier: small
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
끝난 실행을 다시 돌렸을 때 issue 처리 실패를 사람이 알게 한다.

## 완료 조건
- '이미 끝남' 경로에서 `sync_issues`의 실패가 `■ issue: #12 다시 열기 실패(gh). 다음 gs go가 다시 시도한다` 모양으로 끝 출력에 나온다. 실패가 없으면 줄이 없다. 종료 코드는 그대로다.
- `report.md`와 base는 건드리지 않는다는 시험이 있다.

## 범위 밖
- 보고서 다시 쓰기. 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 1-5, §6. 아이디어 `goldstack-v15-02-2`.
