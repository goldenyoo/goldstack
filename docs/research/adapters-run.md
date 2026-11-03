# 05 모델 어댑터: 실제 codex·agy 실행 기록 (2026-11-03)

티켓 05 완료 조건 "실제 codex·agy로 작은 티켓을 한 번씩 돌린 로그"의 증거. PR 본문에 붙일 원본이다.
환경: codex-cli 0.166.0, agy 1.4.12, macOS arm64. 버리는 레포 `/tmp/gs05real.XblG/`(원격은 로컬 bare 레포, gh는 가짜).

## 1. `gs go`로 codex 티켓 하나, agy 티켓 하나
티켓: `01`(model codex), `02`(model agy). 둘 다 "`greet_<model>.py`에 `greet(name)`, unittest 하나, 커밋". spec `verify: python3 -m unittest discover -q`, `max_workers: 2`.
이 브랜치의 gs로 돌렸다(`GS_RUNNER=subprocess .venv/bin/python -m gs.cli go demo`). 먼저 `gs check demo`: 경고 0(agy hook 확인 통과).

```
■ integration: gs/demo/integration @ d3a14cf5
■ 순서: 01 02
■ 동시 worker: 최대 2
[01] 시작: codex 작은 티켓: greet_codex (codex, pid 70803, 로그 …/run/01/worker.log)
[02] 시작: agy 작은 티켓: greet_agy (agy, pid 71025, 로그 …/run/02/worker.log)
[01] worker 끝: 종료 코드 0, 새 커밋 1
[01] 검증: python3 -m unittest discover -q
[01] 검증 통과 → integration 병합
[02] worker 끝: 종료 코드 0, 새 커밋 1 (ERROR 단계 1개(막힌 도구 호출 포함))
[02] 검증: python3 -m unittest discover -q
[02] 검증 통과 → integration 병합
■ 요약: 병합 2
■ PR: https://example.test/pr/1
exit=0
```

### 1.1 codex: gs가 만든 명령(run.sh)
```sh
export GS_ROLE=worker …
( codex exec --json -s workspace-write -c sandbox_workspace_write.network_access=false --skip-git-repo-check \
    -C …/run/wt/01 \
    --add-dir …/repo/.git/worktrees/01 --add-dir …/repo/.git/objects \
    --add-dir …/repo/.git/refs/heads/gs/demo --add-dir …/repo/.git/logs/refs/heads/gs/demo \
    '아래 <stdin>의 brief대로 일한다. sandbox 때문에 … gs가 sandbox 밖에서 검증을 다시 돌린다.' < …/run/01/brief.md ) 2>&1 | tee -a …/worker.log | python -m gs.streamfmt
```
worker.log(`gs.streamfmt`로 보기 좋게 바꿈):
```
■ 시작: codex thread 01a19f30-6b19-77e0-9d7f-97c7b9bf608a
! failed to parse plugin hooks config ~/.codex/plugins/cache/cc-ops-kit/…/hooks.json: unknown field `modules` …   (사용자 codex 설정 문제, 무관)
→ 파일 변경 [".../wt/01/greet_codex.py", ".../wt/01/test_greet_codex.py"]
→ /bin/zsh -lc 'python3 -m unittest discover -q' (종료 0)
→ /bin/zsh -lc "git add -- greet_codex.py test_greet_codex.py; …; git commit -m 'Add codex greeting function and unittest'" (종료 0)
완료했습니다. … 커밋: `4d171e7` (`gs/demo/01`)
■ 결과: turn.completed
```

### 1.2 agy: gs가 만든 명령(run.sh)
```sh
export GS_ROLE=worker
export GS_WORKTREE=…/run/wt/02
( agy -p "$(cat …/run/02/brief.md)" --output-format stream-json --dangerously-skip-permissions --disable-slash-commands \
    --settings '{"permissions":{"deny":["command(git push)","command(gh pr create)","command(gh pr merge)","command(gh pr close)","command(gh api)","command(gh repo)","command(gh release)","command(gh auth)"]}}' \
    --model gemini-4-argon-high ) 2>&1 | tee -a …/worker.log | python -m gs.streamfmt
```
띄우기 전 gs가 worktree에 `.agents/hooks.json`(`goldstack-worker-guard`, PreToolUse `*`, `<python> -m gs.cli hook agy-pretooluse`)을 쓰고
git exclude 파일(`git rev-parse --git-path info/exclude`, linked worktree라 공통 git 디렉터리의 것)에 `/.agents/hooks.json`을 넣었다. 커밋에 섞이지 않았다(integration 트리에 `.agents/` 없음).

worker.log(`gs.streamfmt`):
```
■ 시작: model=gemini-4-argon-high cwd=…/run/wt/02 permission=always-proceed
→ read_file …/wt/02/.work/demo/spec.md
→ read_file …/wt/02/.work/demo/tickets/02-agy.md
→ run_command git status && ls -la
→ run_command git log -n 5 --stat
! run_command find .agents -maxdepth 4 — tool call denied by pre-tool hook: gs가 막음: `.agents/`는 gs가 건 차단 장치(hook 설정)다. …
→ write_file …/wt/02/greet_agy.py
→ write_file …/wt/02/test_greet_agy.py
→ run_command python3 -m unittest discover -q
→ run_command rm -rf __pycache__ && git add greet_agy.py test_greet_agy.py && git status
→ run_command git commit -m "Add greet_agy and unittest" && python3 -m unittest discover -q && …
■ 결과: SUCCESS
티켓 02 구현 및 커밋을 완료했습니다. …
```
마지막 줄: `{"event":"result","result":{"status":"SUCCESS",…,"duration_seconds":74.46,"num_turns":1}}`(`finished_reason` 없음 → 성공).
`find .agents`가 막힌 것이 gs hook이 실제 agy 실행 안에서 걸려 있었다는 증거다(그 메시지는 `gs hook agy-pretooluse`만 낸다).

## 2. codex sandbox와 git worktree (어댑터 설계 근거)
worktree의 `.git`은 파일이고 실제 git 디렉터리는 주 레포 `.git/worktrees/<name>`이다. 버리는 레포에서 "파일 하나 만들고 커밋" 프롬프트로:

| 명령 | 결과 |
|---|---|
| `codex exec --json -s workspace-write` | `git add` 실패: `fatal: Unable to create '…/repo/.git/worktrees/wt/index.lock': Operation not permitted`. **종료 0** |
| 위 + `--add-dir <repo>/.git` | 같은 실패. codex는 `.git` 디렉터리를 add-dir해도 쓰기를 막는다 |
| 위 + `--add-dir` `.git/worktrees/wt`, `.git/objects`, `.git/refs`, `.git/logs` | 커밋 됨 |
| `--add-dir` `.git/worktrees/wt`, `.git/objects`, `.git/refs/heads/gs/x`, `.git/logs/refs/heads/gs/x` + `network_access=false` | 커밋 됨 → 어댑터가 쓰는 형태 |

codex는 커밋을 못 해도 종료 0이다. gs는 원래 "새 커밋 0 = 실패"로 본다.

## 3. agy deny 규칙의 gh 범위 (11 §6 "[추정], 05에서 한 번 확인")
hook 없이(`.agents/` 없는 디렉터리) 어댑터의 `--settings`만 주고 `--help` 형태(돌아도 무해)로 시험. `gemini-3.8-flash-low`.

| 명령 | 결과 |
|---|---|
| `gh pr create --help` | 막힘(`permission check failed for unsandboxed "gh pr create --help": Permission denied…`) |
| `gh pr merge --help` | 막힘 |
| `gh api --help` | 막힘 |
| `gh repo view --help` | 막힘(`command(gh repo)`가 읽기까지 막는다. 넓게 막는 쪽이라 둔다) |
| `gh auth status --help` | 막힘(`command(gh auth)`) |
| `gh pr view --help` | 통과 |

`result.status: SUCCESS`, 종료 0(막혀도 0: 11 §3.1과 같다).
