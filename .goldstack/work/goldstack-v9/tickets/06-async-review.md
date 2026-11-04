---
id: "06"
title: "리뷰를 루프 밖 스레드로, 리뷰 중 자리 비우기"
blocked_by: ["05"]
touches: ["src/gs/go.py", "src/gs/review.py", "src/gs/state.py", "src/gs/metrics.py", "tests/test_async_review.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
한 티켓의 리뷰가 도는 동안에도 `go._loop`가 끝난 worker를 처리하고 새 티켓을 시작하게 한다. v8에서 worker가 끝난 뒤 361초, 166초, 635초를 기다린 세 건은 모두 다른 티켓의 리뷰 구간에서 시작됐다.

## 완료 조건
- 리뷰·판단·재리뷰가 루프 밖 스레드에서 돈다. 그동안 다른 worker 종료가 처리되고 준비된 티켓이 시작된다. 시험은 가짜 리뷰어를 파일 신호로 붙잡아 두고, 그 사이 다른 worker가 처리되는지 시간에 기대지 않고 본다.
- 병합·검증은 지금처럼 루프 안에서 한 번에 하나만 돈다. 두 티켓의 리뷰가 함께 끝나도 integration 병합이 겹치지 않는다.
- 리뷰 중인 티켓은 `max_workers` 자리를 차지하지 않는다. worker는 최대 `max_workers`, 리뷰 중인 티켓도 최대 `max_workers`다. 시험이 있다. 수정 worker는 worker 자리를 쓰고, 자리가 없으면 기다린다.
- `state.json`은 루프 스레드만 고친다. 리뷰 스레드는 결과를 돌려주고 루프가 반영한다.
- 리뷰 스레드의 뜻밖의 오류는 그 티켓의 지금 실패 처리로 간다.
- `중단(네트워크)`, 사람의 중단, 예상 못 한 오류로 루프를 떠나면 돌던 리뷰어의 프로세스 그룹을 끝낸다. 시험이 있다.
- 다음 `gs go`는 끝나지 않은 리뷰를 다시 한다. 옛 `state.json`을 읽어도 깨지지 않는다. 시험이 있다.
- `gs status`와 진행 바가 리뷰 중인 티켓을 그대로 보인다. 처리 대기 측정(`processing_wait_seconds`)의 뜻이 바뀌면 필드 설명을 고친다.
- agy 호출 상한이 동시 리뷰에서도 지켜진다.

## 범위 밖
- 검증을 루프 밖으로(`.goldstack/out-of-scope/async-verify.md`).
- 임계 경로 우선, stacking(`.goldstack/out-of-scope/async-coordinator.md`).

## 참고
- spec §3 1-5, 1-6, 1-7, §6 코디네이터. 스레드 풀 선례는 `review.run_together`.
- 동작을 바꾸면 `go.py`·`review.py` docstring도 고친다. `docs/internals.md`는 티켓 08이 고친다.
