---
id: "01"
title: "worker hook의 = 판정에서 놓침과 오차단을 줄인다"
blocked_by: []
touches: ["src/gs/hook.py", "tests/test_hook.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
이 레포에서 재현된 판정 오류 세 가지를 판정 구조를 바꾸지 않고 고친다.

## 완료 조건
- 오차단 해소: `cat <<'123'` 본문의 `===`를 막지 않는다. 산술 `(( 1 << 2 ))` 뒤의 `echo ===`는 계속 막는다.
- 놓침 해소: 같은 zsh에서 도는 `eval 'echo ===; echo done'`, `zsh -f -c 'echo ===; echo done'`, `echo $(echo ===)`를 막는다. `bash -c 'echo ==='`와 `sh -c 'echo ==='`는 막지 않는다.
- 놓침 해소: `echo ""===; echo done`과 `echo ''===; echo done`을 막는다. `echo foo\ ===; echo done`은 막지 않는다.
- 위 문장마다 `hook.decide` 시험이 있고, 수정을 지우면 실패한다. 기존 `tests/test_hook.py`의 단언을 약하게 하지 않는다.

## 범위 밖
- 단어 단위 파서 재작성(결정 2-6)
- 따옴표 없는 숫자 종료자 `<<123`

## 참고
- spec §3 2-6
- 아이디어 `goldstack-v21-07-1`, `goldstack-v21-07-3`, `goldstack-v21-07-4`
