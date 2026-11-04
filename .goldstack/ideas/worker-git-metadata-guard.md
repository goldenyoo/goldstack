---
date: "2026-11-04"
severity: "high"
source: "2026-11-04 Codex 리뷰(Claude가 재현)"
status: "taken"
feature: "goldstack-v8"
---
worker가 공용 git 설정을 바꿔 gs의 push 목적지나 실행될 git hook을 바꿀 수 있다.

**재현(2026-11-04, `hook.decide`에 직접 입력)**: `git remote set-url origin <주소>`, `git config remote.origin.url <주소>`, `git config core.hooksPath <경로>`, `git config --global core.hooksPath <경로>`, `git branch -f gs/f/02 HEAD`, `git update-ref refs/heads/main HEAD`가 모두 통과한다. `git push`만 막힌다.

**왜 나쁜가(코드 추적, 끝까지 재현하지는 않음)**: worktree의 git 설정은 주 레포와 공유한다. worker의 push 차단 env는 worker 안에서만 듣고 gs 자신의 push는 그 밖에서 돈다. 그래서 worker가 원격 URL을 바꾸면 worktree는 깨끗한 채로 남고, 뒤의 gs push가 그 주소로 코드를 보낼 수 있다. `core.hooksPath`면 gs의 git 명령이 그 hook을 실행할 수 있다(추정).

**해당 범위**: Claude·agy worker. Codex worker는 `Codex.writable_dirs`에 공용 `.git/config`가 없어 sandbox가 막는다(코드 확인).

**제안(S–M)**: hook에서 `git remote` 변경, `git config` 쓰기, 다른 ref를 옮기는 `update-ref`·`branch -f`를 막는다. 실행 시작 때 원격 URL을 기록하고 gs의 push 전에 대조한다. Codex는 저장소 분리(L)를 제안했지만 비용이 커서 작은 안을 먼저 한다.

**한계**: hook은 안전띠다(`docs/internals.md`). `python -c`처럼 코드로 파일을 고치는 길은 hook으로 못 막으므로 push 전 대조가 함께 있어야 한다.
