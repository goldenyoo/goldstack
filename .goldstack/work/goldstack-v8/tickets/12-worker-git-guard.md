---
id: "12"
title: "worker의 git 설정 변경을 막고, gs의 push 전에 원격 설정을 대조한다"
blocked_by: ["15"]
touches: ["src/gs/hook.py", "src/gs/go.py", "src/gs/finish.py", "src/gs/state.py", "tests/test_worker_git_guard.py"]
model: claude
reviewer: codex
tier: large
---
## 목표
worker가 공용 git 설정을 바꿔 gs의 push 목적지나 실행될 git hook을 바꾸는 길을 막는다.

## 완료 조건
- `gs hook pretooluse`가 worker의 다음 명령을 막는다: `git remote` 변경(`set-url`, `add`, `remove`, `rename`), `git config` 쓰기(`--global` 포함, 읽기 `--get`·`--list`는 통과), 자기 브랜치 밖의 ref를 옮기는 `git update-ref`·`git branch -f`·`git symbolic-ref`. `git -C`·환경 변수 앞붙임 등 기존 hook이 푸는 형태도 잡는다. 시험이 아이디어의 재현 명령 전부를 본다.
- worker의 일반 작업은 그대로 통과한다: 자기 브랜치 `commit`, `add`, `status`, `diff`, `log`, 자기 브랜치 안에서의 `reset`. 시험이 있다.
- agy hook(`hook_agy`)도 같은 판정을 쓴다. 시험이 있다.
- `gs go`가 실행 시작 때 원격의 URL·pushurl과 `core.hooksPath`를 state에 기록한다. 재개하면 기록을 유지한다. gs의 모든 push 직전에 대조해 다르면 push하지 않고, 어떤 값이 바뀌었는지와 되돌릴 명령을 말하며 오류로 멈춘다. 시험: worker 쪽에서 `git config`로 원격을 바꾼 뒤 gs가 그 주소로 push하지 않는다(`python -c`처럼 hook을 우회한 경우를 흉내 낸다).
- `url.*.insteadOf`처럼 push 목적지를 바꾸는 사용자 설정이 원래 있어도 그것 때문에 멈추지 않는다(시작 때 값과 같으면 통과). worker 전용 push 차단 env는 판정에 쓰지 않는다. 시험이 있다.
- 기록이 없는 옛 state.json은 대조를 건너뛴다. 시험이 있다.

## 범위 밖
- 저장소 분리(비용이 크다), codex worker(sandbox가 공용 `.git/config`를 막는다), hook의 다른 빈틈(`agy-hook-search-secret`, v9).

## 참고
- spec §3 5-1 a. 아이디어 `.goldstack/ideas/worker-git-metadata-guard.md`.
- hook은 안전띠다(`docs/internals.md`). push 전 대조가 함께 있어야 한다.
