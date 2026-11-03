# goldstack 엔진 명세

`gs`가 안에서 하는 일. 쓰는 법은 [guide.md](guide.md), 첫 화면은 [README](../README.md). 코드는 `src/gs/`, 시험은 `tests/`(`uv run python -m unittest discover -s tests`), plugin은 `.claude-plugin/`·`hooks/`·`skills/`.

| 파일 | 하는 일 |
|---|---|
| `cli.py` | `gs` 명령줄: `init`, `config`, `migrate`, `check`, `go`, `status`, `backlog`, `hook` |
| `config.py` | `.goldstack/config.toml` 읽기·검사, `local.env` 읽기, `gs init` |
| `feature.py`, `frontmatter.py`, `graph.py`, `check.py` | spec·티켓 읽기, 그래프(순환, 없는 id, 위상 순서, frontier), 환경 검사 |
| `go.py` | `gs go` 코디네이터: 병렬 루프, 병합·검증, 재시도, 요약 출력, 알림 |
| `worker.py`, `herdr.py`, `adapters.py`, `streamfmt.py` | worker 띄우기(brief, 실행 스크립트, push 차단), herdr pane, 모델별 명령·판정, pane 출력 정리 |
| `review.py` | 다른 계열 리뷰와 판단 모델의 fix·report 분류 |
| `verify.py`, `failure.py` | verify 명령(시간 제한, 프로세스 그룹), 실패 증거와 요약 |
| `finish.py`, `report.py` | 보고서, PR, 병합 확인, base 재검증, revert |
| `state.py`, `status.py` | `state.json`, 잠금, 단계 시각, 진행 계산, `gs status` |
| `notify.py` | 텔레그램 전송 |
| `hook.py`, `hook_agy.py` | worker 차단 판정(Claude Code, agy) |
| `migrate.py` | `gs migrate` |
| `backlog.py` | `gs backlog`: 아이디어 파일 읽기·검사, 범위 밖 다시 볼 조건 |
| `git.py` | git 호출, 원격 URL에서 GitHub owner/repo 풀기(`github_repo`) |

## 대상 레포의 파일 배치

goldstack은 사용자 머신·레포를 가정하지 않는다. 레포마다 값은 대상 레포 안의 파일에 두고, 비어 있으면 채우라고 안내한다.
```
.goldstack/config.toml          커밋. 레포마다 값(gs init이 쓴다)
.goldstack/local.env            gitignore. 비밀(TG_TOKEN, TG_CHAT_ID)
.goldstack/local.env.example    커밋. 빈 값 + 채우는 법 안내
.goldstack/work/<feature>/      spec.md, tickets/NN-slug.md, report.md (run/은 gitignore)
.goldstack/out-of-scope/        grill이 뺀 개념
.goldstack/ideas/               아이디어 함: <slug>.md 하나씩(아래 "아이디어 함"), README.md는 형식 설명
```
`gs init`이 `.gitignore`에 넣는 줄: `.goldstack/local.env`, `.goldstack/work/*/run/`. 레포 루트는 지금 디렉터리에서 위로 `.git`을 찾는다(`--repo`로 지정 가능). 옛 위치(`.work/`, `.out-of-scope/`, `.ideas/`)는 읽지 않는다. `gs migrate`로 옮긴다.

## 설정

**`config.toml`** — `gs init`이 전부 쓴다. 빠진 섹션·키와 형이 틀린 값(문자열·정수·불리언, 불리언은 정수로 받지 않는다)은 오류, 모르는 섹션·키는 경고. 값 범위도 본다: `timeouts.*`가 0 이하면 오류, `models.*`가 비었거나 공백뿐이면 오류(`models.codex`만 빈 값 허용: codex 기본 모델). 없으면 `gs check`·`gs go`·`gs config`가 "`gs init`을 먼저" 오류로 멈춘다(내장 기본값으로 돌지 않는다). `gs go`는 시작할 때 한 번 읽어 그 실행의 모든 호출에 쓴다.

| 키 | 기본 | 쓰는 곳 |
|---|---|---|
| `git.remote` | `"origin"` | fetch, integration push, base push(revert·최종 보고서), PR 저장소(URL의 owner/repo → `gh pr … --repo`) |
| `git.base` | `origin/HEAD`의 브랜치(없으면 `"main"`) | PR 대상, worker·integration의 출발점(`<remote>/<base>`), 재검증 |
| `models.judge` | `"opus"` | 판단 모델 `claude -p --model`: 실패 요약, 리뷰 분류, 보고서 요약 |
| `models.claude_review` | `"opus"` | reviewer가 claude일 때 `--model` |
| `models.agy` | `"gemini-4-argon-high"` | agy worker·reviewer `--model` |
| `models.codex` | `""` | codex worker·reviewer `--model`. 비우면 옵션을 넣지 않는다(codex 기본) |
| `timeouts.review_minutes` | `30` | reviewer 호출 시간 제한 |
| `timeouts.judge_minutes` | `10` | 리뷰 분류·보고서 요약 호출 시간 제한 |
| `timeouts.summary_seconds` | `60` | 재시도용 실패 요약 호출 시간 제한 |
| `notify.telegram` | `false` | `gs go` 끝 알림 |

`gs config <섹션.키>`는 값 한 줄을 출력한다(불리언은 `true`/`false`). 없는 키는 종료 1. `/go` skill이 `gs config git.base`, `gs config git.remote`로 base를 읽는다.

**`local.env`** — `KEY=value` 줄, `#` 주석. gs는 이 파일만 읽고 `os.environ`은 보지 않는다(원천 하나). 토큰은 출력·로그에 쓰지 않는다. worker 차단 hook이 이 파일 읽기를 막는다.

**spec frontmatter**(feature마다) — `feature`(디렉터리 이름과 같아야 한다), `verify`(비어 있지 않은 한 줄 셸 명령)는 필수. 숫자 키는 모두 1 이상 정수: `max_workers`(기본 3), `idle_minutes`(기본 20), `verify_minutes`(기본 20). 그 밖의 키는 경고, 0·정수 아닌 값은 오류.

**티켓 frontmatter** — `id`, `title`, `blocked_by`(목록, 없으면 `[]`), `model`, `reviewer`가 모두 필요. 파일 이름은 `<id>-`로 시작한다. `model`·`reviewer`는 `claude|codex|agy` 중 하나이고 서로 달라야 한다. `gs check`는 없는 id 참조, 순환, 겹치는 id를 오류로 본다.

**`gs check`의 환경 검사** — `git`, `gh`, `claude`(판단 모델은 티켓 모델과 무관하게 늘 claude다)와 범위 안 티켓의 `model`·`reviewer` CLI가 PATH에 없으면 오류. `git.remote`의 URL에서 GitHub owner/repo를 풀지 못하면 오류(``원격 `origin`의 URL `…`은 GitHub 저장소 형식이 아니다``). `https://github.com/o/r`, `git@github.com:o/r`, `ssh://git@github.com/o/r` 꼴을 받고 `.git` 접미사는 대소문자 없이 뗀다. `git remote get-url`(insteadOf 적용)이 GitHub가 아니면 원격에 직접 설정된 `remote.<이름>.url`을 다시 본다(시험·미러용 insteadOf). 아이디어 파일은 보지 않는다. `notify.telegram`이 켜졌는데 `local.env`에 `TG_TOKEN`·`TG_CHAT_ID`가 없으면 경고. 범위에 agy 구현 티켓이 있으면 버리는 디렉터리에서 agy 차단 장치를 확인해 안 되면 경고(아래 "모델 어댑터"). `gs go`는 같은 검사를 먼저 하고 오류가 있으면 아무것도 띄우지 않는다.

## `gs go`의 흐름

1. 검사 → 잠금(`run/lock`) → `git fetch <remote> <base>`.
2. `.goldstack/work/<f>/spec.md`와 `tickets/`가 커밋돼 있고 `<remote>/<base>`와 같은지 본다. 다르면 시작하지 않는다(worker는 `<remote>/<base>` 기준으로 일한다). `report.md`는 보지 않는다.
3. state를 읽어 실행을 시작하고, integration worktree(`run/wt/integration`, 브랜치 `gs/<f>/integration`)를 준비한다: 남은 병합·변경을 버리고 `<remote>/<base>`를 합친다.
4. integration의 병합 표시(`gs-ticket: <f>/<NN>` 트레일러)로 이미 병합된 티켓을 회복한다. 지난 마무리가 PR 병합 대기·병합 뒤·main 검증 실패에서 멈췄으면 그것부터 이어 간다.
5. 티켓 루프(병렬, 리뷰, 재시도) → 마무리(보고서, PR, 병합, base 재검증) → `finished_at` 기록 → 요약 출력 → 알림.

종료 코드는 모든 티켓이 병합되고 마무리가 끝났을 때(base 검증 통과)만 0이다. 병합 대기와 base 검증 실패도 1이다.

## 상태

`run/state.json`이 상태의 원천이다. `gs go`의 요약·보고서·PR 본문·알림, `gs status`, 진행 바 mod가 모두 이 파일을 읽는다. 쓰기는 같은 디렉터리의 임시 파일 뒤 rename(원자적)이다.
- 위: `feature`, `pid`(마지막으로 쓴 `gs go`), `only`, `started_at`, `updated_at`(heartbeat로 상태가 그대로여도 60초마다 바뀐다), `finished_at`, `phase`(feature 전체 마무리 중이면 `finish`), `finish`(마무리 재개 지점: `phase`, `outcome`, `url`, `merge_sha`, `revert_sha`, `integration_ok`, `main_ok`, `base_report_tried`, `base_report` 등), `progress`.
- 티켓마다: `status`(`pending`, `running`, `merged`, `failed`, `skipped`), `attempts`, `branch`, `pane`(`pane <id>` 또는 `pid <n>`), `started_at`·`ended_at`, `log`, `reason`, `worktree`, `failures`, `failed_worktrees`, `kept_worktrees`, `failure_summary`, `review`, `phases`.
- `phases`: 단계 전환마다 `{attempt, phase, model, started_at, ended_at}`를 더한다. phase는 `worker`, `review`, `fix`, `verify`, `finish`(티켓을 integration에 커밋하는 순간). 보고서의 단계별 소요가 이것을 합산한다(지난 시도 포함). 분으로 반올림해 0분인 단계(대개 순간인 `finish`)는 줄에서 빼고, 모두 0분이면 `모두 1분 미만`이다.

다시 실행하면 integration에 병합된 티켓은 건너뛰고, 실패·건너뜀 티켓은 `failures`·요약·이유를 비우고 다시 한다. state는 merged인데 integration에 표시가 없으면 다시 한다. 지난 `gs`가 죽어 `running`으로 남은 티켓은 실패로 세지 않고(`attempts`에서 하나 뺀다) 새로 시작한다. 그 시도의 worker가 살아 있으면(명령줄에 그 시도의 `run.sh`가 있는 프로세스) 먼저 끝내고 herdr pane도 닫는다.

같은 feature에 `gs go`는 하나만 돈다: `run/lock`에 flock을 잡고 pid를 적는다. 프로세스가 죽으면 커널이 잠금을 풀어 저절로 회수된다. "돌고 있나"는 적힌 pid가 아니라 잠금이 실제로 잡혔는지로 판단한다(`gs status`는 공유 잠금을 잠깐 잡아 본다).

`gs status [<feature>]`는 읽기 전용이다. 표의 경과는 티켓 시작부터(끝났으면 끝까지, 돌고 있으면 지금까지), 마지막 출력은 worker 로그의 수정 시각이다. 표 아래에 `progress.line`을 보인다.

## 병렬 실행

frontier(대기 중이고 막는 티켓이 모두 병합된 것)를 spec의 `max_workers`개까지 위상 순서대로 띄운다. worker 하나가 끝날 때마다 state에서 frontier를 다시 계산해 빈자리를 채운다. `max_workers: 1`이면 위상 순서로 하나씩 돈다. `--only`면 그 부분 그래프만 돌고, 범위 밖 의존은 끝났다고 본다.

- worker마다 최신 integration 끝에서 브랜치 `gs/<f>/<NN>`과 worktree `run/wt/<NN>`을 만든다. 재시도는 `gs/<f>/<NN>-retry-<k>`, `run/wt/<NN>-retry-<k>`. 번호는 시도 디렉터리 `run/<NN>/<시도>`로 정한다.
- herdr 안이면(`HERDR_SOCKET_PATH`·`HERDR_SESSION`) 지금 workspace(없으면 새 workspace `gs:<f>`)의 탭 `gs:<f>`에 worker마다 새 pane을 연다. 성공한 pane은 닫고 실패한 pane은 남긴다. herdr 밖이면 subprocess로 돈다.
- 루프는 스레드 하나다. 리뷰·병합·검증은 이 루프에서 한 번에 하나씩 한다(다른 worker는 그동안 각자 돈다).
- 병합: 먼저 최신 integration 끝을 티켓 브랜치에 합쳐 본다(충돌이면 이유 `conflict`). 그다음 integration에 `--no-ff --no-commit`으로 합치고(충돌이면 `integration 병합 충돌`) verify를 돌려, 통과하고 그 사이 integration이 바뀌지 않았을 때만 `Merge <NN>: <title>` + 트레일러 `gs-ticket: <f>/<NN>` 커밋을 만든다. 중간에 죽으면 표시 없는 미완 병합만 남고 다음 실행이 버린다.
- worker가 integration worktree를 건드렸으면 되돌린다. 그때 돌던 worker가 그것 하나면 그 티켓의 실패, 여럿이면 누구 짓인지 몰라 경고만 한다.

## 실패 처리

- **멈춤**: worker의 로그 출력도 브랜치의 새 커밋도 없이 spec의 `idle_minutes`가 지나면 프로세스와 pane을 끝낸다(`시간 초과: <N>분 동안 로그 출력·새 커밋 없음`).
- **verify 시간 제한**: 티켓 병합 전, `integration`, `integration-final`, `main`, `main-recheck` 검증이 모두 `verify.py`를 쓴다. 명령은 새 프로세스 그룹에서 `bash -c`로 돈다. 제한은 `GS_VERIFY_TIMEOUT`(초)이 있으면 그것, 없으면 spec `verify_minutes`. 넘기면 그룹 전체에 SIGTERM, 5초 뒤 남았으면 SIGKILL을 보내 자손까지 끝내고, 로그 끝에 `시간 초과: <N>분`을 남겨 검증 실패로 친다: 티켓이면 `검증 시간 초과(<N>분, 로그 <경로>)`로 재시도, integration이면 병합 안 함, base면 병합 커밋 revert.
- **재시도**: 티켓 실패(종료 코드, 커밋 없음, 멈춤, 검증 실패(시간 초과 포함), 병합 충돌, 띄우기 실패 등)는 모두 같은 모델로 한 번 재시도한다. 최신 integration에서 새 브랜치·worktree를 만들고, 새 판단 모델 호출이 요약한 실패 로그(`failure-summary.md`)를 brief에 붙인다. 요약 호출이 실패하면 증거 파일 경로를 붙인다. 실패 횟수는 요약 호출 전에 state에 적어 중간에 죽어도 재시도 한도가 늘지 않는다.
- 두 번째 실패는 `failed`, 그 티켓에 직접·간접으로 막힌 티켓은 `skipped`(`막힘: <id>`)로 두고 나머지는 계속한다.
- 증거: 시도마다 `failure.log`(이유 + worker·verify·merge 로그 끝 64KiB), `failure-summary.md`, `judge.log`. 실패 worktree는 지우지 않고 `failed_worktrees`에 남긴다.
- 한 티켓의 준비·확인·병합 중 오류(git, herdr, 파일, 어댑터)는 그 티켓의 실패로 한정한다. 예상 못 한 오류로 루프를 떠나도 띄운 worker를 끝낸다.

**worktree 정리** — 티켓이 integration에 병합되면 성공한 시도의 worktree를 바로 지우고(`--force` 없이) `[NN] worktree 정리: <경로>`를 출력한다. 로컬 티켓 브랜치는 끝이 integration에 포함될 때만(`merge-base --is-ancestor`) 지우고, 아니면 경고하고 남긴다. 병합된 worktree에 미커밋 변경이 있으면 worktree·브랜치를 모두 남기고 `kept_worktrees`에 적으며 보고서 티켓 결과에 `남긴 worktree: <경로> (미커밋 변경)`을 표시한다. 재시작 때도 이미 병합된 티켓의 남은 worktree·브랜치를 같은 규칙으로 정리한다. `kept_worktrees`의 옛 경로는 티켓이 다시 대기로 돌아가거나 새 시도를 띄울 때 다시 본다: 경로가 없거나 미커밋 변경이 없어졌으면 worktree를 정리하고 목록에서 뺀다. 그 worktree의 실제 브랜치가 티켓 브랜치와 다르면(분리 HEAD 포함. 사람이 거기서 커밋했을 수 있다) 경고하고 남긴다. 브랜치는 끝이 integration에 있을 때만 지운다. `--only` 범위 밖 티켓이 남긴 worktree도 보고서 티켓별 결과 아래 `범위 밖 티켓의 남긴 worktree:`에 나온다. 실패한 시도의 worktree·브랜치, integration worktree, 로컬·원격 integration 브랜치는 남긴다. 정리 오류는 경고만 하고 티켓의 merged 상태를 바꾸지 않는다.

## 리뷰

worker가 성공하면 병합 전에 티켓의 `reviewer`가 그 티켓 diff(최신 integration과의 merge-base 기준)를 읽기 전용으로 리뷰한다. 구현 `model`과 같은 계열이면 부르지 않고 그 티켓을 실패시킨다.
1. reviewer에게 diff·티켓·spec·worktree 경로를 준다. 답은 고정 JSON `{"findings": [{"severity": "high|medium|low", "location", "claim", "evidence"}]}`. 시간 제한 `timeouts.review_minutes`.
2. 새 판단 모델 호출(`models.judge`, 파일 경로만 받는다, 제한 `timeouts.judge_minutes`)이 지적마다 `fix`·`report`를 정한다. 근거(evidence)가 빈 지적은 늘 `report`다(코드 규칙: 취향은 고치지 않는다). 판단 모델이 실패하면 모두 `report`.
3. `fix`가 있으면 같은 구현 모델로 수정 worker를 같은 브랜치·worktree에 한 번 띄운다(지적을 brief 끝에 붙인다). 재리뷰는 없고 verify만 돈다. 수정 worker가 실패하면(종료 코드, 멈춤, 커밋 없음, 리뷰한 커밋을 지움) 수정을 버리고 리뷰한 구현을 병합·검증한다. 티켓 실패로 세지 않는다.
4. reviewer·판단 모델 호출이 실패하거나 답의 형식이 틀려도 티켓은 그대로 간다(병합 관문은 verify). 그 사실은 리뷰 기록의 `note`에 남는다.

기록은 state의 `review`(`reviewer`, `merge_base`, `note`, `fix`, 지적마다 `action`·`why`·`fix_attempt`)와 시도 디렉터리의 `review/`(`diff.patch`, `prompt.md`, `review.txt`, `reviewer.log`, `findings.json`, `judge-prompt.md`, `judge.txt`, `judge.log`), `fix/`(수정 worker). 재리뷰가 없으니 지적은 수정을 시도한 것까지 모두 보고서의 "남은 리뷰 지적"에 들어간다.

reviewer 명령(모두 읽기 전용, worker와 같은 push·gh 차단 환경):

| reviewer | 명령 |
|---|---|
| claude | `claude -p --model <models.claude_review> --permission-mode bypassPermissions --tools Read,Grep,Glob` (stdin = 프롬프트) |
| codex | `codex exec [--model <models.codex>] -s read-only --skip-git-repo-check -C <wt> --output-last-message <review.txt> -` |
| agy | `agy -p <프롬프트> --sandbox --dangerously-skip-permissions --disable-slash-commands --settings '<deny 규칙>' --model <models.agy>` |

## 마무리

티켓 루프가 끝나면(`state.phase = finish`) `finish.py`가 외부 작업마다 `state.finish`를 저장하며 진행한다. 중단 뒤 다시 실행해도 같은 PR을 두 번 병합하거나 두 번 revert하지 않는다.

모든 `gh pr` 호출(`view`, `list`, `create`, `edit`, `merge`)은 `--repo <owner/repo>`를 붙인다. owner/repo는 그때마다 `git.remote`의 URL에서 푼다(위 "환경 검사"). gh의 기본 저장소(`gh repo set-default`, 첫 원격)를 따르지 않으므로, 원격이 여럿이어도 gs가 push한 그 저장소의 PR만 다룬다. 그래서 `git.remote`는 GitHub 저장소여야 한다.

1. integration 검증(`integration`). 실패하면 integration을 되돌린다.
2. 보고서: 새 판단 모델 호출(`models.judge`, 제한 `timeouts.judge_minutes`)이 증거 파일(`finish/report-input.md`, `finish/diff-stat.txt`, spec)을 읽고 Summary를 쓴다. 프롬프트는 마무리 상태·병합 여부 문장을 쓰지 말라고 한다(그 시점에는 아직 모른다). gs가 원본 증거를 붙여 `.goldstack/work/<f>/report.md`를 integration에 커밋한다: Summary, 마무리 상태 줄(아래), Evidence(티켓별 결과, 단계별 소요 `단계별 소요: worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`, 남은 리뷰 지적, verify 출력), Merge Danger(`결과:` 줄, PR, verify 결과, 병합·revert 커밋, 되돌리는 법). PR 본문 상한(60,000자)을 넘으면 로그를 줄이고, 그래도 길면 자른다. 판단 모델이 실패하면 그 사실을 Summary에 쓴다.
3. integration을 `<remote>`에 일반 push하고 `gh pr create --repo <owner/repo> --base <base>`(열린 PR이 있으면 `gh pr edit`). PR 본문은 보고서와 같다.
4. 보고서 커밋까지 포함한 PR head를 다시 검증(`integration-final`).
5. merged 티켓이 하나 이상이고 1과 4가 모두 통과하면 `gh pr merge --repo <owner/repo> --merge --match-head-commit <검증한 head>`. 아니면 `not_merged`(병합 안 함).
6. PR을 다시 읽어 실제 `MERGED`, base 이름, 병합 커밋, head가 검증한 것과 같은지 확인한다. 아직이면 `merge_pending`(병합 큐 대기, 종료 1, 다음 실행이 이어 간다). 사람이 닫았으면 `closed`(다음 실행이 새 PR을 연다).
7. 최신 `<remote>/<base>`를 임시 detached worktree에 받아 재검증(`main`). 실패하면 그 병합 커밋을 `git revert`(병합 커밋이면 `-m 1`)해 base에 일반 push한다(force push 없음). 실패 뒤 base가 움직였으면 최신 base를 다시 검증(`main-recheck`)한다. gs 밖에서 이미 되돌렸으면 다시 revert하지 않는다.
8. base를 integration에 합치고 보고서를 갱신해 push, PR 본문도 갱신한다. 같은 `finish/summary.md`(끝 줄바꿈을 뗀다)로 다시 쓰므로 재개해도 보고서가 어긋나지 않는다.
9. **base에 최종 보고서 push** — 이 마무리가 `verified`·`reverted`로 끝났을 때만. 원격 base의 최신 끝을 임시 detached worktree에 받아 `.goldstack/work/<f>/report.md`만 integration의 최종판으로 바꾼 커밋 `gs: <f> 최종 보고서(병합 후)`를 만들어 `<remote>`의 base에 일반 push한다(force 없음). base에 이미 같은 내용이면 커밋하지 않는다. 성공하면 `■ 최종 보고서를 <base>에 push했다(<sha8>)`를 출력하고 state `finish.base_report`에 sha를 적는다.
   - 거부되면(그 사이 base가 움직임) fetch 뒤 최신 base 위에서 다시 만들어 한 번 더 시도한다. 그래도 실패면 `■ 경고: 최종 보고서를 <base>에 push하지 못했다(두 번 시도). 실행 결과는 그대로다: …`만 쓴다. 실행 결과·종료 코드는 바뀌지 않는다.
   - 시도를 마치면(성공이든 실패든) `finish.base_report_tried`를 남기고, 다음 `gs go`는 다시 시도하지 않는다. 시도 전에 끊긴 실행(예: 8의 `gh pr edit` 실패)은 다음 재개가 처음으로 시도한다.
   - `not_merged`·`closed`·`merge_pending`이면 push하지 않는다. 보호된 base(직접 push 금지)는 다루지 않는다: push가 두 번 거부되어 경고로 끝나고, base에는 병합 시점의 report.md가 남는다.

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
| 그 밖(`preparing`) | `마무리: preparing · 병합 전` |

끝나지 않은 phase에 오류가 있으면 끝에 `· 오류(아래 Merge Danger)`가 붙는다. PR이 없으면 `<url>` 자리가 `PR 없음`이다. 보고서 커밋 때문에 병합 revert가 report.md에서 충돌하면, 되돌리는 법에 지금 보고서를 남기고 이어 가는 명령이 적힌다.

base가 이 feature의 병합을 revert했으면, 다음 실행이 integration을 준비할 때 그 revert를 되돌린 커밋을 만들어 합친다(그냥 합치면 feature 코드가 조용히 사라진다). 보고서에 그 사실을 적고, 다음 PR이 feature 코드를 다시 들인다. 상태 이름·로그 이름의 `main`(`main_failed`, `main-verify.log`)은 "base 브랜치"를 뜻하는 옛 이름이다.

git 오류나 herdr 오류(`HerdrError`)로 루프를 떠나도 `gs go: … 오류: …`를 stderr에 쓰고 `finished_at` 기록, 요약 출력, 알림까지 간다(종료 1).

마지막 출력은 요약과 PR 링크다:
```
■ 요약: 병합 7, 실패 1
■ 마무리: integration·main 검증 통과, PR 병합 완료
■ 보고서: .goldstack/work/<f>/report.md · 남은 리뷰 지적 2
■ PR: https://github.com/…/pull/4
```

## 진행 계산과 진행 바 mod

gs가 state를 쓸 때마다 `progress`를 계산해 같이 쓴다(`state.calculate_progress`, Python 시험). mod는 그리기만 한다.

**heartbeat** — state는 상태가 바뀔 때(`Run.save()`)만 쓰이므로, worker가 10분 넘게 단계를 바꾸지 않으면 mod의 10분 기준에 걸려 바가 사라졌다. 그래서 `go._wait_any`의 polling 루프가 상태 변화가 없어도 마지막 저장에서 `HEARTBEAT_SECONDS`(60초)가 지나면 `Run.save()`를 다시 불러 `updated_at`·`progress`(경과 시간 포함)와 파일 수정 시각을 새로 쓴다. mod 기준(10분)은 그대로다. 그러니 10분 넘게 안 바뀐 state는 `gs go`가 죽었다는 뜻이다.
```json
{"done": 3, "total": 8, "running": [{"id": "04", "phase": "review", "model": "codex"}],
 "elapsed_s": 1440, "eta_s": 2400, "line": "▓▓▓░░░░░ goldstack-v2 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음"}
```
- `done`: 이번 범위에서 merged·failed·skipped인 티켓 수. 막대는 8칸.
- `running`: 돌고 있는 티켓마다 마지막 단계와 그 모델(리뷰면 reviewer). feature 전체 마무리 중이면 `{"id": "", "phase": "finish", "model": "claude"}` 하나(`마무리 중(claude)`).
- `eta_s`: 이번 실행에서 끝난 티켓(이번 실행 전에 이미 병합된 티켓은 뺀다)의 평균 소요(재시도를 포함한 첫 단계부터 끝까지) × 남은 티켓 수 ÷ `max_workers`, 분 단위로 반올림. 표본이 없으면 `null`이고 line은 `남은 시간 계산 중`.

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

| model | 명령 | 차단 장치 |
|---|---|---|
| claude | `claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --disallowedTools "Bash(git push *)" "Bash(gh *)" < brief` | plugin hook + 도구 차단 |
| codex | `codex exec --json -s workspace-write [--model <models.codex>] -c sandbox_workspace_write.network_access=false --skip-git-repo-check -C <wt> --add-dir … "<안내>" < brief` | sandbox(네트워크 꺼짐, worktree 밖 쓰기 불가) |
| agy | `agy -p "$(cat brief)" --output-format stream-json --dangerously-skip-permissions --disable-slash-commands --settings '<deny 규칙>' --model <models.agy>` | deny 규칙 + `gs hook agy-pretooluse`(두 겹) |

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

비밀 읽기 검사는 직접 지정한 경로 외에 파일 이름 glob(`cat .goldstack/local.e*`, `cat .goldstack/*.env`, `head .goldstack/local.?nv`)과 알려진 재귀 검색(`grep -r`·`grep -R`·`rg`·`find`)의 시작점도 본다. 시작점 아래에 비밀 파일이 있으면 검색을 막는다(내용은 읽지 않고 경로를 검사한다). Grep·Glob 도구도 `path` 아래에 비밀이 있으면 막으며, 시작점을 생략하면 현재 디렉터리를 검사한다. 이 규칙은 `gh/hosts.yml` 등 다른 비밀 경로에도 같다. 검색 필터가 비밀 파일을 제외해도 시작점이 비밀을 품으면 막는다.

worker worktree는 주 레포의 `.goldstack/work/<f>/run/wt/` 아래에 있지만, 조상에 `.goldstack`이 있다는 이유로 막지는 않는다. 검색 시작점의 자손만 검사하므로 worktree 안에 비밀이 없으면 `rg foo`, `grep -r foo src`, Grep·Glob 검색은 통과하고, `.goldstack/work/<f>/spec.md`도 읽을 수 있다. 반대로 주 레포나 주 레포의 `.goldstack`에서 시작한 재귀 검색은 그 아래 `local.env`가 있으면 막는다.

막으면 이유와 "이 일은 `gs`가 한다"를 돌려준다. worker에서 hook 입력을 해석하지 못하면 막는다(fail closed). **hook은 안전띠이며 비밀을 격리하는 보안 경계가 아니다.** `python -c "open(...)"`처럼 코드 안에서 파일을 여는 일, 다른 인터프리터·스크립트 본문의 읽기, 셸에서 동적으로 만든 경로는 모두 해석하지 못한다. 심볼릭 링크 대상도 비밀 읽기 판정에서 보장하지 않으며, 디렉터리 재귀 검사에서는 링크를 따라가지 않는다. 검사 후 파일이 바뀌는 경우도 막지 못한다. 따라서 **값어치 낮은 비밀만 `local.env`에 둔다.** claude worker 명령의 도구 차단 옵션과 push·gh 차단 환경을 함께 두고(여러 겹), codex는 sandbox, agy는 deny 규칙과 `gs hook agy-pretooluse`를 쓴다. codex의 비밀 읽기를 이 hook으로 막는 것은 범위 밖이다.

skill은 `skills/<이름>/SKILL.md`다. `diagnosing-bugs`만 모델 호출이고 나머지는 `disable-model-invocation: true`(사용자 호출)라 description이 늘 문맥에 실리지 않는다. 옮겨 온 다섯 skill의 출처는 [skills/NOTICE-mattpocock.md](../skills/NOTICE-mattpocock.md).

## 실행 디렉터리

`.goldstack/work/<f>/run/`(gitignore):
```
state.json, lock
<NN>/<시도>/          brief.md, run.sh, worker.log, exit, verify.log, merge.log,
                      failure.log, failure-summary.md, judge.log, review/, fix/
wt/integration        integration worktree(gs만 쓴다)
wt/<NN>, wt/<NN>-retry-<k>   티켓 worktree(병합되면 정리, 실패면 보존)
finish/               summary.md, report-input.md, diff-stat.txt, report-judge.log,
                      integration-verify.log, integration-final-verify.log, main-verify.log, main-recheck-verify.log
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
| `GS_VERIFY_TIMEOUT` | verify 시간 제한(초). spec `verify_minutes`를 덮는다 |
| `GS_TELEGRAM_API` | 텔레그램 Bot API 주소(기본 `https://api.telegram.org`). 시험은 localhost 가짜 서버 |
