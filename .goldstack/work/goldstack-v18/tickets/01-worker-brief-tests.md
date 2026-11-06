---
id: "01"
title: "codex 첫 worker는 전체 시험을 돌리지 않고, worker는 새 시험의 실패를 본다"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/adapters.py", "tests/test_fix_brief.py", "tests/test_ticket_verify.py", "tests/test_sandbox_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
codex 첫 worker가 sandbox에서 통과할 수 없는 전체 시험에 시간을 쓰지 않게 한다. 버그를 고치는 worker가 새 시험이 고친 코드 없이 실패하는 것을 직접 보게 한다.

## 완료 조건
- 티켓 `model`이 codex면 첫 worker brief가 전체 검증을 돌리라고 하지 않고 좁은 시험까지만 시킨다. `Codex.NOTE`와 부딪치지 않는다. claude·agy의 첫 worker 문구는 그대로다. 재개로 부르는 `write_brief`도 같다.
- 첫·수정·수리 worker brief에 "버그를 고치면 고친 곳을 잠깐 되돌려 새 시험의 실패를 보고, 복구한 뒤 커밋하고, 본 것을 마지막 메시지에 적는다"는 뜻의 문장이 있다. 시험이 없는 문서 티켓에는 해당하지 않는다고 적는다.
- 재리뷰 지시는 바꾸지 않는다.
- 위 각 경우를 시험한다. `write_brief` docstring을 고친다.

## 범위 밖
- claude 첫 worker의 전체 시험 제거(`first-worker-no-verify`). 문서는 티켓 05가 맡는다.

## 참고
- spec 결정 1-1, 1-2, §6. 아이디어 `codex-worker-no-full-test`, `test-fails-without-fix`. 특정 레포의 시험 명령을 넣지 않는다.
