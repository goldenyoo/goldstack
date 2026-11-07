---
id: "07"
title: "worker hook이 따옴표 없는 = 단어를 막는다"
blocked_by: []
touches: ["src/gs/hook.py", "tests/test_hook.py"]
closes: [32]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker의 명령 묶음이 zsh의 `=` 확장으로 조용히 끊겨, 뒤 명령이 돌지 않았는데 돈 것처럼 읽히는 일을 막는다.

## 완료 조건
- `GS_ROLE=worker`일 때 따옴표 밖에서 `=`로 시작하고 두 글자 이상인 단어가 있는 Bash 명령을 막고, 따옴표를 쓰라고 안내한다. 예: `echo ===`, `echo =====`, `x ==`, `[ a == a ]`, `test a == a`, `x=$(echo ==)`.
- 막지 않는다: `echo =`, `[ a = a ]`, `test a = a`, `FOO=bar true`, `echo a=b`, `export X==1`, `git log --format==`, `echo "==="`, `echo '==='`, `[[ a == a ]]`, `if [[ a == a ]]; then …; fi`, heredoc 본문과 주석.
- 판정은 따옴표 정보가 남아 있는 단계에서 한다. `shlex`로 나눈 뒤에는 `"==="`와 `===`를 가르지 못한다.
- 위 예를 모두 시험한다. `GS_ROLE`이 worker가 아니면 막지 않는 것도 시험한다.

## 범위 밖
- 일반 세션 차단과 `hooks/hooks.json`: spec 결정 2-8. `docs/guide.md`의 `setopt noequals` 안내: 티켓 10.

## 참고
- spec 결정 2-8, §6의 zsh 측정. 위 예의 분류는 zsh 5.9 실측이다.
