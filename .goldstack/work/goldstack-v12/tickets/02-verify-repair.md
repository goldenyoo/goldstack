---
id: "02"
title: "티켓 검증 실패를 같은 브랜치에서 수리"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/state.py", "src/gs/review.py", "src/gs/worker.py", "src/gs/metrics.py", "src/gs/report.py", "tests/test_verify_repair.py", ".goldstack/out-of-scope/repair-worker.md"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
티켓 검증이 실패하면 처음부터 다시 구현하는 대신, 같은 브랜치·worktree에서 실패 로그를 주고 고치게 한다.

## 완료 조건
- 티켓 검증이 실패(시간 초과 제외)하면 첫 번은 `go._fail`의 새 시도가 아니라 수리 worker가 같은 브랜치·worktree에서 돈다. brief에 `verify.log` 경로가 들어간다. 단계 이름은 `repair`이고 `state.PHASE_LABELS`에 있다.
- 수리 worker가 커밋을 남기면 `tiers.rereview`로 수리 diff를 재리뷰한 뒤 다시 병합·검증한다. 커밋이 없으면 재리뷰 없이 바로 다시 검증한다(불안정한 시험의 경우).
- 다시 검증도 실패하면 지금처럼 `go._fail`로 간다. 첫 실패를 재시도 횟수로 두 번 세지 않는다. 수리는 시도 하나에 한 번이다.
- 병합 충돌, `검증하는 동안 integration이 바뀌었다`, 검증 시간 초과는 수리하지 않고 지금 경로로 간다.
- 수리 중 gs가 죽거나 네트워크가 끊겨도 재실행이 이어 간다. 옛 형식 `state.json`을 그대로 읽는다. 수정 worker의 agy 상한 처리와 같게 동작한다.
- 보고서와 `gs status`에 수리한 사실과 그 결과가 보인다.
- 시험: 수리 뒤 통과, 커밋 없는 재검증 통과, 수리 뒤 실패의 새 시도, 수리 중 재개, 충돌은 수리 안 함.
- `out-of-scope/repair-worker.md`의 범위를 마무리 실패와 병합 충돌 수리로 좁힌다. `go.py`·`review.py` docstring을 고친다.

## 범위 밖
- 수정·수리 worker의 시험 범위: 티켓 03.
- 마무리 검증 실패와 병합 충돌의 수리: `out-of-scope/repair-worker.md`.

## 참고
- spec 2-1
- `.goldstack/ideas/e2e-time-reduction-2.md` 제안 2
- `go._start_fix`, `go._fail`, `go._check_worker`
- `docs/internals.md`
