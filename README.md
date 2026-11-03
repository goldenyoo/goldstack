# goldstack

Claude Code로 프로젝트를 진행하는 개인 운영 kit. 처음에 grill로 깊게 정렬하고, `go` 한 번 뒤에는 구현 완료와 main 병합까지 알아서 진행한다.

- 철학: [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first", "never block on the human".
- 모델: Claude · codex · gemini를 티켓마다 고르고, 리뷰는 항상 다른 계열이 한다. herdr pane에서 worker를 보이게 돌린다.
- 상태: 레포 안 markdown 파일(`.work/<feature>/spec.md`, `tickets/NN.md`)과 git.

시작 배경과 요구사항은 [docs/ORIGINS.md](docs/ORIGINS.md), 참고한 kit 분석은 [docs/research/](docs/research/)(pstack, mattpocock/skills, 비교표).

## 설치와 사용
사람이 쓰는 명령은 Claude Code의 `/grill <feature>`와 `/go <feature>` 둘이다(plugin skill, 아래 "plugin" 절로 설치).
- `/grill <feature>`: 사실은 직접 찾고 결정만 번호 붙인 라운드로 묻는다(선택지마다 예시, 추천과 이유, "yes" = 추천 전부).
  답은 라운드마다 `.work/<feature>/spec.md`에 적고, 마지막 라운드에서 티켓 분해를 확인받아 `tickets/`와 `.out-of-scope/`를
  쓴 뒤 `gs check`가 통과할 때까지 고친다. 파일 형식은 `skills/grill/templates/`.
- `/go <feature>`: `gs check` → herdr pane에서 `gs go` → 끝나면 report.md의 세 줄 요약과 PR 링크. 중간에 묻지 않는다.

그 아래의 `gs` CLI:
```sh
uv tool install --reinstall .   # 고정 복사로 설치. main을 받은 뒤 다시 실행한다
gs check <feature>              # .work/<feature>/의 spec과 티켓 그래프 검사
gs check <feature> --only 03,04 # 일부 티켓만 기준으로 순서·frontier 계산
gs go <feature> [--only 03,04]  # 티켓 실행 → 보고서·PR → 병합 → main 재검증
gs status [<feature>]           # 실행 상태 표(읽기 전용). 생략하면 실행 중인 feature 전부
uv run python -m unittest discover -s tests   # 검증 명령
```

`gs go`: 시작할 수 있는 티켓(frontier)을 spec의 `max_workers`(기본 3)개까지 동시에 돌린다(04). worker마다
티켓 `model`의 headless CLI(아래 "모델 어댑터")를 herdr pane에서 돌리고, pane들은 feature마다 탭 하나(`gs:<feature>`)에 모인다.
worker는 최신 integration 끝에서 만든 `gs/<feature>/NN` worktree에서 커밋하고 끝난다. 하나 끝날 때마다 gs가
state에서 frontier를 다시 계산해 빈자리를 채운다. 병합·검증은 한 번에 하나씩: 먼저 최신 integration 끝을 티켓
브랜치에 합쳐 보고(충돌 이유 `conflict`), 검증을 다시 돌려 통과한 것만
`gs/<feature>/integration`에 병합한다. `max_workers: 1`이면 02와 같은 위상 순서로 하나씩 돈다.
끝나면 새 Opus 호출로 요약을 작성하고 티켓 결과·남은 리뷰 지적·실제 검증 출력·되돌리는 법을
`.work/<feature>/report.md`에 모아 integration에 커밋한다. integration을 일반 push하고 PR을 만들거나
갱신한다. PR 본문은 이 보고서와 같다.

merged 티켓이 하나 이상이고 보고서 커밋까지 integration 검증이 통과하면 `gh pr merge --merge`를 실행한다.
PR을 다시 읽어 실제 MERGED와 병합 커밋을 확인한 뒤, 최신 `origin/main`을 임시 detached worktree에 받아
재검증한다. 실패하면 그 병합 커밋을 `git revert`하고 main에 일반 push한다(force push 없음).
main 검증 결과와 revert SHA도 보고서·PR 본문에 반영한다. 병합 큐 대기와 main 검증 실패는 종료 코드 1이다.
마무리 상태는 `run/state.json`에 남겨 중단 뒤 다시 실행해도 중복 병합·revert를 피한다.
마지막 출력은 세 줄 요약(티켓 결과, 마무리 결과, 보고서·남은 지적)과 PR 링크다.
실행 흔적은 `.work/<feature>/run/`(gitignore): `NN/<시도>/brief.md`, `run.sh`, `worker.log`, `verify.log`, `wt/`.

실패 처리(07): worker의 로그 출력도 새 커밋도 없이 spec의 `idle_minutes`(기본 20분)가 지나면 프로세스와
pane을 끝낸다. 종료 코드, 커밋 없음, 시간 초과, 검증 실패, 병합 충돌은 같은 모델로 한 번 재시도한다.
매번 최신 integration에서 새 브랜치·worktree(`NN-retry-<번호>`)를 만들고, 새 `claude -p --model opus` 호출이
요약한 실패 로그를 brief에 붙인다. 요약 호출이 실패하면 증거 파일 경로를 붙여 재시도한다.
두 번째 실패는 `failed`, 여기에 직접·간접으로 막힌 티켓은 `skipped`로 두고 나머지는 계속한다.
실패 worktree는 삭제하지 않는다. state의 `failed_worktrees`에 경로를 보존하며, 시도별 `failure.log`,
`failure-summary.md`, 검증·충돌 로그도 남긴다.

리뷰(06): worker가 성공하면 병합 전에 티켓의 `reviewer`(구현 `model`과 다른 계열, 같으면 거부)가 그 티켓 diff
(최신 integration과의 merge-base 기준)를 읽기 전용으로 리뷰한다. reviewer에게는 diff·티켓·spec 경로를 주고, 답은 고정된
JSON(`{"findings": [{"severity": "high|medium|low", "location", "claim", "evidence"}]}`)이다. 새 `claude -p --model opus`
(판단 모델, 파일 경로만 받는다)가 지적마다 fix·report를 정한다. 근거(evidence)가 빈 지적은 늘 report다(코드 규칙).
fix가 있으면 같은 구현 모델로 수정 worker를 같은 브랜치에 한 번 띄운다(지적을 brief에 붙인다). 재리뷰는 없고 verify만 돈다.
수정 worker가 실패하면 수정 커밋을 버리고 리뷰한 구현을 병합·검증한다(티켓 실패로 세지 않는다). reviewer·판단 모델
호출이 실패해도 티켓은 그대로 간다(관문은 verify). 기록은 state의 `review`(지적, fix 여부, 메모)와 시도 디렉터리의
`review/`(diff, 프롬프트, 답), `fix/`(수정 worker)에 남는다. 고치지 않은 지적이 보고서(08)의 남은 지적이다.

상태(03): `run/state.json`이 상태의 원천이다. 티켓별 상태(pending, running, merged, failed, skipped), 시도 횟수,
브랜치, pane, 시작·끝 시각, 로그 경로, 실패 이유. 쓰기는 임시 파일 뒤 rename(원자적). `gs go`의 요약·PR 본문과
`gs status`가 모두 이 파일을 읽는다(마지막 출력 시각은 worker 로그의 수정 시각).
다시 실행하면 integration에 병합된 티켓은 건너뛰고, 실패·건너뜀 티켓은 다시 한다. 지난 `gs`가 죽어 running으로 남은
티켓은 실패로 세지 않고(시도 횟수에서 뺀다) 새로 시작한다. 같은 feature에 `gs go`는 하나만 돈다: `run/lock`에 flock을
잡고 pid를 적는다. 프로세스가 죽으면 커널이 잠금을 풀어 저절로 회수된다.

바꿔 끼우는 곳(시험 seam): `GS_RUNNER=subprocess|herdr`(기본: herdr 안이면 herdr), `GS_WORKER_CMD`(worker 셸 명령,
어댑터를 건너뛴다), `GS_GH`(gh 경로), `GS_AGY`(agy 경로), `GS_JUDGE`(실패 요약·리뷰 분류·보고서용 Claude CLI 경로),
`GS_REVIEWER_CMD`(reviewer 셸 명령: stdin = 프롬프트, stdout = JSON 답).

## 모델 어댑터(05)
`src/gs/adapters.py`. 어댑터마다 같은 입력(brief, worktree, 로그 경로)을 받아 준비(`prepare`), 환경(`env`, 모두
`GS_ROLE=worker`), 셸 명령(`command`), 종료 판정(`outcome`)을 한다. 실행 스크립트가 명령을 감싸 로그와 exit 파일을 남긴다.

| model | 명령 | 차단 장치 |
|---|---|---|
| claude | `claude -p --output-format stream-json --permission-mode bypassPermissions --disallowedTools … < brief` | plugin hook(09) + 도구 차단 |
| codex | `codex exec --json -s workspace-write -c sandbox_workspace_write.network_access=false -C <wt> --add-dir … "<안내>" < brief` | sandbox(네트워크 꺼짐, worktree 밖 쓰기 불가) |
| agy | `agy -p "$(cat brief)" --output-format stream-json --dangerously-skip-permissions --disable-slash-commands --settings '<deny 규칙>' --model gemini-4-argon-high` | deny 규칙 + `gs hook agy-pretooluse`(두 겹) |

- codex: worktree의 git 디렉터리는 주 레포 `.git/` 아래라 sandbox 밖이다. 그대로면 커밋이 `index.lock: Operation not
  permitted`로 실패하고, `.git` 전체를 `--add-dir`해도 codex가 막는다. 그래서 이 worktree의 git 디렉터리, `objects`, 이
  브랜치의 ref·reflog 디렉터리만 연다. sandbox에서 못 도는 시험(localhost 등, ORIGINS 실패 13)은 멈추지 말고 커밋하라는
  안내를 brief 앞에 붙인다. 검증은 어차피 gs가 sandbox 밖에서 다시 돌린다.
- agy(docs/research/agy.md §6): `--mode auto`, `--sandbox`, `--print-timeout`은 넣지 않는다. hook은 worktree의
  `.agents/hooks.json`에 쓰고 git exclude(`/.agents/hooks.json`)에 넣는다. 전역 agy 설정은 건드리지 않는다. hook 명령은
  지금 도는 gs와 같은 python(`<python> -m gs.cli hook agy-pretooluse`)이다. agy 입력(`toolCall`)을 09의 판정으로 바꾸고
  stdout JSON(`{"decision":"deny","reason":…}`)으로 답한다. `lastUserInput`(프롬프트)은 보지 않는다. worktree의 `.agents/`를
  바꾸거나 읽는 일도 막는다.
  띄우기 전에 `agy -p /hooks`(모델 호출 없음)에 gs hook 줄이 있는지, hook 명령이 실제로 `git push`를 막는지 확인한다.
  둘 중 하나라도 아니면 그 티켓을 실패로 적고 worker를 띄우지 않는다. `gs check`도 범위에 agy 티켓이 있으면 같은 확인을
  버리는 디렉터리에서 해서, 안 되면 경고한다.
  종료 0은 성공이 아니다. 성공은 종료 0 + 마지막 `result` 이벤트의 `status: SUCCESS` + `finished_reason` 없음이다.
  `warning:` 줄(모드 무시 같은 조용한 강등), ERROR 단계 수, `denied_actions`는 실패 이유·로그 메모에 붙는다.

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
도구 차단 옵션(`--disallowedTools "Bash(git push *)" "Bash(gh *)"`)도 남겨 둔다(이중 장치). codex는 sandbox, agy는 deny 규칙과
`gs hook agy-pretooluse`로 막는다(위 "모델 어댑터").
