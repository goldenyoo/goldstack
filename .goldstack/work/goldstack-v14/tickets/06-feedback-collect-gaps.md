---
id: "06"
title: "결함 수집이 마무리 초반·수정 worker 실패도 보게"
blocked_by: ["05"]
touches: ["src/gs/feedback.py", "src/gs/go.py", "src/gs/finish.py", "src/gs/state.py", "tests/test_feedback_collect.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
gs 결함 자동 수집이 마무리 초반 오류와 수정 worker 실패도 보게 한다.

## 완료 조건
- `_publish`의 `GitError`처럼 preparing 단계에서 난 마무리 오류가 state에 남고 `feedback`이 초안을 만든다.
- 수정·수리 worker의 실패(`agy-no-result`, codex ref 잠금 등)도 `failure_logs`가 찾는다.
- 환경 오류(인증, 네트워크, 권한)는 지금 분류를 따라 공개 issue 잡음이 늘지 않는다. 시험으로 본다.
- 옛 `state.json`을 읽고, 재개·재실행에서 같은 오류를 두 번 올리지 않는다.

## 범위 밖
- 모델로 분류하기: `out-of-scope/feedback-model-classify.md`.

## 참고
- `.goldstack/ideas/feedback-collect-gaps.md`
- `feedback.failure_logs`, `go.go`, `finish`
