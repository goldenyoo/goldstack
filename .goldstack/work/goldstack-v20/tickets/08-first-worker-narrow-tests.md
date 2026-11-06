---
id: "08"
title: "모든 첫 worker가 좁은 시험까지만 돌리고 자기 프로세스만 다룬다"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/go.py", "tests/test_fix_brief.py", "tests/test_ticket_verify.py", "tests/test_sandbox_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
같은 전체 시험을 worker와 gs가 두 번 돌리는 시간을 없애고, 기계를 함께 쓰는 worker끼리 부딪치지 않게 한다.

## 완료 조건
- 계열과 상관없이 첫 worker, 재개한 worker의 brief가 수정·수리 worker와 같은 좁은 시험 규칙을 쓴다. 전체 검증은 gs가 병합 트리에서 돌린다는 문장이 그대로 있다. `write_brief`의 `narrow` 인자와 계열 분기를 없애고 `go.py`의 호출을 고친다.
- 모든 worker brief에 "다른 티켓이 같은 기계에서 함께 돈다. 네가 띄운 프로세스는 그 PID로 기다리고 끝낸다"는 뜻의 문장이 있다.
- 티켓 `verify`가 좁아도 같은 규칙이 나온다. 위 각 경우를 시험한다. `write_brief` docstring을 고친다.

## 범위 밖
- 수정·수리 흐름, 재리뷰 지시. 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 4-1, 4-2. 아이디어 `claude-first-worker-no-verify`, `worker-machine-wide-kill`. 특정 레포의 시험 명령을 넣지 않는다.
