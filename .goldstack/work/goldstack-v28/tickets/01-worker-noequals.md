---
id: "01"
title: "worker 셸의 zsh `=` 확장을 끈다(ZDOTDIR 전달 폴더)"
blocked_by: []
touches: ["src/gs/adapters.py", "src/gs/shellenv.py", "tests/test_shellenv.py", "docs/research/worker-noequals.md"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker 명령 묶음이 `zsh: == not found`로 끊기는 원인을 hook 판정 대신 셸 설정으로 없앤다.

## 완료 조건
- gs가 worker를 띄울 때 실행 디렉터리(worktree 밖)에 전달 폴더를 만들고 worker 환경의 `ZDOTDIR`을 그 폴더로 둔다. 폴더의 `.zshenv`·`.zprofile`·`.zshrc`·`.zlogin`은 각각 원래 위치(worker를 띄우기 전의 `ZDOTDIR`, 없으면 `HOME`)의 같은 파일이 있으면 읽고, `.zshenv`만 끝에 `setopt noequals`를 더한다. 원래 위치가 전달 폴더 자신이면 다시 읽지 않는다(무한 재귀 없음).
- 이 환경을 받은 worker에 `GS_NOEQUALS=1`을 넣는다(02의 hook이 본다).
- 먼저 설치된 CLI로 실측해 `docs/research/worker-noequals.md`에 명령과 결과를 적는다: claude·agy·codex worker 각각, 이 환경에서 셸 도구로 `echo ===; echo after`를 돌려 `===`와 `after`가 둘 다 나오는지, 그리고 사용자 `.zshrc`가 설정한 PATH 항목 하나가 그대로 보이는지. 실측이 실패했거나 worker 안에서 그 CLI를 부를 수 없어 재지 못한 CLI(표에 "측정 불가"와 이유)에는 `GS_NOEQUALS`를 넣지 않는다(ZDOTDIR은 넣어도 된다). 결과는 CLI별 표로 적는다.
- 시험 `tests/test_shellenv.py`: 전달 폴더 네 파일의 내용(원래 파일 읽기, `.zshenv`의 `noequals`), 원래 `ZDOTDIR`이 있을 때·없을 때, 원래 위치가 전달 폴더일 때 재귀 없음, 실제 `/bin/zsh -c 'echo ===; echo after'`를 그 `ZDOTDIR`로 돌리면 둘 다 출력. 실측 표에서 통과한 CLI의 env에만 `GS_NOEQUALS=1`이 있다. 각 동작을 지우면 실패한다.
- `adapters.py` 머리말에 이 환경 변수들을 적는다.

## 범위 밖
- hook의 `=` 판정 변경(02)
- 일반 대화 세션의 zsh 설정(`.goldstack/out-of-scope/hook-equals-all-sessions.md`)
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4, §6(claude Bash 도구 실측)
