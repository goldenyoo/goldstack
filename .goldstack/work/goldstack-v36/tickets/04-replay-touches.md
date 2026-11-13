---
id: "04"
title: "gs replay worker brief에도 touches 줄"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/replay.py", "tests/test_brief_rules.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
`gs replay`가 띄우는 첫 구현 worker도 touches 목록과 "touches 밖 파일은 고치지 않는다" 규칙을 받는다(spec 1-11, 아이디어 `goldstack-v35-04-1`).

## 완료 조건
- replay worker brief에 그 티켓의 touches 줄(`TOUCHES_LABEL`)과 금지 문장이 들어간다.
- 수정·수리 worker brief는 지금처럼 touches 줄이 없다.
- replay brief의 base 줄은 지금과 같다(병합 목록을 새로 만들지 않는다).
- `tests/test_brief_rules.py`에 replay 경로 brief의 touches 단언과 수정 brief에 없다는 단언.

## 범위 밖
- replay의 다른 동작

## 참고
- `src/gs/worker.py` 172–175행, `src/gs/replay.py` 571행, `.goldstack/ideas/goldstack-v35-04-1.md`
