---
id: "03"
title: "gs check가 agy 호출을 최악으로 센다"
blocked_by: []
touches: ["src/gs/check.py", "tests/test_agy_config.py", "tests/test_second_review.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
재리뷰까지 세어, 경고 0으로 시작한 실행에서 재시도 없이 agy 리뷰가 빠지지 않게 한다.

## 완료 조건
- `check.agy_problems`가 범위 안 티켓의 `model`·`reviewer`·`second_reviewer` 중 agy인 자리마다 3회로 센다. 넘으면 `경고: 범위 안 agy 최대 9회(배정 3 × 3)가 상한 agy.max_calls_per_run=6회를 넘는다` 모양으로 나온다.
- 경계를 시험한다: 배정 2 × 3 = 상한 6이면 경고가 없고, 배정 3이면 경고가 있다. 상한 0에 배정이 있으면 경고가 있다.
- docstring이 새 세는 법과 재시도를 세지 않는다는 것을 적는다.

## 범위 밖
- 실행 중 상한 동작은 바꾸지 않는다. `docs/guide.md`는 티켓 06이 맡는다.

## 참고
- spec 결정 2-1, §6. 아이디어 `agy-limit-counts-rereview`.
