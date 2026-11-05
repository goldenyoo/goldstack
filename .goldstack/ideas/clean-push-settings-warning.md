---
date: "2026-11-05"
severity: "low"
source: "goldstack-v8 12 리뷰(codex) 보고만, 2026-11-05 코드 대조"
status: "open"
feature: ""
---
자동 integration 정리에서 push 설정 변경을 감지해도 경고만 내고 `gs go`가 성공으로 끝난다.

**근거(코드 확인)**: `clean._remove`의 `git.check_push`는 `except (git.GitError, OSError)` 안에 있어 `PushSettingsChanged`도 경고가 된다. `clean.integration`은 "오류는 실행 결과를 바꾸지 않는다"고 적는다.

**낮춘 이유**: 원래 medium이다. push는 대조로 막히고, 바뀐 값은 경고에 나온다. 빠지는 것은 종료 코드뿐이다.
