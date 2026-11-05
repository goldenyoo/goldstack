---
id: "05"
title: "빈 자리 순서와 끊김 중 리뷰 준비"
blocked_by: ["04"]
touches: ["src/gs/go.py", "src/gs/review.py", "tests/test_async_review.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
드문 순서 문제 둘을 고친다.

## 완료 조건
- 앞 티켓이 병합된 뒤 끝나 있던 리뷰 결과를 먼저 거둬, 빈 자리를 수정 worker가 새 티켓보다 먼저 얻는다(`Reviews.fix_waiting`). 11 병합, 12 리뷰 끝남, 14 대기의 재현을 시험으로 둔다.
- 끊김 중에는 두 번째 리뷰 준비를 미뤄 단계가 `network`로 보이고, 끊김이 끝난 뒤 최신 head를 리뷰한다. 재현을 시험으로 둔다.

## 범위 밖
- 검증을 루프 밖으로: `out-of-scope/async-verify.md`.

## 참고
- `.goldstack/ideas/fix-seat-priority-race.md`
- `.goldstack/ideas/outage-review-phase-label.md`
