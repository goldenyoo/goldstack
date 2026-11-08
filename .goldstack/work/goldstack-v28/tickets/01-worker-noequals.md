---
id: "01"
title: "worker 셸의 zsh `=` 확장을 끈다(ZDOTDIR 전달 `.zshenv`)"
blocked_by: []
touches: ["src/gs/adapters.py", "src/gs/shellenv.py", "tests/test_shellenv.py", "docs/research/worker-noequals.md"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker 명령 묶음이 `zsh: == not found`로 끊기는 원인을, 사용자 셸 설정을 보존한 채 worker 셸에서 없앤다.

## 완료 조건
- gs가 worker를 띄울 때 실행 디렉터리(worktree 밖)에 전달 폴더를 만들고 worker 환경의 `ZDOTDIR`을 그 폴더로 둔다. 폴더에는 `.zshenv` 하나만 있다. 그 파일은 (1) `ZDOTDIR`을 원래 값(worker를 띄우기 전의 `ZDOTDIR`, 없으면 변수 없음)으로 되돌리고, (2) 원래 `.zshenv`(`${ZDOTDIR:-$HOME}/.zshenv`)가 있으면 읽고, (3) `setopt noequals`를 켠다. 그래서 사용자 `.zshenv`의 `$ZDOTDIR` 상대 경로가 원래 폴더를 가리키고, 뒤의 `.zprofile`·`.zshrc`·`.zlogin`은 zsh가 원래 위치에서 읽는다.
- 띄우는 실행에서 전달 폴더를 준비하지 못하면 그 worker는 `ZDOTDIR`도 바꾸지 않고 `GS_NOEQUALS`도 넣지 않는다(지금과 같음).
- `GS_NOEQUALS=1`은 이번 실행에서 전달 폴더를 준비했고, 그 CLI가 실측 통과 목록(코드 상수, 근거는 연구 문서)에 있을 때만 넣는다. 실측이 실패했거나 재지 못한 CLI는 `ZDOTDIR`도 바꾸지 않는다.
- 먼저 설치된 CLI로 실측해 `docs/research/worker-noequals.md`에 명령·버전·결과를 CLI별 표로 적는다: claude(실제 `claude -p` Bash 도구, 셸 스냅샷 포함)·agy·codex 각각, 이 환경에서 셸 도구로 `echo ===; echo after`를 돌려 둘 다 나오는지, 사용자 `.zshrc`가 설정한 PATH 항목 하나와 별칭 하나가 그대로 보이는지. worker 안에서 그 CLI를 부를 수 없어 재지 못하면 표에 "측정 불가"와 이유를 적고 실패로 본다.
- 시험 `tests/test_shellenv.py`(실제 `/bin/zsh`, 임시 HOME): 원래 `ZDOTDIR`이 있을 때·없을 때; 사용자 `.zshenv`가 `source "$ZDOTDIR/extra"`를 할 때 원래 폴더의 파일을 읽음; 사용자 `.zshenv`가 `ZDOTDIR`을 바꿀 때; 비대화형 `zsh -c`와 로그인 `zsh -l -c` 둘 다 `echo ===; echo after`가 둘 다 출력하고 사용자 `.zshrc`·`.zprofile`의 값이 보임; 준비 실패면 env에 `ZDOTDIR`·`GS_NOEQUALS` 둘 다 없음; 목록 밖 CLI의 env에 둘 다 없음. 각 동작을 지우면 실패한다.
- `adapters.py` 머리말에 이 환경 변수들을 적는다.

## 범위 밖
- hook의 `=` 판정 변경(02)
- 일반 대화 세션의 zsh 설정(`.goldstack/out-of-scope/hook-equals-all-sessions.md`)
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4·3-1, §6(claude Bash 도구 실측)
