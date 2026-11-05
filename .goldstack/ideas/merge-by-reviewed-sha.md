---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v8 13 리뷰(codex) 보고만, 2026-11-05 코드 대조"
status: "taken"
feature: "goldstack-v15"
---
head 대조 뒤 실제 병합까지 티켓 브랜치가 움직이면 재리뷰 없이 새 커밋이 병합된다.

**근거(코드 확인)**: `go._merge_stage`는 `_catch_up` 뒤 `git merge --no-ff --no-commit <브랜치 이름>`으로 병합한다. 리뷰어가 본 SHA로 고정하지 않는다. v8 리뷰가 mock 재현에서 리뷰 A, 병합 B를 확인했다. 지금 구조의 대조 위치는 `_leave_review`다.

**판단**: git 명령 몇 개 동안만 열리는 틈이고 살아남은 worker 자손이 그때 커밋해야 한다. 막으려면 catch-up 커밋 구분, SHA 고정 병합, 늦은 커밋 처리까지 병합 경로를 바꿔야 한다.
