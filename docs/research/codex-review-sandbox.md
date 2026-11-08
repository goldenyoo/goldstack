# codex 리뷰어 sandbox 실측: workspace-write + 빈 임시 폴더 (2026-11-08)

티켓 goldstack-v27 02의 첫 완료 조건. codex 리뷰어가 `-s read-only`라 임시 디렉터리를 못 만들어 시험으로 재현하지 못한다
(아이디어 `codex-reviewer-writable-tmp`). 쓰기를 빈 임시 폴더로만 열고 리뷰 대상 worktree는 계속 막을 수 있는지 설치된 codex로 쟀다.
환경: codex-cli 0.167.0, macOS arm64. 실측한 worktree는 이 티켓의 worktree(`…/run/wt/02`), TMPDIR=`/var/folders/…/T/`.

## 명령

```
T=$(mktemp -d)        # 빈 임시 폴더
cd $T && codex exec --json -s workspace-write -c sandbox_workspace_write.network_access=false \
    --skip-git-repo-check -C $T "<아래 다섯 명령을 실행하고 명령·종료 코드·출력을 그대로 보고하라>"
```

codex가 실행한 명령(`command_execution` 이벤트의 `aggregated_output`, `exit_code`):

| # | 확인 | 명령 | 종료 | 결과 |
|---|---|---|---|---|
| 1 | `-C` 폴더에 쓰기 | `touch $T/probe_cwd && echo ok` | 0 | `ok`. 파일이 실제로 생겼다 |
| 2 | TMPDIR에 쓰기 | `touch "$TMPDIR/probe_tmp" && echo ok` | 0 | `ok`. 파일이 실제로 생겼다 |
| 3 | 폴더 밖 worktree 읽기 | `head -3 <worktree>/pyproject.toml` | 0 | `[project]` / `name = "goldstack"` / `version = "0.2.10"` |
| 4 | worktree에 쓰기 | `touch <worktree>/probe_wt` | 1 | `touch: …/probe_wt: Operation not permitted`. 파일이 생기지 않았다 |
| 5 | 네트워크 | `curl -sS -m 10 https://example.com` | 6 | `curl: (6) Could not resolve host: example.com` |

## 판정

네 가지 모두 기대대로다.

1. 쓰기: `-C` 폴더와 TMPDIR에 쓸 수 있다. 
2. 읽기: 폴더 밖 worktree 파일을 읽을 수 있다. 
3. 막힘: worktree에는 쓸 수 없다(`Operation not permitted`). 
4. 네트워크: `sandbox_workspace_write.network_access=false`로 이름 해석부터 실패한다.

그래서 코드를 바꿨다(`review.reviewer_argv`, `review._ask_reviewer`): codex 리뷰 호출은 `-s workspace-write -c sandbox_workspace_write.network_access=false -C <리뷰마다 새로 만든 빈 임시 폴더>`이고, 임시 폴더는 호출이 끝나면(실패·재시도 포함) 지운다.
gs가 만든 실제 argv(`-C`는 `tempfile.mkdtemp(prefix="gs-review-")`)로 한 번 더 돌려 같은 결과를 봤다: worktree `touch`는 `Operation not permitted`, `$TMPDIR`에는 쓰기 `tmpok`.

## 알아 둘 것

- `$TMPDIR`는 임시 폴더 하나가 아니라 사용자 전체의 임시 디렉터리(`/var/folders/…/T/`)다. 쓰기가 열린 곳은 `-C` 폴더와 이 TMPDIR이다. 리뷰어가 TMPDIR에 만든 파일은 gs가 지우지 않는다. `-C` 폴더만 지운다. 리뷰어에게는 쓰기를 임시 폴더와 TMPDIR에만 하라고 프롬프트로 알린다.
- worker의 `workspace-write`(`docs/research/adapters-run.md` §2)는 `.git` 쓰기가 막혀 gs가 ref 디렉터리를 따로 연다. 리뷰어는 worktree를 쓰지 않으므로 이 문제가 없다.
- `--output-last-message <review.txt>`는 `-C` 밖 경로에 쓴다. 같은 argv 형태에 `--output-last-message <다른 임시 폴더>/review.txt`를 붙여 돌리니 종료 0이고 파일에 `pong`이 남았다. sandbox가 이 파일을 막지 않는다.
