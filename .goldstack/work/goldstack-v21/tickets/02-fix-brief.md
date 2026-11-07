---
id: "02"
title: "수정 worker brief에 touches의 시험과 설명 확인 규칙을 넣는다"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/go.py", "tests/test_fix_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
수정 worker가 돌릴 시험을 찾지 못하거나, 지적이 요구하지 않은 설명을 확인 없이 커밋해 2차 수정으로 가는 일을 줄인다.

## 완료 조건
- `review.fix_brief`가 티켓 `touches`를 받고, brief에 `touches` 목록과 그중 시험 파일을 돌리라는 문장이 나온다. `go.py`의 호출 두 곳이 모두 넘긴다. 시험 파일이 없으면 시험 문장은 나오지 않는다.
- brief에 "지적이 요구하지 않은 새 동작 설명은 쓰지 않거나, 쓰면 코드 줄을 확인한다"는 뜻의 문장이 1차·2차 모두 나온다.
- `tests/test_fix_brief.py`가 touches가 있을 때, 시험 파일이 없을 때, 2차 수정일 때를 시험한다. 문장을 지우면 실패한다.
- `go.py`와 `review.py`의 docstring이 이 동작과 맞는다.

## 범위 밖
- 리뷰·판단 프롬프트: 티켓 03. 수리 worker brief(`repair_brief`)는 고치지 않는다.

## 참고
- spec 결정 2-3, §6. 아이디어 `skill-test-finding`, `fix-worker-unverified-text`.
