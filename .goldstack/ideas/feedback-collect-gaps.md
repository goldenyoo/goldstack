---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v8 06 리뷰(codex) 보고만 2건, 2026-11-05 코드 대조"
status: "taken"
feature: "goldstack-v14"
---
gs 결함 자동 수집이 마무리 초반 오류와 수정 worker 실패를 놓친다.

**근거(코드 확인)**:
- `feedback`의 마무리 수집은 `finish.error`와 `마무리 실패`로 시작하는 outcome을 본다. `_publish`의 `GitError`는 `go.go`가 잡고 state에 흔적을 남기지 않아 preparing 단계 실패는 초안이 없다.
- `feedback.failure_logs`는 `*/*/failure.log`만 찾는다. 수정 worker는 이 파일을 남기지 않는다(docstring에 적혀 있다). 수정 worker의 `agy-no-result`, codex ref 잠금 실패가 빠진다.

**정할 것**: 고치려면 `go.py`나 `finish.py`가 오류를 state에 남겨야 한다. 환경 오류와 구별할 수 있어야 공개 issue에 잡음이 늘지 않는다.
