---
id: "03"
title: "수정·수리 worker는 좁은 시험만"
blocked_by: ["02"]
touches: ["src/gs/worker.py", "src/gs/review.py", "tests/test_fix_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
gs가 어차피 병합 트리에서 다시 검증하므로, 수정·수리 worker는 전체 시험 대신 좁은 시험만 돌린다.

## 완료 조건
- 수정·수리 worker의 brief에서 `커밋 전에 이 명령을 한 번 돌린다`가 빠지고, 고친 곳에 닿는 좁은 시험만 돌리라고 적힌다. 전체 검증은 gs가 한다는 것도 적힌다.
- 첫 구현 worker의 brief는 글자 하나 바뀌지 않는다.
- `tests/test_fix_brief.py`가 세 brief를 모두 본다. 티켓에 좁은 `verify`가 있어도 같게 동작한다.

## 범위 밖
- 첫 worker의 전체 시험 제거: `out-of-scope/first-worker-no-verify.md`.

## 참고
- spec 2-2
- `worker.write_brief`, `review.fix_brief`
