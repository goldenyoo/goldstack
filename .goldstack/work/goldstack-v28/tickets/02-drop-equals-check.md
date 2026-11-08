---
id: "02"
title: "noequals worker에서는 같은 셸의 `=` 판정만 건너뛰고 새 zsh 본문은 계속 본다"
blocked_by: ["01"]
touches: ["src/gs/hook.py", "tests/test_hook.py", "tests/test_hook_equals_cases.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
놓침과 오차단을 반복한 `=` 단어 판정을, 원인이 없어진 곳(같은 셸)에서는 하지 않고, 원인이 남는 곳(새로 띄운 zsh)에서는 지금처럼 한다.

## 완료 조건
- 환경에 `GS_NOEQUALS=1`이 있으면 맨 바깥 셸과 같은 셸에서 도는 `eval` 본문·치환·`( )` 속의 `=` 단어 판정을 건너뛴다. 새 zsh 프로세스의 본문(`zsh -c`, `zsh -f -c`, `zsh -o equals -c` 등)은 시작 파일을 읽지 않을 수 있으니 지금처럼 판정한다. `GS_NOEQUALS`가 없으면 지금과 똑같다. 판정 코드는 지우지 않는다.
- 다른 판정(push, gh 쓰기, worktree 밖 쓰기, 비밀 파일, `pkill`, v26의 `[hook.worker_tests]`)의 결과는 바뀌지 않는다. `tests/test_hook.py`·`tests/test_hook_worker_tests.py`의 기존 시험은 그대로 통과한다.
- 시험 `tests/test_hook_equals_cases.py`: `GS_NOEQUALS=1`에서 통과 — `eval "[[ \$(echo ===) == a ]]"`, `""! [[ a == a ]]`, `> ""/dev/null [[ a == a ]]`, `echo ';' eval '==='`, `echo ===`. `GS_NOEQUALS=1`에서도 막힘 — `zsh -f -c 'echo ==='`, `zsh -c 'echo ==='`. `GS_NOEQUALS`가 없으면 `echo ===`가 지금처럼 막힌다. 각 경우는 `/bin/zsh`(통과 쪽은 01의 전달 폴더 환경, `; echo after`를 붙여 `after`가 나오는지)로 끊김 여부를 함께 확인한다. `""!`는 `bad pattern`을 내지만 끊기지 않는다(grill 때 실측). 건너뛰는 분기나 새 zsh 판정을 지우면 실패한다.
- `hook.py` 머리말에 `GS_NOEQUALS`에서 건너뛰는 범위와 남는 범위를 적는다. 남는 알려진 오차단(`zsh -f -c "echo \$(echo a)==="`, `echo ';' zsh -c 'echo ==='`)도 적는다.

## 범위 밖
- 단어 단위 파서 재작성(`.goldstack/out-of-scope/hook-word-parser.md`)
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4·3-1, §6
- 아이디어 `hook-missed-agy-findings`, `goldstack-v23-01-2`
