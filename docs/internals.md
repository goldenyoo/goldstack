# goldstack 엔진 명세

`gs`가 안에서 하는 일. 쓰는 법은 [guide.md](guide.md), 첫 화면은 [README](../README.md). 코드는 `src/gs/`, 시험은 `tests/`(`uv run python -m unittest discover -s tests`), plugin은 `.claude-plugin/`·`hooks/`·`skills/`.

| 파일 | 하는 일 |
|---|---|
| `cli.py` | `gs` 명령줄: `self-update`, `init`, `doctor`, `config`, `migrate`, `check`, `go`(여러 feature 연속 실행 포함), `clean`, `status`, `backlog`, `feedback`, `hook` |
| `config.py` | `.goldstack/config.toml` 읽기·검사, `local.env` 읽기, `gs init` |
| `selfupdate.py` | CLI 재설치·플러그인 갱신, 머신 프로세스 검사와 결과 요약 |
| `version.py` | 설치 버전·VCS 출처·플러그인 조회, main 비교 경고, 레포 최소 버전 비교 |
| `doctor.py` | `gs doctor`: GitHub 병합·보호 설정 읽기, config 제안, `--write` |
| `feature.py`, `frontmatter.py`, `graph.py`, `check.py` | spec·티켓 읽기, 그래프(순환, 없는 id, 위상 순서, frontier), `touches` 겹침, agy 배정 수, 환경 검사 |
| `go.py` | `gs go` 코디네이터: 병렬 루프, 병합·검증, 재시도, 리뷰·수정·재리뷰 띄우기(두 리뷰 동시), agy 호출 세기, 재개 뒤 멈춤, 요약 출력, 알림 |
| `worker.py`, `herdr.py`, `adapters.py`, `streamfmt.py` | worker 띄우기(brief, 실행 스크립트, push 차단), herdr pane, 모델별 명령·판정, pane 출력 정리 |
| `review.py` | 다른 계열 리뷰, 판단 모델의 fix·report 분류, 수정 커밋 재리뷰 |
| `transient.py` | 일시 오류 판별, 대기 일정(`Backoff`), 중단 예외(`NetworkAbort`), codex `Reconnecting` 감시 |
| `verify.py`, `setup.py`, `failure.py` | verify 명령(시간 제한, 프로세스 그룹, 재시도), worktree 준비 명령, 실패 증거와 요약 |
| `finish.py`, `report.py` | 보고서, PR, CI 대기, 병합 확인(merge·squash), base 재검증, revert, 보호된 base의 PR |
| `state.py`, `status.py` | `state.json`, 잠금, 단계 시각, 진행 계산(ETA 이력 포함), `gs status` |
| `metrics.py` | 판정과 분리한 실행·검증·리뷰·마무리 측정, 설치본 메타데이터 |
| `clean.py` | `gs clean`, verified 뒤 integration 자동 정리 |
| `feedback.py` | 가린 초안 저장·전송, gh 실패 재시도, 하루 한도·지문 중복 댓글, `gs feedback` |
| `notify.py` | 텔레그램 전송 |
| `hook.py`, `hook_agy.py` | worker 차단 판정(Claude Code, agy) |
| `migrate.py` | `gs migrate` |
| `backlog.py` | `gs backlog`: 아이디어 파일 읽기·검사, 범위 밖 다시 볼 조건 |
| `git.py` | git 호출, 원격 URL에서 GitHub owner/repo 풀기(`github_repo`), push 전 설정 대조(`push_settings`, `check_push`, `push`) |

`gs go`(`cli.cmd_go`)·`gs doctor`는 시작할 때 설치 배포판의 `direct_url.json`에서 git URL·commit을 읽는다. 로컬 디렉터리 설치는 출처가 없다. `git ls-remote <설치 URL> main`(5초 제한)의 main commit이 다르면 `gs self-update` 경고만 내고, 조회 실패·출처 없음은 건너뛴다. `claude plugin list --json`(`GS_CLAUDE`)에서 goldstack 플러그인 버전이 gs 버전과 달라도 경고하며, 목록을 못 읽으면 건너뛴다. 대상 레포의 원격 주소는 설치 출처로 쓰지 않는다.

`gs self-update`는 설치 기록의 git 주소(또는 `--from`)로 main을 재설치한다(`--version`으로 태그 지정). 다른 `gs go` 프로세스가 있거나 프로세스 목록을 읽지 못하면 변경 전에 거부한다. machine-wide-lock은 없으므로 확인 직후 시작되는 `gs go`까지 막지 못한다. CLI 성공 뒤 marketplace와 플러그인을 갱신하며, 플러그인 실패도 CLI 결과와 함께 보고하고 종료 1이다. CHANGELOG는 wheel에 포함해 설치본에서 읽는다.


선택 설정 `[goldstack] requires = ">=0.1"`은 최소 버전 하나(숫자 1–3부분)를 받는다. 형식 오류는 config 오류이며, `gs check`·`gs go`는 설치 버전이 낮으면 실행을 거부하고 `gs self-update`를 안내한다. 생략하면 최소 버전 검사를 하지 않는다. 비교 때 `0.1`과 `0.1.0`은 같다.

## 대상 레포의 파일 배치

goldstack은 사용자 머신·레포를 가정하지 않는다. 레포마다 값은 대상 레포 안의 파일에 두고, 비어 있으면 채우라고 안내한다.
```
.goldstack/config.toml          커밋. 레포마다 값(gs init이 쓴다, gs doctor --write가 git 키 셋을 고친다)
.goldstack/profile.md           커밋. 레포 요약(/adopt가 쓴다, /grill·/go가 커밋한다)
.goldstack/local.env            gitignore. 비밀(TG_TOKEN, TG_CHAT_ID)
.goldstack/local.env.example    커밋. 빈 값 + 채우는 법 안내
.goldstack/work/<feature>/      spec.md, tickets/NN-slug.md, report.md (run/은 gitignore)
.goldstack/out-of-scope/        grill이 뺀 개념
.goldstack/ideas/               아이디어 함: <slug>.md 하나씩(아래 "아이디어 함"), README.md는 형식 설명
```
`gs init`이 `.gitignore`에 넣는 줄: `.goldstack/local.env`, `.goldstack/work/*/run/`. 레포 루트는 지금 디렉터리에서 위로 `.git`을 찾는다(`--repo`로 지정 가능). 옛 위치(`.work/`, `.out-of-scope/`, `.ideas/`)는 읽지 않는다. `gs migrate`로 옮긴다.

## 설정

**`config.toml`** — `gs init`이 전부 쓴다. 키·기본값·누가 쓰나는 [guide.md의 표](guide.md#config-키)가 원천이다. 빠진 섹션·키와 형이 틀린 값(문자열·정수·불리언, 불리언은 정수로 받지 않는다)은 오류, 모르는 섹션·키는 경고. 단 옛 config를 위해 `[agy]`, `[worktree]`, `[tiers]`, `git.merge_method`·`direct_push`·`wait_checks`, `models.failure_summary`(없으면 `models.judge`), `timeouts.checks_minutes`·`setup_minutes`·`rereview_minutes`·`checks_grace_seconds`·`network_wait_minutes`는 없으면 기본값으로 읽는다(`config.py` dataclass 기본값). 값 범위도 본다: `timeouts.*`가 0 이하면 오류(`checks_grace_seconds`만 0을 허용하고 음수가 오류), `agy.max_calls_per_run`이 음수면 오류, `models.*`가 비었거나 공백뿐이면 오류(`models.codex`만 빈 값 허용: codex 기본 모델), `git.merge_method`가 `merge`·`squash` 밖이면 오류. `[tiers]`는 중첩 표라 따로 읽는다(`config._load_tiers`): 계열 표에 `small`·`medium`·`large`가 모두 있어야 하고 값은 공백 없는 `"모델"` 또는 `"모델/effort"`, effort는 `low`·`medium`·`high`·`xhigh`·`max`(codex는 `none`·`minimal`도), `review`·`rereview`는 세 등급 중 하나다. 어기면 오류, 모르는 키는 경고. `gs config`는 `tiers.review`·`rereview`만 값 그대로 보이고 칸(`tiers.claude.small`)은 없는 키로 답한다. 없으면 `gs check`·`gs go`·`gs config`·`gs doctor`가 "`gs init`을 먼저" 오류로 멈춘다(내장 기본값으로 돌지 않는다). `gs go`는 시작할 때 한 번 읽어 그 실행의 모든 호출에 쓴다.

`gs config <섹션.키>`는 값 한 줄을 출력한다(불리언은 `true`/`false`). 없는 키는 종료 1. `/go` skill이 `gs config git.base`, `gs config git.remote`로 base를 읽는다.

**`local.env`** — `KEY=value` 줄, `#` 주석. gs는 이 파일만 읽고 `os.environ`은 보지 않는다(원천 하나). 토큰은 출력·로그에 쓰지 않는다. worker 차단 hook이 이 파일 읽기를 막는다.

**spec frontmatter**(feature마다, [guide.md의 표](guide.md#spec-frontmatter-키)) — `feature`(디렉터리 이름과 같아야 한다), `verify`(비어 있지 않은 한 줄 셸 명령)는 필수. 선택: `verify_ticket`(같은 형식), 1 이상 정수 `max_workers`(기본 3)·`idle_minutes`(기본 20)·`verify_minutes`(기본 20), 0 이상 정수 `verify_retries`(기본 0). 그 밖의 키는 경고, 범위 밖·정수 아닌 값은 오류.

**티켓 frontmatter** — `id`, `title`, `blocked_by`(목록, 없으면 `[]`), `model`, `reviewer`가 모두 필요. 파일 이름은 `<id>-`로 시작한다. `model`·`reviewer`는 `claude|codex|agy` 중 하나이고 서로 달라야 한다. `gs check`는 없는 id 참조, 순환, 겹치는 id를 오류로 본다. 그 밖의 키는 경고다. 선택 키 넷(`feature.TICKET_OPTIONAL`):
- `tier`: `small`·`medium`·`large`. 아니면 오류. worker의 등급이고 없으면 `medium`이다(아래 "모델 어댑터"). 계열 표가 없으면 쓰이지 않는다. `/grill`이 적는다(템플릿에 `tier: medium`).
- `touches`: 문자열 목록, 레포 루트 기준 경로(glob 허용). 목록이 아니거나, 빈 값·절대 경로·`..`가 든 값은 오류. 없으면 `[]`이고 겹침 검사에서 빠진다. `/grill`의 티켓 분해 라운드가 적는다(템플릿 `skills/grill/templates/ticket.md`에 `touches: []`).
- `verify`: 비어 있지 않은 한 줄 셸 명령. 아니면 오류. 이 티켓의 검증 명령을 spec의 것 대신 정한다("검증 명령 고르기와 재시도"). 마무리는 영향을 받지 않는다. 템플릿에는 주석으로 있다(필요한 티켓에만).
- `second_reviewer`: `claude|codex|agy` 중 `model`·`reviewer`와 모두 다른 것. 같으면 오류(`리뷰는 다른 계열이어야 한다: reviewer과 second_reviewer가 둘 다 …`). 템플릿에는 없다(필요한 티켓에만).

**`touches` 겹침 검사**(`check.touches_problems`) — 범위 안에서 `touches`가 있는 티켓 쌍마다 본다. 경로를 `/`로 나눠 부분끼리 맞춘다: `*`·`?`·`[…]`는 한 부분, `**`는 0개 이상의 부분. 두 패턴이 함께 맞는 경로가 하나라도 있으면 겹침이다(같은 경로 포함). 순서는 전체 그래프(`--only` 범위 밖 포함)에서 `blocked_by`를 따라간 조상 집합으로 본다: 한쪽이 다른 쪽의 조상이면 순서가 있다. 겹치는데 순서가 없으면 쌍마다 겹친 경로 하나로 경고 `<a>·<b>가 <경로>를 함께 건드리는데 순서가 없다`. 경고라 `gs go`를 막지 않는다.

**`gs check`의 환경 검사** — `git`, `gh`, `claude`(판단 모델은 티켓 모델과 무관하게 늘 claude다)와 범위 안 티켓의 `model`·`reviewer`·`second_reviewer` CLI가 PATH에 없으면 오류. 범위 안 agy 배정(`model`·`reviewer`·`second_reviewer` 중 agy인 것, 티켓마다 첫 호출만)이 `agy.max_calls_per_run`을 넘으면 경고 `범위 안 agy 배정 <n>회가 상한 agy.max_calls_per_run=<m>회를 넘는다`. 범위 안 티켓 `model`의 계열에 등급표가 없으면 경고 ``` `tiers.<계열>` 표가 없다. 모델·effort가 사용자 설정을 따른다```(reviewer 계열만 쓰는 표는 보지 않는다). `git.remote`의 URL에서 GitHub owner/repo를 풀지 못하면 오류(``원격 `origin`의 URL `…`은 GitHub 저장소 형식이 아니다``). `https://github.com/o/r`, `git@github.com:o/r`, `ssh://git@github.com/o/r` 꼴을 받고 `.git` 접미사는 대소문자 없이 뗀다. `git remote get-url`(insteadOf 적용)이 GitHub가 아니면 원격에 직접 설정된 `remote.<이름>.url`을 다시 본다(시험·미러용 insteadOf). 아이디어 파일은 보지 않는다. `notify.telegram`이 켜졌는데 `local.env`에 `TG_TOKEN`·`TG_CHAT_ID`가 없으면 경고. 범위에 agy 구현 티켓이 있으면 버리는 디렉터리에서 agy 차단 장치를 확인해 안 되면 경고(아래 "모델 어댑터"). `gs go`는 같은 검사를 먼저 하고 오류가 있으면 아무것도 띄우지 않는다.

**`gs doctor [--write]`**(`doctor.py`) — config를 읽고(없으면 종료 1), `git.remote`의 URL에서 푼 저장소를 `gh api`로 읽는다(`GS_GH`, 한 호출 20초). 못 읽은 항목은 `모름(<이유>)`이고 제안이 없으며 종료 코드는 0이다. `gs init` 끝에 `--write` 없이 한 번 돈다.
- **병합 방식**: `repos/<o>/<r>`의 `allow_merge_commit`, `allow_squash_merge`. merge가 켜져 있으면 `merge`, 아니면 squash가 켜져 있으면 `squash`, 둘 다 꺼져 있으면 경고(제안 없음).
- **보호**: `repos/<o>/<r>/branches/<base>/protection`(관리자 권한 필요). 못 읽으면 `repos/<o>/<r>/rules/branches/<base>`(rulesets). rulesets는 확인한 양의 사실만 쓴다: 규칙이 없으면 보호가 없다고 단정하지 않고 `모름`이다. 직접 push 금지로 치는 것: 필수 리뷰, push 제한(restrictions), branch lock, 필수 검사, 필수 서명(새 revert·보고서 커밋이 통과할 수 없다). code owner 리뷰나 last-push 승인이 켜져 있으면 승인은 최소 1명이다. 필수 검사가 있으면 `wait_checks = true`를 제안한다.
- **검증**: `.goldstack/work/*/spec.md`마다 `verify`를 읽어 없거나 `true`·`:`면 경고. 경고일 뿐 `gs check`는 막지 않는다.
- **setup**: `worktree.setup`의 명령 중 `npm install`·`npm i`, 또는 `--frozen-lockfile`·`--immutable` 없는 `yarn`(`yarn`, `yarn install`, `yarn --…`)이 있으면 `setup  lockfile을 바꾸지 않는 명령 권장: npm ci · yarn --frozen-lockfile · uv sync --locked`를 더한다. 제안 키가 없어 `--write`는 고치지 않는다. `/adopt`도 같은 것을 권한다.
- **`--write`**: 제안한 키(`git.merge_method`, `git.direct_push`, `git.wait_checks`)만 값이 다를 때 고치고 `git.<키>: <전> → <후> (<이유>)`를 쓴다. 후보 위치를 TOML 전체 파싱 결과가 원하는 한 키만 바뀌는지로 확인해 다른 줄·주석을 그대로 둔다. 그렇게 고칠 수 없는 형식이면 `오류: config를 쓸 수 없다: …`, 종료 1. `모름`·제안 없음은 쓰지 않는다.

## `gs go`의 흐름

1. 검사 → 잠금(`run/lock`) → `git fetch <remote> <base>`.
2. `.goldstack/work/<f>/spec.md`와 `tickets/`가 커밋돼 있고 `<remote>/<base>`와 같은지 본다. 다르면 시작하지 않는다(worker는 `<remote>/<base>` 기준으로 일한다). `report.md`는 보지 않는다.
3. state를 읽어 실행을 시작하고, integration worktree(`run/wt/integration`, 브랜치 `gs/<f>/integration`)를 준비한다: 남은 병합·변경을 버리고 `<remote>/<base>`를 합친 뒤, `[worktree] setup`이 있으면 처음 한 번 돌린다(아래 "준비 실패 위치별 처리").
4. integration의 병합 표시(`gs-ticket: <f>/<NN>` 트레일러)로 이미 병합된 티켓을 회복한다. 지난 마무리가 CI 대기(`checks_*`), PR 병합 대기, gs PR 대기(`revert_pending`·`report_pending`), 병합 뒤, base 미검증, main 검증 실패에서 멈췄거나(`finish.RESUME_PHASES`), `verified`·`reverted`인데 base 보고서를 아직 시도하지 않았으면(`go._resuming`) 새 worker를 띄우기 전에 그것부터 이어 가고 그 실행은 멈춘다(아래 "재개는 멈춘다").
5. 이어 갈 마무리가 없으면 티켓 루프(병렬, 리뷰, 재시도) → 마무리(보고서, PR, 병합, base 재검증).
6. `finished_at` 기록 → 요약 출력 → 알림.

종료 코드는 모든 티켓이 병합되고 마무리가 끝났을 때(base 검증 통과, gs PR 대기 없음)만 0이다. 병합 대기, CI 실패·시간 초과, 승인 대기, 준비 실패, base 검증 실패, 재개 뒤 남은 티켓도 1이다. `중단(네트워크)`만 3이다(아래 "네트워크 끊김").

**여러 feature(`gs go a b …`, `cli.cmd_go`)** — 먼저 feature마다 `gs check`를 하고 하나라도 오류면 아무것도 시작하지 않는다(종료 1). 그 뒤 같은 프로세스에서 feature마다 `go.go()`를 차례로 부르고, 끝날 때마다 state.json의 `finish.phase`를 다시 읽는다. 종료 코드가 0이고 phase가 `verified`일 때만 `■ <a>: verified → <b> 시작`을 쓰고 다음으로 간다. 아니면 `■ <a>: <phase> → 여기서 멈춤(남은: <b> …)`을 쓰고 그 종료 코드로 끝난다(state를 못 읽으면 phase `unknown`, 종료 1. `network.aborted`가 있으면 지난 마무리 phase와 상관없이 phase 자리가 `중단(네트워크)`, 종료 3). 시작 전 거부(잠금, 미커밋 spec)는 종료 코드가 1이라 지난 실행의 `verified`가 state에 남아 있어도 멈춘다. `--only`와 함께 쓰면 argparse 오류다. 실행 중 gs를 다시 설치하지 않으므로, 앞 feature가 gs를 고쳐도 뒤 feature는 프로세스가 시작할 때 실린 gs로 돈다(spec 결정: 이어 받을 때 `uv tool install --reinstall .`은 사람·세션이 한다). `/go a b`는 feature마다 check·커밋·push를 한 뒤 이 명령을 한 번 띄운다.

## 상태

`run/state.json`이 상태의 원천이다. `gs go`의 요약·보고서·PR 본문·알림, `gs status`, 진행 바 mod가 모두 이 파일을 읽는다. 쓰기는 같은 디렉터리의 임시 파일 뒤 rename(원자적)이다.
- 위: `feature`, `pid`(마지막으로 쓴 `gs go`), `only`, `started_at`, `updated_at`(heartbeat로 상태가 그대로여도 60초마다 바뀐다), `finished_at`, `phase`(feature 전체 마무리 중이면 `finish`, integration·base worktree 준비 중이면 `setup`), `finish`(마무리 재개 지점: `phase`, `outcome`, `url`, `merge_head`, `merge_method`, `merge_sha`, `revert_sha`, `integration_ok`, `main_ok`, `checks`, `revert_pr`·`revert_head`·`revert_merge`, `report_pr`·`report_head`·`report_merge`·`report_result`, `base_report_tried`, `base_report`, `reintroduced`, `error`, `head` 등), `progress`, `agy_calls`(이번 실행에서 gs가 띄운 agy 호출 수, 실행 시작마다 0), `network`(`errors`·`waited_seconds`는 실행을 넘어 누적, `wait`는 지금의 대기 `{count, due_at}`, `due_at`이 비면 회복 확인 중, `aborted`는 중단 이유. 뒤의 둘은 실행 시작 때 지운다), `metrics`(아래), `push_record`(실행 시작 때의 push 설정, 아래 "마무리"의 "push 전 대조").
- 티켓마다: `status`(`pending`, `running`, `merged`, `failed`, `skipped`), `attempts`, `branch`, `pane`(`pane <id>` 또는 `pid <n>`), `started_at`·`ended_at`, `log`, `reason`, `worktree`, `failures`, `failed_worktrees`, `kept_worktrees`, `isolation_warnings`(플러그인 격리 실패, 지난 시도·수정 worker 것도 남긴다), `failure_summary`, `review`(재리뷰 필드는 아래 "재리뷰"), `second_review`(`second_reviewer`가 있을 때 두 번째 리뷰 기록, 모양은 `review`와 같다), `phases`, `transient_errors`·`network_wait_seconds`(일시 오류 수·대기 초, `failures`와 따로 누적), `network_resume`(잇는 표시: `branch`, `worktree`, `base`, `fix`, `rundir`, `done`. 아래 "네트워크 끊김").
- `phases`: 단계 전환마다 `{attempt, phase, model, started_at, ended_at}`를 더한다. worker·수정 단계에는 `tier`, `actual_model`, `effort`도 있다. phase는 `setup`, `worker`, `review`, `fix`, `rereview`(model은 `codex+agy`처럼 리뷰어들), `fix2`, `network`(네트워크 대기), `verify`, `finish`(티켓을 integration에 커밋하는 순간). ETA 표본은 이 단계들을 포함한 티켓 전체 시간이다. 보고서의 단계별 소요가 이것을 합산한다(지난 시도 포함). 분으로 반올림해 0분인 단계(대개 순간인 `finish`)는 줄에서 빼고, 모두 0분이면 `모두 1분 미만`이다.
- `metrics`(선택, `metrics.py`): 재개·재시도에도 남기는 목록들이다. `runtime`은 실행별 gs 버전·설치 commit(`direct_url.json`의 VCS 기록이 있을 때만), `workers`는 구현·수정·네트워크 재시작별 실행 디렉터리·실제 모델/effort·`exit` mtime(`worker_exited_at`)·첫 처리 시작(`processing_started_at`)·실행 초·처리 대기 초다. `validations`는 gs가 돌린 검증의 재시도마다 라벨·명령·HEAD SHA·초·종료 코드·시간 초과·결과·트리 변경 여부를 남긴다. 티켓의 미완 병합에는 `merge_head`와 `tree_sha`도 남겨 검증한 병합 트리를 구별한다. 보고서만 바뀌어 건너뛴 검증은 호출 기록을 만들지 않는다.
- `metrics.reviewers`는 첫 리뷰·재리뷰별 모델/effort·전체 소요(판단·네트워크 대기 포함)·새 지적 수·채택(fix) 수다. 채택 수는 해결 수가 아니며, 재리뷰가 기존 지적을 다시 확인한 것은 새 채택으로 세지 않는다. 각 `review`·`rereviews`에도 `seconds`, `findings_count`, `fix_count`가 있다. `review_calls`는 실제 리뷰어 재호출마다 모델/effort·호출 시간·성공/오류를 남겨 중단된 호출도 보존한다(판단·대기 제외). `finish_stages`는 마무리 단계별 벽시계 시작/끝과 monotonic 초다. `total`, `postmerge`, `sync-integration` 같은 상위 단계는 하위 단계를 포함하므로 모두 더하면 안 된다. 보고서는 생성 시점의 요약이며 진행 중 단계는 그때까지의 경과다. 빈 모델·effort는 CLI 기본값이고, 설치 기록이 없는 commit은 추측하지 않는다.
- 보고서 Evidence의 `### 실행 측정`(`report.measurements`)이 이 목록과 일시 오류 수·대기 초를 전체·티켓별로 보인다. worker 표의 처리 대기는 worker가 끝난 뒤 gs가 처리를 시작하기까지다(`_loop`가 리뷰·검증을 하는 동안 다른 worker가 기다린 시간).
- 측정은 판정과 분리한다. 측정 시계·설치 메타데이터·기록·추가 저장·보고서 측정 요약의 오류는 측정만 잃고 원래 작업의 반환값·예외·검증/병합 판단을 유지한다. 이 선택 필드가 없는 옛 state도 `go`·`status`가 그대로 읽는다.
- 재개할 때 미완 `finish_stages`는 지난 `updated_at`까지의 시간으로 닫고 `interrupted`를 남긴다. 보고서는 이 시간을 실제 소요의 하한으로 표시해 중단 기간을 더하지 않는다. 측정이 없던 옛 worker는 실행 디렉터리에 맞는 `phases`에서 단계·시도·모델을 복구하고, 시작 시각과 실행 초는 알 수 없으므로 보고서에 `기록 없음`으로 표시한다.

다시 실행하면 integration에 병합된 티켓은 건너뛰고, 실패·건너뜀 티켓은 `failures`·요약·이유를 비우고 다시 한다. `중단(네트워크)`로 대기에 둔 티켓은 `failures`를 그대로 두고 `network_resume`으로 잇는다. state는 merged인데 integration에 표시가 없으면 다시 한다. 지난 `gs`가 죽어 `running`으로 남은 티켓은 실패로 세지 않고(`attempts`에서 하나 뺀다) 새로 시작한다. 그 시도의 worker가 살아 있으면(명령줄에 그 시도의 `run.sh`가 있는 프로세스) 먼저 끝내고 herdr pane도 닫는다.

같은 feature에 `gs go`는 하나만 돈다: `run/lock`에 flock을 잡고 pid를 적는다. 프로세스가 죽으면 커널이 잠금을 풀어 저절로 회수된다. "돌고 있나"는 적힌 pid가 아니라 잠금이 실제로 잡혔는지로 판단한다(`gs status`는 공유 잠금을 잠깐 잡아 본다).

`gs status [<feature>]`는 읽기 전용이다. 표의 경과는 티켓 시작부터(끝났으면 끝까지, 돌고 있으면 지금까지), 마지막 출력은 worker 로그의 수정 시각이다. 표 아래에 `progress.line`을 보인다.

## 병렬 실행

frontier(대기 중이고 막는 티켓이 모두 병합된 것)를 spec의 `max_workers`개까지 위상 순서대로 띄운다. worker 하나가 끝날 때마다 state에서 frontier를 다시 계산해 빈자리를 채운다. `max_workers: 1`이면 위상 순서로 하나씩 돈다. `--only`면 그 부분 그래프만 돌고, 범위 밖 의존은 끝났다고 본다.

- worker마다 최신 integration 끝에서 브랜치 `gs/<f>/<NN>`과 worktree `run/wt/<NN>`을 만들고, `[worktree] setup`이 있으면 worker 전에 돌린다. 재시도는 `gs/<f>/<NN>-retry-<k>`, `run/wt/<NN>-retry-<k>`. 번호는 시도 디렉터리 `run/<NN>/<시도>`로 정한다.
- herdr 안이면(`HERDR_SOCKET_PATH`·`HERDR_SESSION`) 지금 workspace(없으면 새 workspace `gs:<f>`)의 탭 `gs:<f>`에 worker마다 새 pane을 연다. 성공한 pane은 닫고 실패한 pane은 남긴다. herdr 밖이면 subprocess로 돈다.
- 루프는 스레드 하나다. 리뷰·병합·검증은 이 루프에서 한 번에 하나씩 한다(다른 worker는 그동안 각자 돈다).
- 병합: 먼저 최신 integration 끝을 티켓 브랜치에 합쳐 본다(충돌이면 이유 `conflict`). 그다음 integration에 `--no-ff --no-commit`으로 합치고(충돌이면 `integration 병합 충돌`) 이 미완 병합 트리에서 티켓 검증을 돌려(명령은 티켓 `verify` → spec `verify_ticket` → spec `verify`), 통과하고 검증이 트리를 바꾸지 않았고 그 사이 integration이 바뀌지 않았을 때만 `Merge <NN>: <title>` + 트레일러 `gs-ticket: <f>/<NN>` 커밋을 만든다. 중간에 죽으면 표시 없는 미완 병합만 남고 다음 실행이 버린다.
- worker가 integration worktree를 건드렸으면 되돌린다. 그때 돌던 worker가 그것 하나면 그 티켓의 실패, 여럿이면 누구 짓인지 몰라 경고만 한다.

## 실패 처리

- **일시 오류는 실패가 아니다**: worker가 연결·DNS·5xx·429로 끝나면 아래 어느 것도 하지 않고 기다렸다 같은 worktree에서 잇는다(아래 "네트워크 끊김").
- **멈춤**: worker의 로그 출력도 브랜치의 새 커밋도 없이 spec의 `idle_minutes`가 지나면 프로세스와 pane을 끝낸다(`시간 초과: <N>분 동안 로그 출력·새 커밋 없음`). 이것은 일시 오류로 치지 않고 실패다.
- **verify 시간 제한**: 티켓 병합 전, `integration`, `integration-final`, `integration-recheck`, `main`, `main-recheck` 검증이 모두 `verify.py`를 쓴다. `verify_retries`가 있으면 시간 초과도 그만큼 다시 돈 뒤의 결과다. 명령은 새 프로세스 그룹에서 `bash -c`로 돈다. 제한은 `GS_VERIFY_TIMEOUT`(초)이 있으면 그것, 없으면 spec `verify_minutes`. 넘기면 그룹 전체에 SIGTERM, 5초 뒤 남았으면 SIGKILL을 보내 자손까지 끝내고, 로그 끝에 `시간 초과: <N>분`을 남겨 검증 실패로 친다: 티켓이면 `검증 시간 초과(<N>분, 로그 <경로>)`로 재시도, integration이면 병합 안 함, base면 병합 커밋 revert.
- **재시도**: 티켓 실패(종료 코드, 커밋 없음, 멈춤, 검증 실패(시간 초과 포함), 병합 충돌, 띄우기 실패 등)는 같은 계열에서 한 등급 올려 한 번 재시도한다(등급표가 없으면 기존 모델 선택 유지). `준비 실패`와 `agy 한도`만 재시도 없이 바로 실패다. 최신 integration에서 새 브랜치·worktree를 만들고, 새 호출(`models.failure_summary`, 제한 `timeouts.summary_seconds`)이 요약한 실패 로그(`failure-summary.md`)를 brief에 붙인다. 요약 호출이 실패하면(끊긴 채 대기 상한을 넘겨도) 증거 파일 경로를 붙인다. 실패 횟수는 요약 호출 전에 state에 적어 중간에 죽어도 재시도 한도가 늘지 않는다.
- 두 번째 실패는 `failed`, 그 티켓에 직접·간접으로 막힌 티켓은 `skipped`(`막힘: <id>`)로 두고 나머지는 계속한다.
- 증거: 시도마다 `failure.log`(이유 + worker·verify·merge 로그 끝 64KiB), `failure-summary.md`, `judge.log`. 실패 worktree는 지우지 않고 `failed_worktrees`에 남긴다.
- 한 티켓의 준비·확인·병합 중 오류(git, herdr, 파일, 어댑터)는 그 티켓의 실패로 한정한다. 예상 못 한 오류로 루프를 떠나도 띄운 worker를 끝낸다.

**worktree 정리** — 티켓이 integration에 병합되면 성공한 시도의 worktree를 바로 지우고(기억한 setup 산출물만 먼저 지운 뒤 `--force` 없이) `[NN] worktree 정리: <경로>`를 출력한다. 로컬 티켓 브랜치는 끝이 integration에 포함될 때만(`merge-base --is-ancestor`) 지우고, 아니면 경고하고 남긴다. 병합된 worktree에 미커밋 변경이 있으면 worktree·브랜치를 모두 남기고 `kept_worktrees`에 적으며 보고서 티켓 결과에 `남긴 worktree: <경로> (미커밋 변경)`을 표시한다. 재시작 때도 이미 병합된 티켓의 남은 worktree·브랜치를 같은 규칙으로 정리한다. `kept_worktrees`의 옛 경로는 티켓이 다시 대기로 돌아가거나 새 시도를 띄울 때 다시 본다: 경로가 없거나 미커밋 변경이 없어졌으면 worktree를 정리하고 목록에서 뺀다. 그 worktree의 실제 브랜치가 티켓 브랜치와 다르면(분리 HEAD 포함. 사람이 거기서 커밋했을 수 있다) 경고하고 남긴다. 브랜치는 끝이 integration에 있을 때만 지운다. `--only` 범위 밖 티켓이 남긴 worktree도 보고서 티켓별 결과 아래 `범위 밖 티켓의 남긴 worktree:`에 나온다. 실패한 시도의 worktree·브랜치는 남긴다(`gs clean`이 지운다). integration worktree와 로컬·원격 integration 브랜치는 마무리가 `verified`일 때만 자동으로 지운다(아래 "자동 정리"). 정리 오류는 경고만 하고 티켓의 merged 상태를 바꾸지 않는다.

## 리뷰

worker가 성공하면 병합 전에 티켓의 `reviewer`(있으면 `second_reviewer`도)가 그 티켓 diff(최신 integration과의 merge-base 기준)를 읽기 전용으로 리뷰한다. 리뷰가 하나인데 구현 `model`과 같은 계열이면 부르지 않고 그 티켓을 실패시킨다.
1. reviewer에게 diff·티켓·spec·worktree 경로를 준다. 지시문은 전체 시험 대신 지적을 확인할 좁은 재현만 돌리라고 한다(재리뷰도 같다). 답은 고정 JSON `{"findings": [{"severity": "high|medium|low", "location", "claim", "evidence"}]}`. 시간 제한 `timeouts.review_minutes`.
2. 새 판단 모델 호출(`models.judge`, 파일 경로만 받는다, 제한 `timeouts.judge_minutes`)이 지적마다 `fix`·`report`를 정한다. 근거(evidence)가 빈 지적은 늘 `report`다(코드 규칙: 취향은 고치지 않는다). 판단 모델이 실패하면 모두 `report`.
3. `fix`가 있으면 같은 구현 모델로 수정 worker를 같은 브랜치·worktree에 띄운다(지적을 brief 끝에 붙인다). 커밋하면 재리뷰로 간다(아래). 수정 worker가 실패하면(종료 코드, 멈춤, 커밋 없음, 이전 커밋을 지움) 이번 수정 커밋만 버리고 수정 전 head로 되돌려 병합·검증한다. 재리뷰하지 않고 티켓 실패로 세지 않는다.
4. reviewer·재리뷰·판단 모델 호출이 실패하거나 답의 형식이 틀려도 티켓은 그대로 간다(병합 관문은 verify). 그 사실은 리뷰 기록의 `note`나 지적의 `rereview_reason`에 남는다. 일시 오류·시간 초과는 실패가 아니다: 기다렸다 다시 부르고, 대기 상한을 넘기면 `중단(네트워크)`다("리뷰·판단 호출의 대기").

기록은 state의 `review`(`reviewer`, `dir`, `merge_base`, `reviewed_head`, `note`, `fix`, `rereviews`, `findings`, 호출 때의 `tier`·`actual_model`·`effort`), 두 번째 리뷰는 `second_review`, 그리고 시도 디렉터리의 `review/`(두 번째 리뷰는 `review-<계열>/`, 예 `review-agy/`)(`diff.patch`, `prompt.md`, `review.txt`, `reviewer.log`, `findings.json`, `judge-prompt.md`, `judge.txt`, `judge.log`), `fix/`·`fix2/`(수정 worker), `rereview<회차>-<계열>/`(재리뷰). 병합 전 대조로 다시 부르면 디렉터리 이름에 `-again`이 붙어 앞 증거가 남는다.

**읽는 트리**(`go._review_tree`) — 첫 리뷰와 재리뷰가 같은 규칙을 쓴다. 티켓 worktree가 대상 head 그대로이고 깨끗하면(setup 산출물 제외) 그곳이다. 미커밋 변경이 있거나 다른 곳으로 옮겨 갔으면 임시 worktree `run/gs-review-*/wt`(재리뷰는 `run/gs-rereview-*/wt`)다. 판단 모델도 같은 트리에서 돈다. 병합되지 않을 코드를 근거로 지적을 기각하거나 `resolved`로 확인하지 않게 한다. 티켓 worktree의 변경은 지우지 않는다. 트리를 못 만들면 아무도 부르지 않는다(agy 호출로 세지 않는다): 첫 리뷰는 리뷰 실패(`note`)로 적고 verify만으로 병합하고, 재리뷰는 `unchecked`(`재리뷰 실패`)다. 치우기 실패는 경고뿐이다.

**병합 전 대조**(`go._review_to_head`, `go._moved_head`) — 리뷰·재리뷰가 끝날 때마다 티켓 head를 리뷰 기록의 `reviewed_head`와 비교한다. 살아 남은 자손이 리뷰 중에 커밋한 경우 같은, 아무 리뷰어도 보지 않은 head가 병합되지 않게 한다.
- `reviewed_head`: 이 리뷰어를 부른 마지막 리뷰·재리뷰의 대상 head. 호출이 실패해도 옮긴다(실패는 `note`·`failed`가 말한다). 수정 커밋 diff가 비어 부르지 않은 재리뷰도 그 head로 옮긴다. 부르지 못했으면(거부, 한도, 트리 실패) 옮기지 않는다. 옛 state의 기록에는 없고, 값이 하나도 없으면 대조하지 않는다.
- 리뷰가 둘이면 어느 한쪽이 본 head면 같다(재리뷰는 지적을 낸 리뷰어만 부른다).
- 다르면 한 번 다시 부른다. 수정 전이면 `_review`(티켓 diff 전체, 새 기록이 앞 기록을 대신한다. 답을 못 받았으면 앞 지적을 남기고 `note`에 덧붙인다), 수정 뒤면 그 회차의 `_rereview`(수정 worker가 받은 지적, `a.base..head`)다. 고칠 지적이 나오면 평소처럼 수정 worker로 가고 수정 횟수 상한은 그대로다.
- 또 다르면 경고와 기록(`fix`)만 남기고 간다. 리뷰를 깨끗해질 때까지 돌리지 않는다.
- 수정 worker가 실패해 그 수정을 버렸으면 대조하지 않는다. 띄우기 전에 대조한 head로 돌아왔고, 실패한 수정은 재리뷰 없이 병합·검증으로 간다.
- catch-up은 이 뒤라 합친 최신 integration은 worker 변경으로 세지 않는다. 대기 상한을 넘기면 `중단(네트워크)`로 멈추고 `done` 표시로 다음 `gs go`가 잇는다.

**재리뷰**(`go._rereview`, `review.rereview`) — 순서는 구현 → 리뷰 → 수정 → 재리뷰 → (2차 수정 → 재리뷰) → catch-up·verify → 병합이고 verify는 마지막에 한 번이다. 수정은 티켓당 최대 2회, 리뷰를 깨끗해질 때까지 돌리지 않는다.
- **대상**(`review.fix_targets`): 1차는 `fix` 지적 전부. 2차는 1차 재리뷰의 `unresolved`와 1차 재리뷰가 새로 낸 `fix` 지적. `resolved`·`unchecked`는 다시 고치지 않는다. 대상이 있는 리뷰 기록의 리뷰어만 부르고, 둘이면 `review.run_together`로 동시에 띄운다. 각자 자기 지적을 확인하고 새 문제는 부른 리뷰어 모두가 본다.
- **입력**: 수정 커밋 diff `fix.patch`(수정 전 브랜치 head..수정 뒤 head), 그 리뷰어의 지적 `fix-findings.json`, 티켓, spec. 제한은 `timeouts.rereview_minutes`. 답은 고정 JSON `{"verdicts": [{"id", "status": "resolved|unresolved", "evidence"}], "findings": […]}`. 디렉터리에는 `prompt.md`, `review.txt`, `reviewer.log`도 남고, 새 지적을 분류했으면 판단 모델 파일도 남는다.
- **판정**: 답을 못 받으면 그 리뷰어의 지적이 모두 `unchecked`(`재리뷰 실패`)다. 시간 초과와 일시 오류는 다시 부르고, 대기 상한을 넘기면 `중단(네트워크)`다(아래 "리뷰·판단 호출의 대기"). 옛 state에는 이유 `시간 초과`가 남아 있을 수 있다. 판정이 빠졌거나 근거가 빈 지적도 `unchecked`(`재리뷰 실패`)다. 수정 커밋 diff가 비면 부르지 않고 `unresolved`다. 재리뷰 중 어떤 오류도 병합을 막지 않는다.
- **새 지적**: 기록의 `findings` 뒤에 번호를 이어 `found_round`를 적는다. 1차면 판단 모델이 나누고(`fix`면 2차 수정 대상), 2차면 판단 모델을 부르지 않고 `report`다.
- **읽는 트리**: 위 "읽는 트리"의 규칙으로 수정 head를 읽는다.
- **2차 수정을 못 하면**: 띄우지 못했으면(한도 포함) 그대로, 실패하면 이번 수정 커밋만 버리고 1차 수정까지를 병합·검증한다. 2차 재리뷰는 없다.

재리뷰 state 필드:

| 위치 | 필드 | 값 |
|---|---|---|
| 리뷰 기록 | `rereviews` | 회차마다 `round`, `dir`, `base`, `head`, `note`, `failed`(못 했으면 이유), `tier`, `actual_model`, `effort` |
| 리뷰 기록 | `fix` | 수정·재리뷰 경과 메모를 ` / `로 잇는다(`재리뷰 1차: resolved 1 · unresolved 1 · unchecked 0 · 새 지적 1`) |
| 지적 | `fix_attempt` | `""`, `attempted`(수정 worker가 커밋했다), `discarded`(실패해 버렸다) |
| 지적 | `fix_round` | 이 지적을 받은 마지막 수정 회차(0이면 받은 적 없음) |
| 지적 | `fix_reason` | 수정 못 한 이유: `한도`, `띄우지 못함: …`, `수정 worker 실패: …` |
| 지적 | `rereview` | `""`, `resolved`, `unresolved`, `unchecked` |
| 지적 | `rereview_reason` | `unchecked`의 이유: `한도`, `재리뷰 실패`(옛 state는 `시간 초과`도) |
| 지적 | `rereview_evidence` | 판정 근거 또는 재리뷰를 못 한 자세한 내용 |
| 지적 | `rereview_round` | 그 결과를 낸 재리뷰 회차 |
| 지적 | `found_round` | 0 첫 리뷰, 1·2 그 회차 재리뷰가 새로 낸 지적 |

**보고서의 지적 상태**(`report.finding_status`, 위에서부터 먼저 맞는 것): `action`이 `report`이거나 `found_round`가 2면 `보고만` → `rereview`가 `resolved`면 `수정됨(재리뷰 확인)`, `unresolved`면 `미해결`, `unchecked`면 `확인 못 함(<rereview_reason>)` → `fix_reason`이 있으면 `수정 못 함(<fix_reason>)`. 그래서 2차 수정을 못 했거나 버렸어도 1차 재리뷰의 `unresolved`는 `미해결`이다. 재리뷰 도입 전 state는 `수정 못 함(수정 버림)`(`discarded`), `확인 못 함(재리뷰 없음)`(`attempted`), `수정 못 함(수정 기록 없음)`으로 읽는다. 커밋만으로 해결됐다고 보지 않는다. 지적 줄은 `- <NN> 리뷰(<계열>) [<심각도>] <위치>: <주장> — 상태: <상태>`, Summary의 마무리 상태 줄 아래 `리뷰 지적: 수정됨 n · 미해결 n · 보고만 n · 수정 못 함 n · 확인 못 함 n`(`report.finding_counts`, 0개인 상태는 뺀다). 요약·알림의 남은 지적 수(`review.remaining`)는 `resolved`가 아닌 지적 전부다. 판단 모델의 Summary 프롬프트는 수정됨을 남은 위험에 넣지 말고, 수정 커밋만으로 해결됐다고 쓰지 말라고 한다.

**두 리뷰 합치기**(`second_reviewer`, `go._review`) — 두 리뷰를 `review.run_together`로 동시에 띄우고(스레드 둘), 둘 다 끝날 때까지 기다린다. 각자 `timeouts.review_minutes`·`judge_minutes`·`network_wait_minutes` 제한이 있어 한쪽이 무한히 붙잡지 않는다. 판단 모델은 리뷰마다 따로 부른다. 그 뒤:
- 두 기록의 `fix` 지적을 합쳐(`review.labeled_fixes`, 지적 번호가 리뷰마다 1부터라 `codex-1`, `agy-1`처럼 계열을 붙인다) 수정 worker를 **하나** 띄운다. 2차 수정도 같다. 재리뷰는 리뷰어마다 따로다(위).
- 한쪽이 같은 계열이라 거부되거나, 실패·형식 오류·`건너뜀(한도)`이면 그 기록에 `note`만 남기고 다른 쪽 결과로 간다. 시간 초과·일시 오류는 그 리뷰어를 다시 부르고, 대기 상한을 넘기면 다른 쪽 결과를 버리고 `중단(네트워크)`다. 둘 다 거부면 하나일 때처럼 티켓 실패, 띄운 리뷰가 모두 git 오류여도 티켓 실패다.
- 출력은 `[NN] 리뷰: codex+agy`, 리뷰마다 `[NN] 리뷰 끝(<계열>): 지적 n개(fix a, report b)[ — note]`. 보고서 "리뷰 지적"은 리뷰마다 `NN 리뷰(<계열>)`로 나뉜다(`state.reviews`).

**agy 호출 세기**(spec 1-9, 2-5) — gs가 agy를 띄우기 직전에 `state.agy_calls`를 1 올리고 저장한다(`go._count_agy`). 1회 = agy worker 한 번(첫 시도, 재시도, 1·2차 수정 worker, 끊겨서 다시 띄운 worker 각각), agy 리뷰 한 번(첫 리뷰든 두 번째든), agy 재리뷰 한 번(회차마다), 끊겨서 다시 부른 agy 리뷰·재리뷰 한 번 중 하나다. 끊겨서 다시 부르는 리뷰·재리뷰는 상한을 보지 않는다. 끊겨서 다시 띄우는 worker는 상한을 보고, 닿으면 구현은 `agy 한도`로 실패, 수정은 실패한 수정으로 처리한다. 그래서 재시도가 없으면 agy 리뷰어는 티켓 하나에 최대 3회(리뷰 1 + 재리뷰 2), agy 구현도 최대 3회(worker 1 + 수정 2)다. `gs check`의 차단 장치 확인(`agy -p /hooks`, 모델 호출 없음)과 `/retro`의 agy 요약은 세지 않는다. 값은 `gs go`가 실행을 시작할 때(`_begin`) 0으로 돌린다: 상한은 feature 하나의 실행마다다. `agy_calls >= max_calls_per_run`(`state.agy_reached`)이면:
- agy worker: 띄우지 않고 `agy 한도: 이번 실행의 agy 호출이 상한 <n>/<m>에 닿아 worker를 띄우지 않았다(config agy.max_calls_per_run)`로 실패, 재시도 없음(`retry=False`, 다시 해도 같은 이유로 막힌다). 막힌 티켓은 `skipped`.
- agy 리뷰: 띄우지 않고 기록 `note`를 `건너뜀(한도): 이번 실행의 agy 호출이 상한 <n>/<m>에 닿았다`로 둔다. 다른 리뷰가 없으면 verify만으로 병합한다.
- agy 재리뷰: 띄우지 않고 그 리뷰어의 대상 지적을 `unchecked`(이유 `한도`)로 둔다. 보고서 `확인 못 함(한도)`. 다른 리뷰어의 재리뷰는 그대로 돈다.
- agy 수정 worker: 띄우지 않고 지금 브랜치의 구현을 병합·검증한다(1차면 수정 전 구현, 2차면 1차 수정까지. 티켓 실패 아님). 대상 지적에 `fix_reason = 한도`를 남겨 보고서 `수정 못 함(한도)`, 1차 재리뷰의 `unresolved`는 `미해결`이다.
`gs check`는 이 상한을 실행 전에 어림한다: 티켓마다 첫 호출(구현·리뷰·두 번째 리뷰)만 센다. 재시도·수정·재리뷰는 일어날지 몰라 미리 세지 않으므로, 경고가 없어도 실행 중 상한에 닿을 수 있다. 보고서 Evidence 끝에 `agy 사용: <agy_calls>/<상한>`(`report.agy_usage`).

계열 표가 없을 때 reviewer 명령(모두 읽기 전용, worker와 같은 push·gh 차단 환경):

| reviewer | 명령 |
|---|---|
| claude | `claude -p --model <models.claude_review> --output-format json --permission-mode bypassPermissions --tools Read,Grep,Glob` (stdin = 프롬프트) |
| codex | `codex exec --json [--model <models.codex>] -s read-only --skip-git-repo-check -C <wt> --output-last-message <review.txt> -` |
| agy | `agy -p <프롬프트> --sandbox --dangerously-skip-permissions --disable-slash-commands --settings '<deny 규칙>' --model <models.agy>` |

## 네트워크 끊김

코디네이터는 끊김을 실패와 구분한다. 티켓을 잃지 않고, 리뷰 없이 병합하지 않는다. 일시 오류 판별은 아래 "모델 어댑터"의 `transient.reason`이다. 대기 일정(`transient.Backoff`)은 worker와 호출이 함께 쓴다: 1→2→5→10→10…분, 합계 `timeouts.network_wait_minutes`(기본 60), 마지막 간격은 상한에 맞춰 줄인다. 다시 부르는 것이 회복 확인이고 호스트를 따로 찌르지 않는다.

**worker의 대기**(`go.Outage`, `go._net_hold`, `go._net_tick`) — 대기는 sleep이 아니라 `_loop`의 시계다.
1. 판별(`go._transient_end`): worker가 끝났는데 종료 0 + 커밋이 아니면 어댑터의 `transient_reason`을 본다. idle 시간 초과와 확인 오류는 일시 오류가 아니다.
2. 세우기(`_net_hold`): `failures`와 등급을 그대로 두고 `transient_errors`를 올린다. 이유 `네트워크 대기: <이유>`, phase `network`, `network_resume`을 남긴다. 다른 worker가 잡아 둔 대기가 있으면 거기에 함께 탄다. 다음 대기가 없으면(`Backoff.next`가 `None`) `NetworkAbort`다.
3. 끊김 동안(`Outage.active`: 기다리는 worker나 회복을 확인하는 worker가 있을 때): 새 worker·리뷰를 시작하지 않는다. 도는 worker는 그대로 두고, 성공으로 끝난 worker(수정 worker 포함)의 리뷰·재리뷰는 미룬다(`_net_park`, `network_resume.done`). 진행 줄은 `네트워크 대기(2회, 3분 뒤)`, 회복 확인 중이면 `네트워크 회복 확인(2회)`.
4. 다시 띄우기(`_resume`): 같은 worktree·브랜치에서 새 worker를 띄운다. 구현은 새 시도 디렉터리 `run/<NN>/<시도>`, 수정 worker는 `fix-net<k>`(`fix2-net<k>`)다. brief에 `worker.NETWORK_RESUME`("지난 시도가 네트워크로 끊겼다…")가 붙는다. 처음 base를 그대로 쓰므로 앞 시도의 커밋도 이 worker의 커밋으로 센다. 띄우지 못하면 구현은 티켓 실패, 수정은 실패한 수정이다.
5. 회복: 다시 띄운 worker가 `RECOVERY_MINUTES`(5분) 넘게 일시 오류 없이 돌거나 끝나면 끝이다(claude 자체 재시도가 약 3분 넘게 걸린다). 함께 기다리던 worker를 바로 띄우고 일정을 새로 시작하고 미룬 리뷰를 돌려놓는다. `■ 네트워크 회복: 다른 티켓 시작을 재개한다`.

**codex**(`transient.ReconnectWatch`) — codex worker는 끊겨도 죽지 않고 `Reconnecting...` 이벤트를 찍으며 기다린다. `_wait_any`가 로그를 이어 읽어, `Reconnecting`만 `network_wait_minutes` 넘게 이어지면 `NetworkAbort`다. 다른 이벤트가 나오면 처음부터 다시 잰다. 회복 시간도 마지막 `Reconnecting`부터 잰다.

**`중단(네트워크)`**(`transient.NetworkAbort`, `go._net_abort`, `go.EXIT_NETWORK = 3`) — 세 곳에서 온다: worker 대기 합계, codex `Reconnecting`, 리뷰·재리뷰·지적 분류의 대기 합계. `_loop`가 받아 돌던 worker를 끝내고 티켓마다 `network_resume`을 남긴 뒤(리뷰 중이었으면 `done`) `pending`, 이유 `중단(네트워크)`로 둔다. 두 리뷰 중 한쪽이 중단되면 다른 쪽 결과도 버린다(다음 `gs go`가 다시 받는다). `go.go`가 `network.aborted`를 적고 마무리를 건너뛴다: 보고서·PR·병합이 없고 `failures`는 그대로다. 출력은 `■ 네트워크 중단 이유: …`, `■ 중단(네트워크): 다음 gs go가 이어 간다`, 요약(`■ 마무리: 중단(네트워크)`)이고, 종료 코드 3이다. 알림은 `❌ <f> · 중단(네트워크) · …`, `gs status` 첫 줄은 `<f>: 중단(네트워크)(<시각>) · 다음 gs go가 이어 간다`. `gs go a b`는 여기서 멈춘다.

**다음 `gs go`** — `_begin`이 `network.wait`·`aborted`를 지우고 `_loop`가 `Outage`를 새로 만든다: 대기 합계는 `gs go`마다 새로 센다. `_start`가 `network_resume`을 보고, worktree가 그 브랜치로 그대로 있으면(`_resumable`) `_resume`으로 잇는다. `done`이면 프로세스 없이 리뷰·재리뷰부터다. 아니면 경고하고 새로 시작한다. `gs`가 대기 중에 죽어 `running`으로 남아도 표시가 있으면 같다.

**리뷰·판단 호출의 대기**(`review._call`, `review.call_waiting`, `review.CallWait`) — `review._call`은 새 프로세스 그룹에서 돌고, 끝날 때(시간 초과, 정상 종료, 코디네이터 중단 모두) `verify.stop`으로 그룹에 남은 프로세스를 끝낸다(SIGTERM, 5초 뒤 SIGKILL). 그래서 다시 부르는 호출은 앞 호출의 프로세스가 끝난 뒤 시작한다. 호출이 일시 오류(`transient.reason`)나 시간 초과로 끝나면 `call_waiting`이 worker와 같은 일정(호출마다 새로 센다)으로 기다렸다 다시 부른다. 대기 합계는 대기만 센다. 호출이 시간 초과까지 쓴 시간은 넣지 않으므로, 계속 시간 초과인 리뷰어는 기본값으로 대기 60분에 호출 10번 × 30분을 더 쓴 뒤 중단된다. 상한을 넘기면: 리뷰·재리뷰·지적 분류는 `NetworkAbort`로 `_loop`까지 올라가 `중단(네트워크)`가 되고 다음 `gs go`가 리뷰·재리뷰부터 잇는다. 끊겼다는 이유로 리뷰 없이 병합하지 않는다. 보고서 Summary와 실패 요약은 중단하지 않고 대체 문구로 간다(병합 안전과 무관하다). 일시 오류가 아닌 실패(인증, 구독 한도, 형식 오류, 모르는 오류)는 다시 부르지 않고 지금처럼 `리뷰 실패(리뷰 없음, verify만으로 병합한다)`, `unchecked(재리뷰 실패)`, 모두 report, 대체 문구다. 판별의 입력은 CLI 출력 형식에 달렸다: claude는 `--output-format json`의 result(답도 그 `result`에서 꺼낸다), codex는 `--json`의 이벤트(답은 `--output-last-message` 파일. 시도마다 지우고 시작한다), agy는 stderr다(stdout의 답이 stderr의 연결 오류를 가리지 않지만, stdout의 오류 이벤트가 인증·구독 한도를 말하면 일시 오류가 아니다). 실패한 호출의 stdout은 `reviewer.log`·`judge.log`에 덧붙는다. 다시 부르면 로그는 새로 쓴다. 대기 중에는 `CallWait`가 state의 `network`(`wait`, `errors`, `waited_seconds`)와 티켓의 `transient_errors`·`network_wait_seconds`를 쓰고 60초마다 저장해, 진행 바에 `01 리뷰 중(codex) · 네트워크 대기(2회, 3분 뒤)`가 보인다. 코디네이터 스레드에서 기다리므로 그동안 새 worker를 띄우지 않고 끝난 worker도 처리하지 않는다. 돌던 worker는 각자 돈다.

**범위 밖** — 마무리 단계의 push·`gh` 오류는 기다리지 않고 지금의 재개 흐름(`finish.RESUME_PHASES`)이다. 리뷰 호출의 스트리밍·idle 상한(`review-idle-timeout`), 세션 이어 가기(`session-resume-worker`)는 없다.

## 마무리

티켓 루프가 끝나면(`state.phase = finish`) `finish.py`가 외부 작업마다 `state.finish`를 저장하며 진행한다. 중단 뒤 다시 실행해도 같은 PR을 두 번 병합하거나 두 번 revert하지 않는다.

모든 `gh pr` 호출(`view`, `list`, `create`, `edit`, `merge`)은 `--repo <owner/repo>`를 붙인다. owner/repo는 그때마다 `git.remote`의 URL에서 푼다(위 "환경 검사"). gh의 기본 저장소(`gh repo set-default`, 첫 원격)를 따르지 않으므로, 원격이 여럿이어도 gs가 push한 그 저장소의 PR만 다룬다. 그래서 `git.remote`는 GitHub 저장소여야 한다.

**push 전 대조** — worktree는 git 설정을 주 레포와 공유한다. worker나 verify 명령이 원격 주소를 바꾸면 worktree는 깨끗한 채로 남고, 뒤의 gs push가 그 주소로 코드를 보낸다. hook은 `python -c` 같은 길을 못 막으므로(아래 "worker 차단 hook") gs의 push가 대조한다.
- 기록: `_begin`이 worker를 띄우기 전에 `state.push_record`에 남긴다(`git.push_settings`). `remote`, `settings`(`remote.<r>.url`·`pushurl`, `core.hookspath`. 키마다 `[범위, 값]`), `fetch_urls`·`push_urls`(`git remote get-url --all`, insteadOf까지 적용한 실제 주소), `rules`(`url.*.insteadOf`·`pushInsteadOf`), `state_file`(이 기록이 있는 state.json. 값이 아니라 위치라서 `state.load`가 읽을 때마다 실제 경로로 채운다. 이 항목이 없는 기록도 재개와 `gs clean`에서 되돌릴 수 있다). 재개해도 기록을 덮어쓰지 않는다. worker가 바꾼 값을 기준으로 삼지 않기 위해서다. 옛 state에 기록이 없거나 `git.remote`가 바뀌었으면 그 `gs go`가 시작할 때 처음 기록한다.
- 대조: `git.push`가 모든 push 직전에 한다(`finish.py`의 다섯 곳, `clean.py`의 `--delete`). `settings`나 실제 주소가 다르면 push하지 않고 `git.PushSettingsChanged`를 올린다. 글에는 바뀐 값, 범위별 되돌릴 `git config` 명령, 의도한 변경일 때 할 일이 들어간다. 이 글은 `finish.error`를 지나 보고서로 나가므로 주소의 인증 정보(`https://…@`)를 싣지 않는다. 바뀐 값은 `***`로 가리고, 되돌릴 명령은 시작 때 값을 실행할 때 `state_file`에서 읽는다(가린 값을 넣으면 원래 값으로 돌아가지 않는다). `url.*` 규칙의 키에 인증 정보가 있거나, 시작 때 값에 인증 정보가 있는데 `state_file`이 없으면 명령 대신 고칠 곳을 적는다. 보고서 push의 "최선" 처리(`_report_to_base`, `_report_pr`)도 이 오류는 삼키지 않아 `base_report_tried`가 남지 않고, `finish.run`의 실패 처리도 보낼 수 없는 보고서 커밋을 만들지 않는다. `gs go`가 stderr에 전부 쓰고 `finish.error`에 전부, `finish.outcome`에 첫 줄을 남긴다(알림은 한 줄이다). 되돌린 뒤 `gs go`가 멈춘 곳부터 잇는다.
- `rules`는 멈출 이유가 아니다. 실제 주소가 바뀌었을 때 원인과 되돌릴 명령을 찾는 데만 쓴다. 그래서 사용자의 insteadOf는 시작 때와 같으면 통과하고, 이 원격과 상관없는 규칙을 실행 중에 더해도 멈추지 않는다.
- env로 얹은 설정은 빼고 읽는다(`GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_*`, `GIT_CONFIG_VALUE_*`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG`). worker 전용 push 차단(`worker.push_guard`)이 여기 있어서, 판정에 넣으면 gs가 worker 안에서 돌 때 기록이 틀어진다. 파일에 남은 설정만 뒤의 gs push에 영향을 준다.
- `state.push_record`가 없으면(`gs clean`이 읽는 옛 state) 대조를 건너뛴다. `gs clean`은 `ls-remote`도 대조 뒤에 한다.
- 범위는 push뿐이다. 바뀐 `core.hooksPath`의 hook은 gs의 commit·merge에서 push 전에 돌 수 있고, fetch도 바뀐 주소로 간다(worker가 hook을 우회했을 때). `.git/hooks/` 파일과 `core.sshCommand`는 기록하지 않는다.

1. integration 검증(`integration`). 실패하면 integration을 되돌린다.
2. 보고서: 새 판단 모델 호출(`models.judge`, 제한 `timeouts.judge_minutes`)이 증거 파일(`finish/report-input.md`, `finish/diff-stat.txt`, spec)을 읽고 Summary를 쓴다. 프롬프트는 마무리 상태·병합 여부 문장을 쓰지 말라고 한다(그 시점에는 아직 모른다). gs가 원본 증거를 붙여 `.goldstack/work/<f>/report.md`를 integration에 커밋한다: Summary, 마무리 상태 줄(아래), Evidence(티켓별 결과, 단계별 소요 `단계별 소요: worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`, 남은 리뷰 지적, verify 출력), Merge Danger(`결과:` 줄, PR, verify 결과, 병합·revert 커밋, 되돌리는 법). PR 본문 상한(60,000자)을 넘으면 로그를 줄이고, 그래도 길면 자른다. 판단 모델이 실패하면 그 사실을 Summary에 쓴다.
3. integration을 `<remote>`에 일반 push하고 `gh pr create --repo <owner/repo> --base <base>`(열린 PR이 있으면 `gh pr edit`). PR 본문은 보고서와 같다.
4. 보고서 커밋까지 포함한 PR head를 다시 검증(`integration-final`). 1과 달라진 것이 `report.md`뿐이면 건너뛴다(아래 "integration-final 건너뛰기").
5. merged 티켓이 하나 이상이고 1과 4가 모두 통과하면 `merge_head`·`merge_method`를 남기고, `git.wait_checks`면 CI를 기다린 뒤(아래 "CI 대기") `gh pr merge --repo <owner/repo> --merge|--squash --match-head-commit <검증한 head>`(아래 "병합 방식"). 아니면 `not_merged`(병합 안 함).
   `integration`·`integration-final` 검증 실패면 `finish.failed_verify`에 실패 단계를 남긴다. 최종 보고서 Evidence의 "검증 실패"에는 해당 로그 경로와 `FAIL`·`ERROR`·`failed`·`not ok`를 포함하는 첫 10줄, 후보 티켓(추정)을 붙인다. 병합된 티켓의 `touches` 또는 티켓 병합 커밋의 첫 부모 대비 변경 파일을 실패 줄의 경로·이름과 대조하며, 없으면 `후보 없음`이다. 후보 탐색 오류는 보고서에 적고 보고서 쓰기를 계속한다. 검증 통과 때는 이 부분을 붙이지 않는다.
6. PR을 다시 읽어 실제 `MERGED`, base 이름, 병합 커밋, head가 검증한 것과 같은지 확인한다. 아직이면 `merge_pending`(병합 큐·승인 대기, 종료 1, 다음 실행이 이어 간다). 사람이 닫았으면 `closed`(다음 실행이 새 PR을 연다).
7. 병합을 방식대로 확인한 뒤(squash면 tree 비교) 최신 `<remote>/<base>`를 임시 detached worktree에 받아 `[worktree] setup`이 있으면 돌리고(실패하면 `base_unverified`) 재검증(`main`). 실패하면 그 병합 커밋을 `git revert`(병합 커밋이면 `-m 1`)해 base에 일반 push한다(force push 없음, `git.direct_push = false`면 `gs/<f>/revert` PR로). 실패 뒤 base가 움직였으면 최신 base를 다시 검증(`main-recheck`)한다. gs 밖에서 이미 되돌렸으면 다시 revert하지 않는다.
8. **보고서 갱신** — `verified`·`reverted`이고 base 보고서를 아직 시도하지 않았으면 이 feature의 병합을 되돌린 revert만 먼저 되돌려 합치고(`_restore_reverts`, 보고서에 그 커밋을 남기려고), 보고서를 다시 써 integration에 커밋·push하고 PR 본문도 갱신한다(`_update`). 같은 `finish/summary.md`(끝 줄바꿈을 뗀다)로 다시 쓰므로 재개해도 보고서가 어긋나지 않는다. 그 밖의 phase(`closed`, `base_unverified`, `revert_pending`, 끝난 마무리에 이번 실행의 실패 티켓이 더해진 경우)는 base를 합친 뒤 보고서를 다시 쓰고(`merge_base` → `_update`) 9·10은 없다.
9. **base에 최종 보고서 push** — 이 마무리가 `verified`·`reverted`로 끝났을 때만. `git.direct_push = false`면 push 대신 `gs/<f>/report` PR로 같은 커밋을 올린다(아래 "보호된 base"). 원격 base의 최신 끝을 임시 detached worktree에 받아 `.goldstack/work/<f>/report.md`만 integration의 최종판으로 바꾼 커밋 `gs: <f> 최종 보고서(병합 후)`를 만들어 `<remote>`의 base에 일반 push한다(force 없음). base에 이미 같은 내용이면 커밋하지 않는다. 성공하면 `■ 최종 보고서를 <base>에 push했다(<sha8>)`를 출력하고 state `finish.base_report`에 sha를 적는다.
   - 거부되면(그 사이 base가 움직임) fetch 뒤 최신 base 위에서 다시 만들어 한 번 더 시도한다. 그래도 실패면 `■ 경고: 최종 보고서를 <base>에 push하지 못했다(두 번 시도). 실행 결과는 그대로다: …`만 쓴다. 실행 결과·종료 코드는 바뀌지 않는다.
   - 시도를 마치면(성공이든 실패든) `finish.base_report_tried`를 남기고, 다음 `gs go`는 다시 시도하지 않는다. 시도 전에 끊긴 실행(예: 8의 `gh pr edit` 실패)은 다음 재개가 처음으로 시도한다.
   - `not_merged`·`closed`·`merge_pending` 등 그 밖의 phase면 push하지 않는다. `git.direct_push = true`인데 base가 보호돼 있으면 push가 두 번 거부되어 경고로 끝나고, base에는 병합 시점의 report.md가 남는다. revert push도 거부되어 `main_failed`로 멈추니 `gs doctor`대로 `false`로 둔다.

10. **base를 integration에 합침**(`_merge_base_keep_report`) — 보고서를 다시 쓰지 않고 base를 합쳐 `finish.head`로 남기고 push한다. 9의 보고서 커밋이 integration에 들어오고 양쪽 report.md가 같아서, 다음 PR이 report.md에서 충돌하지 않는다. `report_pending`으로 멈췄으면 보고서 PR이 병합된 뒤의 재개에서 한다.
11. **자동 정리**(`clean.integration`) — phase가 `verified`이고 9를 시도한 뒤(`base_report_tried`. 보호된 base면 보고서 PR이 병합된 뒤)에만. integration worktree(`run/wt/integration`, 미커밋 변경도), 로컬 `gs/<f>/integration`, 원격(`git.remote`) `gs/<f>/integration`을 지운다. 원격은 tracking ref가 아니라 `git ls-remote --heads`로 실제 이름을 찾아 `git push <remote> --delete`한다. 오류는 `경고: 정리 실패: …`만 쓰고 결과·종료 코드를 바꾸지 않는다. `verified`가 아닌 phase는 남긴다(원인 조사, 재개). 티켓 worktree·브랜치는 건드리지 않는다. 재개한 마무리는 남은 티켓이 없을 때만 정리한다(남았으면 다음 `gs go`가 이 integration에서 이어 간다).

마무리 순서를 줄이면 **보고서(integration) → base 보고서 → base 합치기 → (남은 티켓이 없으면 자동 정리) → 멈춤**이다. base 보고서 커밋이 늘 base 합치기 앞에 있고, 합친 뒤에는 report.md를 다시 쓰지 않는다.

**재개는 멈춘다**(`go._resume_finish`) — 지난 마무리를 이어 간 실행은 어디서 끝나든 그대로 끝난다. `_loop`도 두 번째 `finish.run`도 없다. 재개가 base 보고서 없는 integration에서 새 티켓을 시작하거나, 두 번째 마무리가 base판과 다른 report.md를 쓰면 다음 PR이 report.md에서 충돌하기 때문이다. `verified`·`reverted`로 끝났는데 범위에 `pending` 티켓(`_begin`이 실패·건너뜀에서 되돌린 것 포함)이 있으면 `■ 남은 티켓 <n>개 → 다음 gs go`를 쓰고 integration을 지우지 않으며, 텔레그램에도 같은 말이 붙는다. 티켓이 병합되지 않았으니 종료 1이고, `gs go a b`는 여기서 멈춘다. 다음 `gs go`는 `base_report_tried`가 있어 재개가 아니므로 평소처럼 티켓 루프와 새 PR로 간다. `report_pending` 재개는 `_report_side_pr`만 한다: 병합되면 기다리던 phase·outcome으로 돌아가(`report_result`) 10·11로, 아직이면 그대로 멈춘다. integration 보고서는 PR에 올린 판 그대로 둔다.

다음 `gs go <f>`가 "정리된 끝난 실행"을 보면(`go._finished_after_clean`: phase가 `verified`·`reverted`, `base_report_tried`, integration worktree 없음, 로컬 `gs/<f>/*` 브랜치 없음, 범위 티켓이 모두 merged, 남긴 worktree 없음) integration을 다시 만들지 않고 `■ 이미 끝남: <f> (<phase>)`를 쓴 뒤 자동 정리만 다시 시도한다(지난 정리가 원격 삭제에서만 실패했을 수 있다). 하나라도 아니면 평소처럼 이어 간다. 이때 integration은 `finish.head`(객체가 남아 있으면)에서 다시 만들어 병합 표시를 회복하므로 병합된 티켓은 다시 돌지 않는다. `finish.head`가 없으면(마무리 phase가 `verified`·`reverted`가 아님) `<remote>/<base>`에서 시작한다.

**마무리 상태 줄** — report.md의 Summary 바로 아래 한 줄을 gs가 `state.finish`에서 만든다(`report.status_line`). 판단 모델의 글이 아니라서, 병합 전에 쓴 Summary가 "아직 병합 전"으로 남는 일이 없다. 형식은 `마무리: <phase> · …`:

| phase | 줄 |
|---|---|
| `verified` | `마무리: verified · PR <url> 병합 · <base> 검증 통과` |
| `reverted` | `마무리: reverted · <base> 검증 실패 → revert <sha8>`(gs 밖에서 되돌렸으면 `<base>에서 이미 되돌림 → revert …`) |
| `not_merged` | `마무리: not_merged · integration 검증 실패`, merged 티켓이 없으면 `… · merged 티켓 없음` |
| `closed` | `마무리: closed · PR <url>이 병합되지 않고 닫힘` |
| `merge_requested`, `merge_pending` | `마무리: merge_pending · PR <url> 병합 대기 · <base> 검증 미실행` |
| `merged` | `마무리: merged · PR <url> 병합 · <base> 검증 대기` |
| `main_failed` | `마무리: main_failed · <base> 검증 실패 · revert push 안 됨` |
| `revert_pending` | `마무리: revert_pending · <base> 검증 실패 · revert PR <url> 병합 대기` |
| `report_pending` | `마무리: report_pending · PR <url> 병합 · 보고서 PR <url> 병합 대기` |
| `setup_failed` | `마무리: setup_failed · 준비 실패 · 병합 안 함` |
| `base_unverified` | `마무리: base_unverified · PR <url> 병합 · base 미검증(준비 실패)` |
| 그 밖(`preparing`, `checks_*`) | `마무리: <phase> · 병합 전` |

기다리는 PR의 head를 바꾸지 않으려고 `merge_pending`·`checks_*`에서는 보고서를 다시 쓰지 않으므로 그동안 파일에는 `preparing`이 남는다. `report_pending`은 보고서 PR에 올린 판(`verified`·`reverted`)을 그대로 둔다. 끝나지 않은 phase에 오류가 있으면 끝에 `· 오류(아래 Merge Danger)`가 붙는다. `finish.error`는 그 뒤 성공하면 지운다(PR 병합 확인, revert·보고서 PR 병합 확인, `verified`·`reverted`로 끝남, `_clear_error`). 그래서 지난 승인 거부·일시 오류가 끝난 보고서의 Merge Danger에 남지 않는다. PR이 없으면 `<url>` 자리가 `PR 없음`이다. 보고서 커밋 때문에 병합 revert가 report.md에서 충돌하면, 되돌리는 법에 지금 보고서를 남기고 이어 가는 명령이 적힌다.

base가 이 feature의 병합을 revert했으면 그 revert를 되돌린 커밋을 만들어 합친다(그냥 합치면 feature 코드가 조용히 사라진다). gs 자신의 revert면 같은 마무리의 8에서, 다른 사람의 revert면 다음 실행이 integration을 준비할 때다. 보고서에 그 사실을 적고, 새 티켓이 든 다음 PR이 feature 코드를 다시 들인다. 상태 이름·로그 이름의 `main`(`main_failed`, `main-verify.log`)은 "base 브랜치"를 뜻하는 옛 이름이다.

git 오류나 herdr 오류(`HerdrError`)로 루프를 떠나도 `gs go: … 오류: …`를 stderr에 쓰고 `finished_at` 기록, 요약 출력, 알림까지 간다(종료 1).

마지막 출력은 요약과 PR 링크다:
```
■ 요약: 병합 7, 실패 1
■ 마무리: integration·main 검증 통과, PR 병합 완료
■ 보고서: .goldstack/work/<f>/report.md · 남은 리뷰 지적 2
■ PR: https://github.com/…/pull/4
```

### 병합 방식: merge와 squash

`git.merge_method`. rebase는 없다(config 오류). 병합을 요청할 때 `finish.merge_method`에 남기고, 그 PR의 확인·revert·재개는 config가 바뀌어도 남긴 방식을 따른다.

| | `merge` | `squash` |
|---|---|---|
| 병합 명령 | `gh pr merge <url> --merge --match-head-commit <merge_head>` | `gh pr merge <url> --squash --match-head-commit <merge_head> --subject <제목> --body <본문>` |
| 메시지 | GitHub 기본 | 제목 `<f>: gs go (#PR)`, 본문은 이번에 base로 가는 티켓(되살린 티켓 포함)의 `NN 제목` 목록, 티켓별 `gs-ticket: <f>/NN` 줄, 되살렸으면 `This reverts commit <revert>.` 줄 |
| 확인(`_check_merge`) | `merge_head`가 병합 커밋의 조상 | 병합 커밋의 부모가 하나이고 **tree가 `merge_head`의 tree와 같다** |
| revert | `git revert -m 1 <병합 커밋>` | `git revert <squash 커밋>`(부모가 하나라 `-m` 없음) |
| 병합된 티켓 찾기 | integration의 병합 커밋 트레일러 | integration의 트레일러, base에서 합쳐 온 squash 본문의 같은 줄 |

`git.ticket_trailers`가 커밋 본문의 독립된 `gs-ticket: <feature>/<id>` 줄을 읽는다. `go`의 재개와 `finish`의 병합 검색 모두 이 함수를 써 feature와 id 전체를 비교하며, 제목이나 본문 문장에 섞인 표시는 세지 않는다. integration은 조상에 있는 병합 커밋을 읽고, 부모가 하나인 커밋은 원격 base의 첫 부모 경로에 있을 때만 squash 표시로 읽는다. worker 일반 커밋의 독립된 표시 줄은 세지 않는다. 새 integration 병합 검색은 squash를 제외한다.

- **tree 비교**: squash 커밋은 base 끝에 PR diff를 얹은 것이다. 검증한 integration을 만든 뒤 base가 움직였으면 tree가 달라 검증하지 않은 내용이 base에 들어갔다는 뜻이다. `_postmerge`는 base 검증 전에 이것을 본다. 다르면 `GitError`: phase는 `merged`, `finish.error`와 `마무리 실패: squash 커밋 <sha>의 tree가 검증한 integration <sha>의 tree와 다르다…`를 남기고 base 검증도 revert도 하지 않는다. integration은 실행을 시작할 때만 base를 합치므로 실행 중 base에 들어온 커밋이면 모두 해당한다. 다음 `gs go`도 같은 오류로 멈춘다. 사람이 base를 확인한 뒤 `gs clean <f> --force` → `gs go <f>`로 빠져나온다: 새 integration은 merge_head를 조상으로 갖지 않아 마무리를 처음부터 하고(병합된 티켓은 base의 `gs-ticket` 줄로 회복), 그때 되돌릴 대상은 새 보고서 병합뿐이다.
- **revert 찾기**: squash 커밋은 parents 하나와 `gs-ticket: <f>/` 본문으로 알아본다(`_feature_merge`. integration의 티켓 병합은 늘 부모가 둘이다). 그래서 finish가 비워진 뒤에도 base의 revert를 찾아 다음 실행이 되살린다. revert·보고서 PR을 squash로 병합할 때는 커밋 메시지를 그대로 넘겨 `This reverts commit <병합>` 줄을 base에 남긴다(`_side_merge`).
- **되살림 식별**(`_squash_message`, `_undone_reverts`) — revert의 revert는 squash하면 이력에서 사라진다. 그래서 squash 본문이 그 일을 대신한다. `finish.reintroduced`(`revert`, `merge`, `commit`) 중 `commit`이 `merge_head`에 들었고 base에서 아직 되돌리지 않은 것마다 (1) 되돌린 병합의 트레일러(`merge^..merge`)에서 티켓을 읽어 목록·`gs-ticket` 줄에 더하고(이 티켓들은 base에 옛 줄이 있어 "새 티켓" 계산에서 빠진다), (2) `This reverts commit <revert>.`를 적는다. `_undone_reverts`는 base 이력에서 이 줄을 찾아 이미 되살린 revert를 건너뛴다(`_revert_of`). 그래서 state·integration이 없는 새 clone도 base 메시지만으로 같은 revert를 다시 되살리지 않고 티켓도 다시 돌리지 않는다. 새 마무리가 `finish`를 비울 때 아직 base에 안 들어간 항목(`_landed`가 아닌 것)은 `reintroduced`로 넘겨 다음 PR 보고서·본문에 남긴다.
- **integration과 base 잇기**: squash 커밋은 `merge_head`를 조상으로 갖지 않아 그대로 합치면 report.md가 충돌한다. `_absorb_squash`가 `merge_head`를 기준으로 합쳐 표시 커밋을 만든다. 병합을 확인하기 전(`merge_requested`·`merge_pending`이고 `merge_sha` 없음)에는 `merge_base`가 base를 합치지 않는다.

### CI 대기

`git.wait_checks = true`. 보고서 커밋까지 든 최종 head(`merge_head`)에서 PR을 연 뒤 병합 전에 돈다(`finish._wait_checks`).

| phase | 뜻 | `outcome` | 다음 |
|---|---|---|---|
| `checks_pending` | 기다리는 중. 진행 바 `CI 대기 중` | `CI 검사 대기 중` | 모두 통과 → `merge_requested` → 병합 |
| `checks_failed` | 실패·취소한 검사가 있다. 병합 안 함, PR은 열어 둠, 종료 1, 알림 | `CI 실패: <이름>, …` | 다음 `gs go`가 다시 읽는다 |
| `checks_timeout` | `timeouts.checks_minutes`를 넘겼다. 병합 안 함, PR은 열어 둠, 종료 1, 알림 | `CI 대기 시간 초과` | 다음 `gs go`가 다시 읽는다(시간도 새로 잰다) |

- **어떤 검사**(`_poll_checks`, revert·보고서 PR도 같다): 먼저 base의 필수 검사 이름을 읽는다(`_required_checks`: `repos/<o>/<r>/branches/<base>/protection`과 `rules/branches/<base>`, `gs doctor`와 같은 해석, 호출 하나 20초). 이름을 알면 `gh pr checks <url> --json name,bucket`에서 그 이름만 보고, 아직 없는 이름은 `pending`으로 친다. 그래서 등록이 늦어도 `timeouts.checks_minutes`까지 기다리고 필수가 아닌 검사의 실패에 막히지 않는다. 두 API 중 하나라도 못 읽으면(부분 목록을 전체로 치지 않는다) 또는 이름이 없으면 gh 판정을 쓴다: `--required`, 없으면(`no required checks reported`) `--required` 없이 전부. `no checks reported`만 빈 목록이고, 그 밖의 gh 오류는 `GitError`다(검사 없음으로 치지 않는다). bucket `pass`·`skipping`은 통과, `fail`·`cancel`은 실패, `pending`은 대기이고 pending이 남아도 실패가 하나 있으면 바로 끝낸다.
- **CI grace**(`timeouts.checks_grace_seconds`, 기본 60, 0 허용): 목록이 비었을 때만 쓴다. 대기를 시작한 때부터 그 시간이 지날 때까지 다시 읽고(`■ PR #N: CI 검사 대기 중(검사 없음)`), 그 안에 검사가 나타나면 평소처럼 끝날 때까지 기다린다. 지나도 비었으면 `■ PR #N: 검사 없음 → 병합`을 쓰고 병합을 시도한다. `gs go`마다 새로 재고, `checks_minutes`를 넘기면 `checks_timeout`이 먼저다. 필수 검사 이름을 알면 목록이 비지 않으므로 grace는 쓰이지 않는다.
- **10초마다** 다시 읽고(`CHECK_INTERVAL`), 목록이 바뀔 때만 `■ PR #N: CI 검사 대기 중(build ✓, test …)`을 쓴다. 변화가 없어도 `finish.checks`를 저장해 진행 바 경과가 간다.
- **head 고정**: 조회할 때마다 PR 상태·head를 대조한다. 대기 중 닫히거나 head가 바뀌면 `GitError`다. 병합도 `--match-head-commit`으로 고정한다. 기다리는 동안 보고서를 다시 쓰거나 base를 합치지 않는다(`merge_base`는 `CHECK_PHASES`에서 바로 돌아간다). 그래서 이 사이 report.md의 마무리 줄은 `preparing`이다. 지금 상태는 `■ 마무리:`, 알림, `state.finish`로 본다.
- **재개**: PR head가 `merge_head`와 같으면 재검증 없이 다시 읽는다. 사람이 고쳐 head가 바뀌었으면 그 head를 받아 `integration-recheck`로 `verify`한 뒤 기다린다(`_refresh_check_head`). 실패면 `not_merged`.

### 보호된 base(`git.direct_push = false`)

gs는 base에 아무것도 push하지 않는다. base로 갈 gs 커밋(revert, 최종 보고서)을 `gs/<f>/revert`·`gs/<f>/report` 브랜치의 PR로 올려 feature PR과 같은 병합 방식으로 병합을 시도한다(`finish._side_pr`). `wait_checks`면 그 PR의 검사도 같은 방식으로 기다린다. 승인은 사람이 한다: gs는 승인하지 않고 막히면 멈춘다. spec·티켓을 원격 base에 올리는 것은 이 흐름 밖이다(`/go`의 push는 보호에 막힌다. 사람이 PR로 올린다, [guide](guide.md#예시-보호된-main--필수-승인)).

| phase | 무엇을 기다리나 | `outcome` | 다음 `gs go` |
|---|---|---|---|
| `merge_pending` | feature PR. 큐·보호 규칙(`direct_push`와 무관하게 같다) | `사람 승인 필요: <url>. <base> 검증은 미실행`, 또는 `병합 명령 뒤 PR이 아직 MERGED가 아니다…` | PR을 다시 읽어 병합을 다시 시도하고, 병합됐으면 base 검증 |
| `revert_pending` | base 검증이 실패해 만든 revert PR. **깨진 코드가 base에 남아 있다** | `사람 승인 필요: <url>`, `revert PR 병합 대기: <url>`, `revert PR CI 실패: <이름>: <url>`, `revert PR CI 대기 시간 초과: <url>`, `revert PR 확인 실패: <브랜치> (…)` | 같은 PR을 다시 읽어 병합되면 `reverted` → 보고서 PR |
| `report_pending` | 최종 보고서 PR. 코드는 병합·검증됐다 | `사람 승인 필요: <url>`, `report PR 병합 대기: <url>`, `report PR CI 실패…`, `report PR 확인 실패: <url 또는 브랜치> (…)` | 같은 PR을 다시 읽어 병합되면 기다리던 `verified`·`reverted`로 돌아간다(`finish.report_result`) |

- 셋 다 종료 1, 알림(`사람 승인 필요: <url>` 포함)이고 worker를 다시 띄우지 않는다(`RESUME_PHASES`). `gs go a b`는 여기서 멈춘다. `report_pending`도 `verified`가 아니라서 멈춘다.
- **막혔는지 판단**(`_needs_human`): PR `reviewDecision`이 `REVIEW_REQUIRED`·`CHANGES_REQUESTED`이거나 `gh pr merge` 오류에 `review|approv|base branch policy|protected branch`가 있으면 `사람 승인 필요`. 아니면 병합 대기로 적는다.
- **상태**: 같은 커밋의 PR을 다시 쓰도록 `finish.<kind>_pr`, `<kind>_head`를 남기고 병합을 확인하면 `<kind>_merge`(`kind`는 `revert`·`report`). squash면 `<kind>_head`는 base의 조상이 되지 않으니 PR로 확인한다.
- **사람이 닫으면**: base에 꼭 넣어야 하는 커밋이라 gs 브랜치를 다시 push(`--force`, gs 전용 브랜치에만)하고 PR을 다시 연다.
- **PR 오류**: 보고서 브랜치를 올리기 전 오류는 직접 push 때처럼 경고뿐이다(`base_report_tried`). 올린 뒤에는(`<kind>_head`를 남긴 뒤) GitHub에 PR이 생겼을 수 있으니, PR 생성 응답 오류·빈 출력·`gh pr list` 실패·조회·검사 오류면 `<kind>_pending`으로 멈춘다(`■ 경고: <kind> PR을 확인하지 못했다…`). `<kind>_pr`을 몰라도 다음 `gs go`가 `_find_side_pr`로 그 브랜치의 열린 PR, 없으면 같은 head로 병합된 PR을 찾아 이어 가고, 없을 때만 새로 만든다. base에 이미 같은 내용이면 보고서 PR을 만들지 않는다.
- `base_report_tried`는 보고서 PR이 병합됐을 때 남고, base 합치기와 자동 정리는 그 뒤에 돈다. 원격 `gs/<f>/revert`·`gs/<f>/report`는 자동 정리 대상이 아니다(`gs clean`이 지운다).

### 준비 실패 위치별 처리

`[worktree] setup`(`setup.py`)은 `bash -c`로 그 worktree에서 돌고, `verify.py`처럼 새 프로세스 그룹에 시간 제한 `timeouts.setup_minutes`다(넘기면 그룹 전체를 끝내고 로그 끝에 `시간 초과: <N>분`). 환경에서 `VIRTUAL_ENV`·`GS_ROLE`을 뺀다. gs가 돌리므로 worker hook 밖이다. 비어 있으면 프로세스도 로그도 없다.

| 위치 | 언제 | 로그 | 실패하면 | 다음 `gs go` |
|---|---|---|---|---|
| 티켓 worktree(`run/wt/<NN>`, 재시도마다) | worker 전 | `run/<NN>/<시도>/setup.log` | 그 티켓 `failed`, 이유 `준비 실패`, **재시도 없음**. 막힌 티켓 `skipped`, 나머지는 계속 | 실패 티켓을 새 worktree에서 다시 |
| integration(`run/wt/integration`) | 티켓 루프 전, 재개 포함 | `run/integration/<시도>/setup.log` | phase `setup_failed`, `준비 실패 → 병합 안 함`. worker·verify·PR 없음, 종료 1. 이미 진행한 마무리(`RESUME_PHASES`, `verified`·`reverted`)가 있으면 그 phase를 덮지 않는다. 보고서는 integration worktree의 `.goldstack/work/<f>/report.md`에만 쓴다(커밋 안 함) | 다시 준비 |
| 병합 뒤 base(`run/gs-main-*/base`, 임시) | base 검증 전 | `run/finish/setup.log` | phase `base_unverified`, `base 미검증(준비 실패)`, `main_ok`는 null. **revert하지 않는다**(코드를 검증하지 못했을 뿐이다). 종료 1 | worker·integration 검증 없이 base 준비·검증부터 |

**추적 파일 변경**(`setup._restore_tracked`) — 세 위치 모두 `setup.run`이 끝날 때(성공·실패·시간 초과·중단 모두) `git status --porcelain`의 `??` 밖 경로를 `git reset`으로 unstage하고, HEAD에 있던 경로만 `git checkout --`으로 되돌린다. HEAD에 없던 경로(setup이 stage한 설치 파일)는 untracked 산출물로 남긴다. 되돌렸으면 `경고: setup이 추적 파일을 바꿨다 → 되돌림: <파일>, …`를 출력과 `setup.log`에 쓴다. 실패로 치지 않고 setup의 종료 코드만 결과다. 그래서 lockfile을 고치는 setup이 worker·verify가 쓰는 트리를 바꾸지 않고, integration의 "worker가 integration을 바꿨다"나 base `_verify`의 "worktree가 바뀌었다" → `main_failed` → revert로 이어지지 않는다. 보고서는 로그에서 다시 읽는다(`setup.warnings`, 지난 시도 포함): 티켓은 티켓별 결과의 이유, integration·base는 Merge Danger의 `<위치>: <경고>`.

표시 파일 `gs-setup-done`을 worktree별 git 디렉터리에 둬(`reset`·`clean`에도 남고 새 worktree에는 없다) integration을 재개할 때 다시 준비하지 않는다. 이 파일에 준비 때 생긴 untracked 파일 목록을 함께 적어(`setup.remember`), gitignore에 없는 산출물도 `git clean`과 "worktree가 바뀌었나" 검사(`setup.is_clean`)가 지우거나 문제 삼지 않는다. 티켓 worktree도 준비 뒤 같은 표시를 남긴다(시도마다 새 worktree라 준비는 다시 한다). 그래서 산출물이 미커밋 변경으로 잡혀 `kept_worktrees`에 남지 않고, 병합 뒤 정리가 기억한 산출물만 지운 뒤(`setup.discard_artifacts`) `--force` 없이 worktree를 지운다. 티켓 worker의 `git add -A`를 막아 주지는 않으니 산출물은 gitignore에 둔다. 로그 끝부분은 보고서 Evidence에 붙고, 티켓이면 `failure.log`에도 들어간다.

### integration-final 건너뛰기

2의 보고서 커밋은 `report.md`만 바꾸는데 전체 `verify`가 느린 프로젝트에서 같은 코드를 한 번 더 돌리게 된다. 그래서 4에서 `git diff --name-only <1에서 통과한 head> HEAD`가 `report.md`뿐이고 worktree가 깨끗하면(`setup.is_clean`) 돌리지 않는다(`finish._verify_final`). 출력 `■ integration-final: 보고서만 바뀜, 건너뜀`, 같은 줄을 `finish/integration-final-verify.log`에 쓰고 보고서 Evidence에도 남긴다. 그 밖의 파일이 바뀌었으면 평소처럼 돈다. 1이 실패했으면 4를 돌리지 않고 병합하지 않는다.

### 검증 명령 고르기와 재시도

spec `verify_ticket`, `verify_retries`. 티켓 검증 명령은 티켓 `verify` → spec `verify_ticket` → spec `verify` 순서로 고르고(`Spec.verify_for`), worker·수정 worker brief의 검증 명령도 그것이다. 어느 명령이든 integration의 미완 병합 트리에서 돈다. 그래서 티켓 worktree의 커밋 안 된 파일은 검증을 통과시키지 못한다. 로그 앞에 `$ <명령>`과 `cwd:`를 쓴다. 검증 뒤 HEAD·브랜치·MERGE_HEAD·index가 달라졌거나 `setup.is_clean(staged_ok=True)`가 거짓이면(index와 다른 파일, 준비 산출물이 아닌 untracked) 로그에 `검증 중 worktree가 바뀌었다`를 남기고 실패다. 다른 곳에서 index·HEAD가 바뀐 것과 구분하지 못하므로 그 경우 이유는 `검증하는 동안 integration이 바뀌었다`다. `integration`, `integration-final`, `integration-recheck`, `main`, `main-recheck`은 늘 `verify`다. `verify_retries`는 어느 지점이든 실패한 명령(시간 초과, 시작 실패 포함)을 그 횟수만큼 다시 돌린다(`verify.run`). 재시도마다 로그에 `검증 재시도 <n>`, 시간 제한은 같고, 통과하면 끝에 `flaky: <지점> 재시도 <n>번 만에 통과`(`verify.flaky`, 지점은 `ticket-<NN>`이나 위 이름)를 적는다. 보고서는 로그를 줄여도 이 줄을 Evidence에 남긴다. 검증이 worktree를 바꾸면 재시도 통과여도 실패다.

## `gs clean`

`gs clean <f> [--force]`(`clean.clean`). 실행 기록은 두고 worktree·브랜치만 지운다.
1. feature 이름 검사(`.goldstack/work/` 바로 아래 디렉터리만), config 읽기.
2. `run/lock`을 `gs go`와 같은 방식으로 잡는다. 잡지 못하면 `gs clean: 이미 다른 gs go가 돌고 있다(pid …)`로 거부(`--force`로도). 검사와 삭제가 모두 이 잠금 안이라 검사 직후 `gs go`가 끼어들 틈이 없다.
3. `finish.phase`가 `verified`·`reverted`가 아니면 `--force` 없이 거부: `gs clean: 마무리가 verified·reverted가 아니다(<phase 또는 없음>). --force가 필요하다`.
4. 지운다: `run/wt/` 아래 항목 전부와 git에 등록된 worktree 중 부모가 `run/wt/`인 것(`git worktree remove --force`, 등록이 풀린 잔여 디렉터리는 `rmtree`, symlink는 대상을 따라가지 않고 링크만), 로컬 `refs/heads/gs/<f>/*`(`branch -D`), 원격 `gs/<f>/*`(`ls-remote --heads`로 찾아 `push --delete`, 보호된 base의 `gs/<f>/revert`·`report` 포함. 먼저 실행 시작 때의 push 설정과 대조한다. 다르면 원격은 건드리지 않고 5의 경고로 남는다). worktree마다 `지움: worktree <절대 경로> (미커밋 변경도 지움)`.
5. 끝 줄 `지움: worktree <n>, 로컬 브랜치 <n>, 원격 브랜치 <n> · 실행 기록은 남김`. 항목 하나가 실패하면 `경고: 정리 실패: …`를 쓰고 나머지를 계속한 뒤 종료 1.

남기는 것: `run/state.json`, `run/lock`, `run/<NN>/<시도>/`, `run/finish/`, 커밋된 spec·티켓·report.md. state에서는 지운 경로와 이미 사라진 `run/wt/` 아래 경로만 뺀다(`kept_worktrees`, `failed_worktrees`, `worktree`). 지우지 못한 경로와 `run/wt/` 밖 경로는 남긴다. 그래서 미커밋 변경으로 worktree를 남겼던 실행도 정리 뒤 `gs go`가 위 "이미 끝남" 판정으로 아무것도 다시 만들지 않고, 남은 티켓이 있으면 평소처럼 재개한다.

## 진행 계산과 진행 바 mod

gs가 state를 쓸 때마다 `progress`를 계산해 같이 쓴다(`state.calculate_progress`, Python 시험). mod는 그리기만 한다.

**heartbeat** — state는 상태가 바뀔 때(`Run.save()`)만 쓰이므로, worker가 10분 넘게 단계를 바꾸지 않으면 mod의 10분 기준에 걸려 바가 사라졌다. 그래서 `go._wait_any`의 polling 루프가 상태 변화가 없어도 마지막 저장에서 `HEARTBEAT_SECONDS`(60초)가 지나면 `Run.save()`를 다시 불러 `updated_at`·`progress`(경과 시간 포함)와 파일 수정 시각을 새로 쓴다. mod 기준(10분)은 그대로다. heartbeat는 `_wait_any` 안에만 있으므로, 코디네이터가 동기로 기다리는 리뷰(`review.run`, 제한 `timeouts.review_minutes` 기본 30분)·재리뷰(`review.rereview`, 제한 `timeouts.rereview_minutes` 기본 10분)·검증(`verify.run`, 제한 `verify_minutes` 기본 20분)·병합·feature 마무리 동안에는 state가 다시 쓰이지 않는다(CI 대기만 10초마다 읽을 때 저장한다. 리뷰·판단 호출의 네트워크 대기도 60초마다 저장한다). 그 단계가 10분을 넘으면 정상 실행이어도 바가 사라졌다가 단계가 끝나 `save()`하면 돌아온다. 그러니 10분 넘게 안 바뀐 state가 곧 `gs go`가 죽었다는 뜻은 아니다. 죽었는지는 `gs status`가 `pid`의 생존으로 가린다(`실행 중`/`중단됨`).
```json
{"done": 3, "total": 8, "running": [{"id": "04", "phase": "review", "model": "codex"}],
 "elapsed_s": 1440, "eta_s": 2400, "line": "▓▓▓░░░░░ goldstack-v2 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음"}
```
- `done`: 이번 범위에서 merged·failed·skipped인 티켓 수. 막대는 8칸.
- `running`: 돌고 있는 티켓마다 마지막 단계와 그 모델(리뷰면 reviewer, 재리뷰면 부른 리뷰어들: `03 재리뷰 중(codex+agy)`, 2차 수정은 `03 수정 2 중(claude)`). 네트워크로 세워 둔 티켓(phase `network`)은 빠지고, line에 `network_label`(`네트워크 대기(2회, 3분 뒤)`) 한 칸이 들어간다. feature 전체 마무리 중이면 `{"id": "", "phase": "finish", "model": "claude"}` 하나(`마무리 중(claude)`). CI를 기다리면(`finish.phase`가 `checks_pending`) phase `checks`(`CI 대기 중`), integration·base worktree 준비 중이면 phase `setup`(`준비 중`). 티켓 준비는 그 티켓의 phase `setup`이다.
- `eta_s`: 이번 실행에서 끝난 티켓(이번 실행 전에 이미 병합된 티켓은 뺀다)의 평균 소요(재시도를 포함한 첫 단계부터 끝까지) × 남은 티켓 수 ÷ `max_workers`, 분 단위로 반올림.
- **ETA 표본이 없을 때**(이번 실행에서 끝난 티켓이 아직 없음): `gs go`가 실행을 시작할 때 한 번 `state.load_eta_history`로 이력 중앙값을 읽어 두고 그것을 평균 자리에 쓴다. line 끝에 `(이전 실행 기준)`이 붙는다(`약 26분 남음(이전 실행 기준)`). 이번 실행에서 티켓 하나라도 끝나면(merged·failed·skipped이고 시작·끝 시각이 있음) 이번 실행 평균으로 바뀌고 꼬리표가 빠진다. 이력도 없으면 `null`이고 line은 `남은 시간 계산 중`.
- **이력 표본**: 같은 레포의 `.goldstack/work/*/run/state.json` 중 **지금 feature를 뺀** 다른 feature의 것. 그 안의 `merged` 티켓마다 첫 단계 `started_at`(없으면 티켓 `started_at`)부터 `ended_at`까지(지난 시도 포함). 실패·건너뜀 티켓은 넣지 않는다. 모든 feature의 표본을 한데 모아 중앙값(평균이 아님: 멈춤·재시도로 길어진 티켓 하나에 덜 흔들린다). 깨졌거나 읽을 수 없는 state.json은 건너뛴다. `run/`은 gitignore라 이 머신에서 돌린 실행만 표본이 된다.

**mod**(`hooks/register.tsx`, `hooks/hooks.json`의 `modules`): 세션 시작 때와 1초마다(`$.clock.every(1000)`) `.goldstack/work`를 찾는다. 엔진의 `$.session.cwd()`가 세션 디렉터리를 절대 경로로 주고 `$.fs`는 절대 경로를 그대로 쓰므로, cwd에서 위로 올라가며 처음 만나는 `.goldstack/work`를 쓴다(레포 하위 디렉터리에서 연 세션도 보이고, 레포가 겹치면 가장 가까운 것). cwd를 묻지 못하면 예전처럼 cwd 바로 아래만 본다. 그 아래 `*/run/state.json` 중 최근 10분 안에 바뀐 것을 수정 시각이 가장 최근인 것부터 보며, `finished_at`이 빈 첫 파일의 `progress.line`을 `AbovePrompt`에 `Text`(dim, 끝 자름)로 그린다(끝난 실행은 건너뛴다). 고를 것이 없거나, 가장 최근 파일을 읽지 못하면(깨진 JSON 등) 더 오래된 실행으로 넘어가지 않고 아무것도 그리지 않는다(`next(e)`). 설문이 떠 있을 때도 그리지 않는다. 상태 계약은 `types/index.d.ts`(`goldstack.line`). 시험은 `claude plugin test .`(`hooks/register.test.tsx`).
mod의 hooks API는 early-access다. Claude Code 2.1.317에서 command hook과 `modules`를 같은 `hooks.json`에 두고 `claude plugin validate .`가 통과하며, `--plugin-dir`로 실은 세션에서 둘 다 로드됨을 확인했다. marketplace 설치본에서 mod가 안 뜨면 `--plugin-dir`이나 `CLAUDE_CODE_PLUGIN_DIRS`로 레포 디렉터리를 싣는다.

## 아이디어 함

`.goldstack/ideas/<slug>.md`가 아이디어 하나다. slug(소문자·숫자·`-`)가 파일 이름이자 id다. `README.md`는 형식 설명이라 아이디어가 아니다.
```
---
date: 2026-11-03          # YYYY-MM-DD, 필수
severity: high            # high | medium | low, 필수
source: goldstack-v2 리뷰 02   # 자유 문장, 필수
status: open              # open | taken | dropped, 필수
feature: ""               # status가 taken이면 필수(예: goldstack-v3)
---
<첫 줄: 한 줄 요약. 이어서 근거·생각. dropped면 끝에 `버린 이유: …` 한 줄>
```
줄 끝 `#` 설명은 형식을 보이려는 것이다. frontmatter는 spec·티켓과 같은 파서(`frontmatter.py`)로 읽는다: 한 줄 `key: value`, `: `·` # ` 등이 든 값은 따옴표로 감싼다. 날짜는 실제 날짜여야 한다.

쓰는 쪽: `/idea`(새 파일, 또는 비슷한 열린 아이디어 끝에 `- <날짜> <근거> (출처: …)` 줄), `/retro <feature>`(사람이 고른 후보를 `/idea` 형식으로), `/grill`(라운드 1에서 고른 아이디어를 `status: "taken"`, `feature: "<f>"`로). 셋 다 커밋하지 않는다. `/grill` 6단계와 `/go` 2단계의 커밋 경로에 `.goldstack/ideas`가 들어 있다(디렉터리가 없으면 `git add`에서 뺀다. `gs init`은 이 디렉터리를 만들지 않는다).

**`gs backlog [--all]`**(`backlog.py`) — 읽기 전용, 경고가 있어도 종료 0.
```
아이디어 (열림 3)
high    2026-11-03  pr-repo-flag  PR 명령이 git.remote를 따르지 않는다   (goldstack-v2 리뷰 02)
low     …
범위 밖 (다시 볼 조건)
same-file-serialization-check  v0 06처럼 blocked_by 누락 충돌로 티켓이 또 버려지면.
…
```
- 열: severity, date, slug, 본문 첫 줄, `(source)`. 정렬은 severity(high→medium→low) → date(오래된 것 먼저) → slug.
- `--all`: 머리가 `아이디어 (전체 N, 열림 M)`이고 date 뒤에 status 열을 더해 taken·dropped도 보인다.
- `README.md`는 건너뛴다. 형식이 틀린 파일(slug, 빠진 필수 키, 허용 밖 값, 날짜, taken인데 빈 feature 등)은 `경고: <파일>: <이유>`로 보이고 목록에서 뺀다. `.goldstack/ideas/`가 없으면 빈 목록. `gs check`는 아이디어를 보지 않는다(아이디어가 실행을 막을 이유가 없다).
- 범위 밖 줄: `.goldstack/out-of-scope/*.md`마다 `<slug>  <**다시 볼 조건**: 뒤 문장>`. 조건 줄이 없거나 비면 `(조건 없음)`.

## 텔레그램 알림

`gs go`가 끝날 때(요약 출력 직후) `notify.telegram = true`면 코디네이터가 한 통 보낸다. worker(`GS_ROLE=worker`)는 보내지 않는다.
```
✅ <feature> · <base> 병합
티켓 <병합>/<전체> 병합 · <분>분 · 남은 지적 <n>
PR <url>
```
종료 코드가 0이 아니면 한 줄: `❌ <feature> · <마무리 결과> · 티켓 <병합>/<전체> (<id> 실패: <이유 첫 줄>, …) · 보고서 .goldstack/work/<feature>/report.md`.
- 전송(`notify.py`): 표준 라이브러리 urllib로 `<api>/bot<TG_TOKEN>/sendMessage`(JSON, 링크 미리보기 끔). api는 `GS_TELEGRAM_API`, 없으면 `https://api.telegram.org`. 3900자를 넘으면 `… (잘림)`으로 자른다.
- 3번까지 시도한다(1초, 2초 쉬고). 연결 실패·5xx·429·응답 해석 실패는 재시도, 그 밖의 4xx(토큰·채팅 ID 오류)는 바로 멈춘다.
- 예외를 밖으로 내지 않는다. 토큰·채팅 ID가 없거나, `local.env`를 못 읽거나, 전송이 실패하면 stderr에 `경고: 텔레그램 …` 한 줄만 쓰고 종료 코드·보고서는 그대로다. 오류 문자열에서도 토큰을 `***`로 가린다.

## 모델 어댑터

`adapters.py`. 어댑터마다 같은 입력(brief, worktree, 로그 경로)을 받아 준비(`prepare`), 환경(`env`, 모두 `GS_ROLE=worker`, `GS_BRIEF`, `GS_WORKTREE`), 셸 명령(`command`), 종료 판정(`outcome`)을 한다. 실행 스크립트(`run.sh`)가 명령을 감싸 `worker.log`에 남기고 종료 코드를 `exit` 파일에 원자적으로 쓴다. 끝은 이 파일로 안다(화면을 읽어 추측하지 않는다).

worker의 모델·effort는 `.goldstack/config.toml`의 `[tiers.claude]`, `[tiers.codex]`, `[tiers.agy]`에서 고른다. 각 표는 `small`, `medium`, `large`를 `"모델/effort"`(effort 생략 가능)로 적는다. 티켓 frontmatter의 선택 키 `tier: small|medium|large`를 쓰며 생략하면 medium이다. 첫 실패 뒤 재시도는 한 단계 올린다(small→medium→large, large는 그대로). 수정 worker는 해당 구현 시도의 등급을 쓰고, 일시 오류 재시작은 등급을 올리지 않는다. 해당 계열의 표가 없으면 기존 선택(claude는 CLI 기본값, codex·agy는 `models.codex`·`models.agy`)을 보존하고 `gs check`가 경고한다. 표가 있으면 `models.codex`·`models.agy`보다 우선한다.

어댑터의 선택 인자 `ModelEffort`는 claude·agy에 `--model <모델> [--effort <effort>]`, codex에 `--model <모델> [-c model_reasoning_effort=<effort>]`를 넣는다. `state.json`의 티켓 `phases`에서 구현·수정 실행마다 `tier`, `actual_model`, `effort`를 보존한다(빈 모델·effort는 CLI 사용자 기본값, 기존 `model`은 계열). 옛 state의 항목에는 이 키가 없어도 된다.

첫 리뷰는 `[tiers] review`(기본 large), 재리뷰는 `rereview`(기본 medium)의 모델·effort를 같은 인자로 넘긴다. 계열 표가 없으면 위 reviewer 명령의 기존 모델과 CLI 기본 effort를 쓴다. 선택은 티켓 등급과 무관하며, 각 리뷰와 회차별 `rereviews` 기록에 `tier`·`actual_model`·`effort`를 남긴다. 실패 요약만 `[models] failure_summary`를 쓰고, 생략하면 `models.judge`를 읽는다. 지적 분류와 보고서 Summary는 계속 `models.judge`다.

`transient_reason(inp)`은 종료 판정과 별개로 `transient.reason(family, text, model=..., cwd=...)`에 로그를 넘겨 일시 오류 이유를 돌려준다(없으면 빈 문자열). 연결·DNS·5xx·429만 인정하고 인증·구독 한도·모르는 오류는 제외한다. claude는 마지막 result, codex는 error·turn.failed 이벤트를 읽어 도구 출력 속 문자열을 무시한다. agy의 `invalid model selection`은 `agy models`(`GS_AGY` seam, 15초 제한)가 실패하거나 선택한 모델이 목록에 있을 때 일시 오류다. 목록에 모델이 없으면 설정 오류다. 이 판별 자체는 대기나 재시작을 하지 않는다.

| model | 명령 | 차단 장치 |
|---|---|---|
| claude | `claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --disallowedTools "Bash(git push *)" "Bash(gh *)" --settings '{"enabledPlugins":{<goldstack 밖 플러그인>:false,…}}' --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands < brief` | plugin hook + 도구 차단 |
| codex | `codex exec --json -s workspace-write [--model <models.codex>] -c sandbox_workspace_write.network_access=false --skip-git-repo-check -C <wt> --add-dir … "<안내>" < brief` | sandbox(네트워크 꺼짐, worktree 밖 쓰기 불가) |
| agy | `agy -p "$(cat brief)" --output-format stream-json --dangerously-skip-permissions --disable-slash-commands --settings '<deny 규칙>' --model <models.agy>` | deny 규칙 + `gs hook agy-pretooluse`(두 겹) |

**worker 명령이 정해진 이유(v4 조사)** — 08·09 티켓이 실제 CLI를 돌려 확인하고 정했다.

| worker | 정한 것 | 근거 |
|---|---|---|
| claude | **격리한다.** goldstack 밖 플러그인은 `--settings`의 `enabledPlugins`로 이 세션에서만 끄고, MCP 서버는 빈 `--strict-mcp-config`, skill·명령은 `--disable-slash-commands`로 뺀다. goldstack 플러그인(그 PreToolUse hook)과 사용자 설정·프로젝트 `CLAUDE.md`는 남는다. 끌 목록은 worker를 띄울 때 worktree에서 `claude plugin list --json`(`GS_CLAUDE`)으로 읽어, 이름이 `goldstack`인 것만 빼고 모두 `false`. 못 읽으면 `--settings`만 빼고 나머지 격리는 넣는다(fail-open: 격리는 문맥 정리라 worker를 거부하지 않는다). 그 사실은 `플러그인 격리 못 함: …`으로 worker 종료 메모와 state `isolation_warnings`에 남아, 보고서 Evidence 맨 앞 `### 남은 위험`과 티켓별 결과의 이유에 나온다. `--bare`(OAuth 로그인을 못 읽음)·`--safe-mode`(CLAUDE.md·goldstack hook까지 꺼짐)·`--setting-sources`(사용자 설정이 빠짐)는 쓰지 않는다. 못 빼는 것: builtin 플러그인과 내장 agent | [research/worker-plugin-isolation.md](research/worker-plugin-isolation.md) |
| codex | **sandbox 그대로, hook으로 바꾸지 않는다.** codex 0.166.0의 PreToolUse hook은 fail-open이다(hook이 종료 1·시간 초과·없음·kill·깨진 출력이면 흔적 없이 통과). apply_patch도 hook으로 오고 `--dangerously-bypass-hook-trust`로 무인 실행에서 걸리지만, 기준(fail-closed)을 못 넘어 코드를 바꾸지 않았다. 그래서 opt-in 설정(`[codex] guard` 같은 키)도 **없다**. config에 적으면 모르는 섹션 경고가 난다. 다시 볼 조건과 그때 할 일은 연구 문서 §4, 아이디어 `.goldstack/ideas/codex-worker-hook.md`(open) | [research/codex-hook.md](research/codex-hook.md) |
| agy | deny 규칙 + worktree `.agents/hooks.json`의 `gs hook agy-pretooluse`, 띄우기 전 `agy -p /hooks`로 확인(아래) | [research/agy.md](research/agy.md), [research/adapters-run.md](research/adapters-run.md) |

그 밖의 `docs/research/`: [pstack.md](research/pstack.md), [mattpocock-skills.md](research/mattpocock-skills.md), [comparison.md](research/comparison.md)(참고한 kit 분석).

모든 worker는 어댑터와 별개로 push·gh가 막힌 환경에서 돈다: `GIT_CONFIG_*` env로 모든 push URL을 만들 수 없는 경로(`/dev/null/gs-worker-push-blocked/`)로 바꾸고(`pushInsteadOf`, 원격의 `pushurl`은 `insteadOf`), `GH_TOKEN`을 틀린 값으로 둔다. fetch·commit은 된다. gs 자신의 push는 이 환경 밖에서 돈다.

- **codex**: worktree의 git 디렉터리는 주 레포 `.git/` 아래라 sandbox 밖이다. 그대로면 커밋이 `index.lock: Operation not permitted`로 실패하고, `.git` 전체를 `--add-dir`해도 codex가 막는다. 그래서 이 worktree의 git 디렉터리, `objects`, 이 브랜치의 ref·reflog 디렉터리만 연다. sandbox에서 못 도는 시험(네트워크, localhost, 홈 디렉터리 쓰기)은 실패로 보지 말고 커밋하라는 안내를 brief 앞에 붙인다. 검증은 gs가 sandbox 밖에서 다시 돌린다.
- **agy**([research/agy.md](research/agy.md) §6): `--mode auto`, `--sandbox`, `--print-timeout`은 넣지 않는다. hook은 worktree의 `.agents/hooks.json`에 쓰고 git exclude(`/.agents/hooks.json`)에 넣는다(레포가 그 파일을 추적하거나 링크면 거부). 전역 agy 설정은 건드리지 않는다. hook 명령은 지금 도는 gs와 같은 python(`<python> -m gs.cli hook agy-pretooluse`)이다. agy 입력(`toolCall`)을 Claude hook의 판정 입력으로 바꾸고 stdout JSON(`{"decision":"deny","reason":…}`)으로 답한다. `lastUserInput`(프롬프트)은 보지 않는다. worktree의 `.agents/`를 바꾸거나 읽는 일도 막는다.
  띄우기 전에 `agy -p /hooks`(모델 호출 없음)에 gs hook 줄이 있는지, hook 명령이 실제로 `git push`를 막는지 확인한다. 둘 중 하나라도 아니면 그 티켓을 실패로 적고 worker를 띄우지 않는다. `gs check`도 범위에 agy 구현 티켓이 있으면 같은 확인을 버리는 디렉터리에서 해서, 안 되면 경고한다.
  종료 0은 성공이 아니다. 성공은 종료 0 + 마지막 이벤트가 `result`이고 `status: SUCCESS` + `finished_reason` 없음이다. `warning:` 줄(모드 무시 같은 조용한 강등), ERROR 단계 수, `denied_actions`는 실패 이유·로그 메모에 붙는다.

## plugin, worker 차단 hook, mod

이 레포가 곧 plugin이자 로컬 marketplace다(`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `hooks/hooks.json`, `skills/`). 설치는 [README](../README.md#설치). plugin 검사는 `claude plugin validate .`(spec verify에 들어 있다).

`hooks/hooks.json`에는 둘이 있다: PreToolUse command hook(matcher `Bash|Read|Write|Edit|MultiEdit|NotebookEdit|Grep|Glob`)과 진행 바 mod(`"modules": ["./register.tsx"]`).

PreToolUse hook 명령은 `GS_ROLE`이 `worker`가 아니면 바로 `exit 0`이다(입력도 읽지 않고 `gs`도 부르지 않는다. 일반 세션에 영향 없고 `gs`가 없어도 조용하다). worker면 `exec gs hook pretooluse`, PATH에 `gs`가 없으면 막는다(종료 2). `gs go`는 worker 실행 스크립트에 `GS_ROLE=worker`, `GS_WORKTREE`를 넣는다. worker일 때 막는 것은 되돌릴 수 없는 일뿐이다:
- `git push`(모든 형태: `-C`, `cd .. &&`, `bash -c`, `$(…)` 안), force 계열(`--force`, `--force-with-lease`, `--force-if-includes`, `push -f`, `+refspec`)
- `gh` 쓰기 명령(`pr create`·`merge`·`close`, `release …`, `repo …`, 쓰기 `gh api` 등). 읽기(`pr view`, `run view` …)는 통과
- worktree 밖 쓰기(Write·Edit 도구, 셸 리다이렉션·`rm`·`mv`·`cp`·`tee`, 밖에서 하는 `git commit` 등). 임시 디렉터리(`/tmp`, `/var/folders`, `$TMPDIR`)와 `/dev`는 통과
- 비밀 파일 읽기: `~/.ssh`, `~/.aws`, `~/.gnupg`, `.env`·`.env.*`(`.env.example`·`.sample`·`.template`·`.dist` 제외), `.netrc`, `.git-credentials`, `.pypirc`, 개인 키(`id_rsa` 등), `.goldstack/local.env`, gh `hosts.yml`, `.kube/config`, `.docker/config.json`, `gh auth token`
- 공용 git 설정 쓰기: `git remote` 변경(`set-url`, `add`, `remove`, `rename` 등. `show`, `get-url`, `update`, `prune`, 목록은 통과), `git config` 쓰기(`--global` 포함). 읽기(`--get*`, `--list`, 이름 하나, `git config get`·`list`)는 통과하고, 모르는 옵션과 줄임말은 쓰기로 본다. `git -c 키=값 <명령>`은 그 명령에서만 들어 통과
- 자기 브랜치 밖의 ref를 옮기는 일: `git update-ref`(`--stdin`은 볼 수 없어 막음), `git branch -f`·`-d`·`-D`·`-m`·`-M`·`-c`·`-C`, `git symbolic-ref` 쓰기. 자기 브랜치는 worktree의 `HEAD`가 가리키는 ref이고, `HEAD` 자체의 `update-ref`는 통과. 이 예외는 git이 이 worktree를 볼 때만이다. `-C`·`cd`로 밖을 가리키거나, 모르는 곳으로 `cd`하거나, `--git-dir`·`--work-tree`·`GIT_DIR=` 등으로 위치를 따로 주면(`export`, `bash -c` 앞의 대입 포함) `HEAD`도 자기 것으로 보지 않는다. `xargs`의 치환 문자열(`-I`, `-J`, `-i`, `--replace`)이 든 단어는 입력으로 바뀌므로 모르는 값으로 본다. `sh -c` 안까지 듣는다(`xargs -I HEAD git update-ref HEAD HEAD~1`의 `HEAD`는 자기 것이 아니다). 치환 문자열이 명령 이름에 들면 무엇을 돌리는지 볼 수 없어 막는다. 분리 HEAD면 자기 브랜치가 없다. 새 브랜치 만들기와 `git reset`은 통과

worktree는 설정과 ref를 주 레포와 공유해서 이 둘을 막는다. 임시 디렉터리의 버리는 레포(`git -C /tmp/x config …`, `cd /tmp/x && git config …`)는 공유하지 않아 통과한다. `-C`·`cd`·`--git-dir`·`GIT_DIR=`(`export` 포함)·`-f`가 가리키는 곳이 전부 임시 디렉터리여야 하고, 모르는 변수(`$X`)가 끼면 막는다. `--global`·`--system`은 언제나 막는다. hook은 안전띠라 이것만으로 끝나지 않는다. 위 "마무리"의 push 전 대조가 함께 있다. `git fetch origin x:main`, `git checkout -B`, `git tag -f`로 ref를 옮기는 길은 이 hook이 보지 않는다.

비밀 읽기 검사는 직접 지정한 경로 외에 파일 이름 glob(`cat .goldstack/local.e*`, `cat .goldstack/*.env`, `head .goldstack/local.?nv`)과 알려진 재귀 검색(`grep -r`·`grep -R`·`rg`·`find`)의 시작점도 본다. 시작점 아래에 비밀 파일이 있으면 검색을 막는다(내용은 읽지 않고 경로를 검사한다). Grep·Glob 도구도 `path` 아래에 비밀이 있으면 막으며, 시작점을 생략하면 현재 디렉터리를 검사한다. 이 규칙은 `gh/hosts.yml` 등 다른 비밀 경로에도 같다. 검색 필터가 비밀 파일을 제외해도 시작점이 비밀을 품으면 막는다.

worker worktree는 주 레포의 `.goldstack/work/<f>/run/wt/` 아래에 있지만, 조상에 `.goldstack`이 있다는 이유로 막지는 않는다. 검색 시작점의 자손만 검사하므로 worktree 안에 비밀이 없으면 `rg foo`, `grep -r foo src`, Grep·Glob 검색은 통과하고, `.goldstack/work/<f>/spec.md`도 읽을 수 있다. 반대로 주 레포나 주 레포의 `.goldstack`에서 시작한 재귀 검색은 그 아래 `local.env`가 있으면 막는다.

막으면 이유와 "이 일은 `gs`가 한다"를 돌려준다. worker에서 hook 입력을 해석하지 못하면 막는다(fail closed). **hook은 안전띠이며 비밀을 격리하는 보안 경계가 아니다.** `python -c "open(...)"`처럼 코드 안에서 파일을 여는 일, 다른 인터프리터·스크립트 본문의 읽기, 셸에서 동적으로 만든 경로는 모두 해석하지 못한다. 심볼릭 링크 대상도 비밀 읽기 판정에서 보장하지 않으며, 디렉터리 재귀 검사에서는 링크를 따라가지 않는다. 검사 후 파일이 바뀌는 경우도 막지 못한다. 따라서 **값어치 낮은 비밀만 `local.env`에 둔다.** claude worker 명령의 도구 차단 옵션과 push·gh 차단 환경을 함께 두고(여러 겹), codex는 sandbox, agy는 deny 규칙과 `gs hook agy-pretooluse`를 쓴다. codex의 비밀 읽기를 이 hook으로 막는 것은 범위 밖이다.

**`/adopt`와 profile** — `/adopt`는 `.goldstack/profile.md`를 쓴다(절: 구조, 빌드·시험, 관례, 주의점, CI). 커밋하지 않는다. `/grill` 1단계가 가장 먼저 읽고, `/grill` 6단계·`/go` 2단계의 커밋 경로에 들어 있다. worker brief에는 내용 대신 포인터 한 줄 "먼저 `.goldstack/profile.md`를 읽어라"가 들어간다(`worker.py`, 그 worktree에 파일이 있을 때만).

skill은 `skills/<이름>/SKILL.md`다. `diagnosing-bugs`만 모델 호출이고 나머지는 `disable-model-invocation: true`(사용자 호출)라 description이 늘 문맥에 실리지 않는다. 옮겨 온 다섯 skill의 출처는 [skills/NOTICE-mattpocock.md](../skills/NOTICE-mattpocock.md).

## 실행 디렉터리

`.goldstack/work/<f>/run/`(gitignore):
```
state.json, lock
<NN>/<시도>/          brief.md, setup.log, run.sh, worker.log, exit, verify.log, merge.log,
                      failure.log, failure-summary.md, judge.log, review/, review-<계열>/, fix/, fix2/,
                      fix-net<k>/, fix2-net<k>/(끊겨서 다시 띄운 수정 worker), rereview<회차>-<계열>/
integration/<시도>/   setup.log
wt/integration        integration worktree(gs만 쓴다, verified면 자동 정리)
wt/<NN>, wt/<NN>-retry-<k>   티켓 worktree(병합되면 정리, 실패면 보존 → gs clean)
gs-main-*/base        base 검증 임시 worktree(끝나면 지운다)
gs-review-*/wt        첫 리뷰 임시 worktree(티켓 worktree가 head와 다를 때만, 끝나면 지운다)
gs-rereview-*/wt      재리뷰 임시 worktree(티켓 worktree가 수정 head와 다를 때만, 끝나면 지운다)
finish/               summary.md, report-input.md, diff-stat.txt, report-judge.log, setup.log(base 준비),
                      integration-verify.log, integration-final-verify.log, integration-recheck-verify.log,
                      main-verify.log, main-recheck-verify.log
```

## 시험 seam

바꿔 끼우는 환경 변수. 시험이 실제 모델·네트워크 없이 엔진을 돌리는 데 쓴다.

| 변수 | 바꾸는 것 |
|---|---|
| `GS_RUNNER=subprocess\|herdr` | worker 실행기(기본: herdr 안이면 herdr) |
| `GS_WORKER_CMD` | worker 셸 명령. 어댑터(준비·판정)를 건너뛴다 |
| `GS_REVIEWER_CMD` | reviewer 셸 명령(stdin = 프롬프트, stdout = JSON 답) |
| `GS_JUDGE` | 판단 모델(실패 요약·리뷰 분류·보고서)로 부를 Claude CLI 경로 |
| `GS_GH` | `gh` 경로 |
| `GS_AGY` | `agy` 경로 |
| `GS_CLAUDE` | claude worker의 플러그인 목록(`claude plugin list --json`)을 읽을 Claude CLI 경로 |
| `GS_UV` | self-update의 uv 실행 파일(기본 `uv`). 시험에서 가짜 설치 명령으로 바꾼다 |
| `GS_VERIFY_TIMEOUT` | verify 시간 제한(초). spec `verify_minutes`를 덮는다 |
| `GS_NETWORK_MINUTE` | 네트워크 대기·회복 판단의 1분(초). 틀린 값이면 60 |
| `GS_TELEGRAM_API` | 텔레그램 Bot API 주소(기본 `https://api.telegram.org`). 시험은 localhost 가짜 서버 |
