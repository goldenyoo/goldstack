---
id: "01"
title: "worker의 worktree 안 git stash와 claude worker의 Monitor를 막는다"
blocked_by: []
touches: ["src/gs/hook.py", "src/gs/adapters.py", "tests/test_hook.py", "tests/test_adapters.py", "tests/test_isolation.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker가 모든 worktree가 함께 쓰는 `refs/stash`를 바꾸지 못하게 하고, claude worker가 `Monitor`를 걸어 일을 마친 뒤에도 알림마다 다시 깨어나지 않게 한다(아이디어 `hook-worktree-stash`, `worker-disallow-monitor`).

## 완료 조건
- worker hook(`gs hook pretooluse`, `GS_ROLE=worker`)이 worktree 안에서 도는 `git stash`(하위 명령 없음, `push`, `pop`, `apply`, `drop`, `clear`, `save`, `create`, `store`, `branch`, `-u` 같은 옵션만 있는 형태)를 막는다. 막는 이유 문구는 "`refs/stash`는 모든 worktree가 함께 쓴다"는 뜻을 담는다. `git stash list`와 `git stash show …`는 막지 않는다. worktree 밖(`-C`, `cd`)의 stash 판정은 지금 그대로다(worktree를 품지 않는 임시 디렉터리 안 레포는 지금처럼 허용, `allowed_outside`).
- `tests/test_hook.py`: 위 막는 형태 각각과 `list`·`show` 허용을 시험한다. 지금 worktree 안 `git stash push -u`가 통과하는 것을 먼저 실패하는 시험으로 본다.
- claude worker 명령(`src/gs/adapters.py` `Claude.BASE`)의 `--disallowedTools`에 `Monitor`가 들어간다. 수정·수리 worker도 같은 명령을 쓰는지 확인하고, `tests/test_adapters.py`가 만들어진 명령에 `Monitor`가 있음을 단언한다. `tests/test_isolation.py`의 `--disallowedTools` 인자 단언(차단 도구 뒤 바로 `--` 옵션)을 세 도구에 맞춘다.
- worker 로그에 `result` 이벤트가 여러 개일 때 gs가 마지막 메시지로 어느 것을 읽는지 확인해 마지막 메시지에 적는다(코드는 바꾸지 않아도 된다).
- 바꾼 상수·함수의 docstring과 주석을 맞춘다(`GIT_WRITES` 주석은 이제 worktree 안의 stash 규칙도 가리킨다).

## 범위 밖
- 문서(`docs/`)는 08
- agy·codex worker의 대기 도구(그 CLI에는 Monitor가 없다)

## 참고
- spec §3 1-1, §6 hook·adapters 줄
- `.goldstack/ideas/hook-worktree-stash.md`, `.goldstack/ideas/worker-disallow-monitor.md`
