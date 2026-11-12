---
date: "2026-11-10"
severity: "high"
source: "/retro goldstack-v31"
status: "taken"
issues: []
feature: "goldstack-v33"
---
hook이 worktree 안의 `git stash`를 막지 않는다. `refs/stash`는 모든 worktree가 함께 쓴다.

- goldstack-v31 03 worker가 `git stash push -u` 뒤 `pop`을 실행했고 규칙 위반을 스스로 적었다(`run/03/1/worker.log` 68행).
- `src/gs/hook.py`의 `GIT_WRITES`는 worktree 밖(`-C`, `cd`)의 `stash`만 막는다.

고칠 곳: worktree에서도 `stash`를 막고 `list`·`show`만 허용한다.
