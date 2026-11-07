# 일반 세션의 `=` 단어 차단

**무엇**: worker가 아닌 대화 세션에서도 hook이 따옴표 없는 `=` 단어를 막는다.

**왜 밖**: `hooks/hooks.json`의 worker 조건을 풀면 모든 Bash 호출마다 `gs`가 돌고, 일반 세션의 정상 명령을 잘못 막을 위험이 있다. 대화 세션은 `~/.zshenv`의 `setopt noequals`로 원인을 없앨 수 있다.

**다시 볼 조건**: `setopt noequals`가 Claude Code Bash 도구에 적용되지 않거나, 적용해도 대화 세션에서 구분선 때문에 명령 묶음이 또 끊기면.

결정: goldstack-v21 grill 라운드 2-8 (2026-11-07)
