---
id: "05"
title: "_finish를 리뷰 전·리뷰·병합 단계로 나누기(동작 그대로)"
blocked_by: ["04"]
touches: ["src/gs/go.py", "tests/test_finish_stages.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
티켓 06이 리뷰만 루프 밖으로 뺄 수 있게, 한 함수에 이어진 `go._finish`를 단계로 나눈다. 이 티켓은 스레드를 넣지 않는다.

## 완료 조건
- worker 결과 확인, 리뷰·재리뷰와 수정 worker 판단, catch-up·병합·검증이 각각 부를 수 있는 함수가 된다. 리뷰 단계는 인자로 받은 값과 결과만 주고받을 수 있게 경계를 드러낸다.
- 기존 시험을 고치지 않고 전체 검증이 통과한다. 동작, 로그 문구, `state.json` 형식이 그대로다.
- 네트워크 중단(`_mark_resume`), 일시 오류 대기(`_net_hold`·`_net_park`), 리뷰한 head를 다시 보는 v8 동작이 그대로다. `tests/test_finish_stages.py`가 단계 경계의 순서를 고정한다.

## 범위 밖
- 스레드, `max_workers` 변경(티켓 06).
- `finish.py`의 판단 분리(`finish-phase-decisions`).

## 참고
- spec §3 1-6, §6 코디네이터. 시작 전에 v8이 병합한 `go.py`를 읽는다. spec §6은 v8 진행 중 코드 기준이다.
