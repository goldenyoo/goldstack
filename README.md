# goldstack

Claude Code로 프로젝트를 진행하는 개인 운영 kit. 처음에 grill로 깊게 정렬하고, `go` 한 번 뒤에는 구현 완료와 main 병합까지 알아서 진행한다.

- 철학: [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first", "never block on the human".
- 모델: Claude · codex · gemini를 티켓마다 고르고, 리뷰는 항상 다른 계열이 한다. herdr pane에서 worker를 보이게 돌린다.
- 상태: 레포 안 markdown 파일(`.work/<feature>/spec.md`, `tickets/NN.md`)과 git.

시작 배경과 요구사항은 [docs/ORIGINS.md](docs/ORIGINS.md), 참고한 kit 분석은 [docs/research/](docs/research/)(pstack, mattpocock/skills, 비교표).

## 설치와 사용
```sh
uv tool install --reinstall .   # 고정 복사로 설치. main을 받은 뒤 다시 실행한다
gs check <feature>              # .work/<feature>/의 spec과 티켓 그래프 검사
gs check <feature> --only 03,04 # 일부 티켓만 기준으로 순서·frontier 계산
gs go <feature> [--only 03,04]  # 티켓을 worker에 맡기고 integration에 모아 PR을 연다
gs status [<feature>]           # 실행 상태 표(읽기 전용). 생략하면 실행 중인 feature 전부
uv run python -m unittest discover -s tests   # 검증 명령
```

`gs go`: 시작할 수 있는 티켓(frontier)을 spec의 `max_workers`(기본 3)개까지 동시에 돌린다(04). worker마다
`claude -p`(headless)를 herdr pane에서 돌리고, pane들은 feature마다 탭 하나(`gs:<feature>`)에 모인다.
worker는 최신 integration 끝에서 만든 `gs/<feature>/NN` worktree에서 커밋하고 끝난다. 하나 끝날 때마다 gs가
state에서 frontier를 다시 계산해 빈자리를 채운다. 병합·검증은 한 번에 하나씩: 먼저 최신 integration 끝을 티켓
브랜치에 합쳐 보고(충돌하면 그 티켓은 실패, 이유 `conflict`), 검증을 다시 돌려 통과한 것만
`gs/<feature>/integration`에 병합한다. `max_workers: 1`이면 02와 같은 위상 순서로 하나씩 돈다. 끝나면 integration을 push하고 PR을 연다(병합은 08부터).
실행 흔적은 `.work/<feature>/run/`(gitignore): `NN/brief.md`, `NN/run.sh`, `NN/worker.log`, `NN/verify.log`, `wt/`.

상태(03): `run/state.json`이 상태의 원천이다. 티켓별 상태(pending, running, merged, failed, skipped), 시도 횟수,
브랜치, pane, 시작·끝 시각, 로그 경로, 실패 이유. 쓰기는 임시 파일 뒤 rename(원자적). `gs go`의 요약·PR 본문과
`gs status`가 모두 이 파일을 읽는다(마지막 출력 시각은 worker 로그의 수정 시각).
다시 실행하면 integration에 병합된 티켓은 건너뛰고, 실패·건너뜀 티켓은 다시 한다. 지난 `gs`가 죽어 running으로 남은
티켓은 실패로 세지 않고(시도 횟수에서 뺀다) 새로 시작한다. 같은 feature에 `gs go`는 하나만 돈다: `run/lock`에 flock을
잡고 pid를 적는다. 프로세스가 죽으면 커널이 잠금을 풀어 저절로 회수된다.

바꿔 끼우는 곳(시험 seam): `GS_RUNNER=subprocess|herdr`(기본: herdr 안이면 herdr), `GS_WORKER_CMD`(worker 셸 명령),
`GS_GH`(gh 경로).

## Claude Code plugin과 worker 차단 hook(09)
이 레포가 곧 plugin이자 로컬 marketplace다(`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`hooks/hooks.json`). 먼저 `gs`를 설치하고(위 `uv tool install`, hook은 별도 런타임 없이 PATH의 `gs`를 부른다), Claude Code에서:
```
/plugin marketplace add /path/to/goldstack   # 이 레포 디렉터리를 로컬 marketplace로 등록
/plugin install goldstack@goldstack          # user scope로 설치: 모든 프로젝트의 worker에 적용
```
명령줄로는 `claude plugin marketplace add /path/to/goldstack && claude plugin install goldstack@goldstack`.
레포를 바꾼 뒤에는 `/plugin marketplace update goldstack`. 설치 없이 한 세션만 쓰려면 `claude --plugin-dir /path/to/goldstack`.

PreToolUse hook은 `gs hook pretooluse`다. `GS_ROLE=worker`일 때만 판정하고, 없으면 입력도 읽지 않고 통과한다(일반 세션에
영향 없음). `gs go`는 worker 실행 스크립트에 `GS_ROLE=worker`, `GS_WORKTREE`를 넣는다. worker일 때 막는 것은 되돌릴 수 없는 일뿐이다:
- `git push`(모든 형태: `-C`, `cd .. &&`, `bash -c`, `$(…)` 안), force 계열(`--force`, `--force-with-lease`, `push -f`)
- `gh` 쓰기 명령(`pr create`·`merge`·`close`, `release …`, `repo …`, 쓰기 `gh api` 등). 읽기(`pr view`, `run view` …)는 통과
- worktree 밖 쓰기(Write·Edit 도구, 셸 리다이렉션·`rm`·`mv`·`cp`·`tee`, 밖에서 하는 `git commit` 등). 임시 디렉터리와 `/dev`는 통과
- 비밀 파일 읽기(`~/.ssh`, `~/.aws`, `~/.gnupg`, `.env`·`.env.*`(`.env.example` 등 제외), `~/.netrc`, gh 인증 파일, `gh auth token`)

막으면 이유와 "이 일은 `gs`가 한다"를 돌려준다. hook은 안전띠라 스크립트 파일 안까지 따라가지 않으므로 worker 명령의
도구 차단 옵션(`--disallowedTools "Bash(git push *)" "Bash(gh *)"`)도 남겨 둔다(이중 장치). codex·agy는 sandbox로 막는다(11).
