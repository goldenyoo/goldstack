---
id: "15"
title: "gs-ticket 표시를 트레일러 줄로 정확히 비교한다"
blocked_by: ["13"]
touches: ["src/gs/go.py", "src/gs/finish.py", "tests/test_ticket_trailer.py"]
model: codex
reviewer: claude
tier: medium
---
## 목표
재개할 때 실행하지 않은 티켓이 merged가 되는 일을 없앤다.

## 완료 조건
- `go._already_merged`가 부분 문자열 검색 대신 커밋 메시지의 트레일러 줄을 파싱해 feature와 id 전체를 비교한다.
- 시험: `gs-ticket: f/010` 병합 커밋이 있어도 티켓 `01`은 merged가 아니다. 본문 문장에 `gs-ticket: f/02`라고 적은 일반 커밋(병합 커밋 아님)으로 `02`가 merged가 되지 않는다. feature 이름의 접두어가 겹쳐도(`f`와 `f2`) 섞이지 않는다.
- squash 커밋 본문의 `gs-ticket:` 줄은 지금처럼 인식한다. `finish.py`의 같은 검색도 같은 함수를 쓴다. 시험이 있다.
- 기존 재개 시험이 통과한다.

## 범위 밖
- 마무리 판단을 순수 함수로 모으기(`finish-phase-decisions`, v9), 티켓 id 형식 제한.

## 참고
- spec §3 5-1 e. 아이디어 `.goldstack/ideas/exact-ticket-trailer-match.md`(재현 방법).
