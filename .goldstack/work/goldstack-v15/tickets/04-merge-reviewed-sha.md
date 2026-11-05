---
id: "04"
title: "리뷰한 SHA로 병합"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/review.py", "tests/test_review_target.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
리뷰어가 본 SHA만 병합되게 한다.

## 완료 조건
- `go._merge_stage`가 브랜치 이름이 아니라 리뷰가 끝난 SHA로 `git merge --no-ff --no-commit`을 한다.
- `_catch_up`이 만든 커밋은 리뷰 대상을 흐리지 않는다. catch-up과 늦은 worker 커밋을 구별한다.
- 브랜치가 리뷰 뒤 움직였으면 병합하지 않고 재리뷰로 돌아간다. 살아남은 worker 자손의 늦은 커밋이 재리뷰 없이 들어가지 않는 것을 시험한다.
- 수리 worker(goldstack-v12 02)의 커밋과 재리뷰 흐름이 그대로 돈다. 재개와 옛 `state.json`을 읽는다. 리뷰 없이 verify만으로 병합하는 경로(리뷰 실패)는 바뀌지 않는다.

## 범위 밖
- 마무리 PR 병합은 건드리지 않는다.

## 참고
- spec 2-23
- `.goldstack/ideas/merge-by-reviewed-sha.md`
- `go._leave_review`
