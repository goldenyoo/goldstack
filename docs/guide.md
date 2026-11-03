# goldstack 사용 가이드

상황별로 무엇을 치고 무엇이 보이는지 적는다. 설치는 [README](../README.md#설치), 엔진이 안에서 하는 일은 [internals.md](internals.md).
예시의 feature 이름은 `csv-export`, base 브랜치는 `main`, 원격은 `origin`이다. 실제 값은 `gs config git.base`, `gs config git.remote`가 알려 준다.

- [다른 레포에 처음 들이기](#다른-레포에-처음-들이기)
- [새 feature](#새-feature)
- [실행 중 보기](#실행-중-보기)
- [실패했을 때](#실패했을-때)
- [기존 레포 옮기기(`gs migrate`)](#기존-레포-옮기기gs-migrate)
- [skill 사용 장면](#skill-사용-장면)

## 다른 레포에 처음 들이기

`gs` CLI와 plugin은 머신에 한 번 설치한다(README "설치" 1–2). 그 뒤 레포마다 아래를 한 번 한다.

**1. `gs init`** — 레포 루트(또는 그 안 어디서든. 위로 `.git`을 찾는다)에서:
```console
$ gs init
만듦: .goldstack/config.toml
만듦: .goldstack/local.env.example
추가: .gitignore (.goldstack/local.env, .goldstack/work/*/run/)
.goldstack/config.toml을 확인하고, local.env.example을 local.env로 복사해 값을 채워라
```
없는 파일만 만들고, 있는 파일은 `그대로 둠: …`으로 알린다. 두 번 돌려도 같다. 커밋은 하지 않는다.
`config.toml`이 없으면 `gs check`·`gs go`·`gs config`는 `.goldstack/config.toml이 없다. gs init을 먼저 실행하라` 오류로 멈춘다.

**2. config 채우기** — `gs init`이 모든 키를 기본값으로 쓴다. 빠진 키는 오류, 모르는 키는 경고다.
```toml
[git]
remote = "origin"             # PR·병합·push 대상 원격
base = "main"                 # PR 대상 브랜치. gs init이 refs/remotes/origin/HEAD에서 찾는다(못 찾으면 main)

[models]
judge = "opus"                # 실패 요약·리뷰 분류·보고서용 claude -p --model
claude_review = "opus"        # reviewer가 claude일 때 --model
agy = "gemini-4-argon-high"   # agy worker·reviewer --model
codex = ""                    # 비우면 codex 기본 모델

[timeouts]
review_minutes = 30           # reviewer 호출 한 번
judge_minutes = 10            # 리뷰 분류·보고서 요약 호출 한 번
summary_seconds = 60          # 재시도 brief용 실패 요약 호출 한 번

[notify]
telegram = false              # true면 gs go가 끝날 때 한 통
```
값 하나를 확인할 때는 `gs config git.base`(→ `main`), `gs config notify.telegram`(→ `false`). `/go` skill도 이것으로 base를 읽는다.
feature마다 다른 값(`verify`, `max_workers`, `idle_minutes`, `verify_minutes`)은 config가 아니라 각 feature의 spec frontmatter에 둔다.

**3. `.gitignore`** — `gs init`이 두 줄을 덧붙인다. 이미 있으면 건드리지 않는다.
```
.goldstack/local.env          # 텔레그램 토큰 같은 비밀
.goldstack/work/*/run/        # 실행 흔적: state.json, 로그, 티켓 worktree
```
`run/` 아래에는 worker worktree(`run/wt/NN`)가 생긴다. 이 줄이 없으면 `git add -A`에 worktree가 섞인다.

**4. 텔레그램(선택)** — `cp .goldstack/local.env.example .goldstack/local.env` 뒤 값을 채운다(따옴표 없이 `KEY=value`).
```
TG_TOKEN=123456:ABC...      # BotFather에서 받은 봇 토큰
TG_CHAT_ID=987654321        # 알림 받을 채팅 ID
```
채팅 ID를 모르면 봇에게 아무 메시지나 보낸 뒤 `https://api.telegram.org/bot<TG_TOKEN>/getUpdates`의 `chat.id`를 본다. 그리고 config에서 `telegram = true`.
gs는 이 파일만 읽는다(환경 변수는 보지 않는다). worker는 이 파일을 읽을 수 없다(차단 hook).

**5. 확인하고 커밋** — `gs check <feature>`는 spec·티켓과 함께 환경도 본다. feature가 아직 없어도 `gs check x`를 돌리면("feature 디렉터리가 없다" 오류는 무시) `git`·`gh`·원격·텔레그램 문제가 먼저 보인다. 나오는 줄:
- ``필요한 CLI `codex`가 PATH에 없다``(오류): `git`, `gh`와 범위 안 티켓의 `model`·`reviewer`가 쓰는 CLI가 있어야 한다.
- `원격 <URL>은 GitHub가 아니다`(경고): PR·병합은 `gh`로만 하므로 GitHub 밖 원격에서는 마무리가 실패한다.
- `notify.telegram이 켜져 있지만 .goldstack/local.env에 TG_TOKEN이 없다`(경고).

```sh
git add .goldstack/config.toml .goldstack/local.env.example .gitignore
git commit -m "goldstack init"
```

## 새 feature

base 브랜치에서 Claude Code를 연다. 순서는 `/grill` → `/go`이고, 둘 다 사용자가 부르는 skill이다.

**`/grill csv-export`**
1. Claude가 레포·문서·도구 버전을 직접 읽고 돌려 본 것을 spec "환경 사실"에 날짜와 함께 적는다. 찾을 수 있는 것은 묻지 않는다.
2. 사람이 정할 결정을 라운드마다 한 메시지에 번호 붙여 묻는다. 질문마다 선택지와 그 선택지의 구체 예시(실제로 보일 명령·파일·출력), 추천과 이유가 붙고, 끝에 `yes = 추천 전부 수락. 바꿀 것만 번호로`.
3. 답하는 법: `yes`(추천 전부), `2. B`(2번만 B), `3. 왜 B가 아니야?`(되묻기: 답을 듣고 같은 라운드를 다시 확정한다). 짧은 답이면 Claude가 "이렇게 읽었다"를 답마다 한 줄로 보이니, 어긋나면 그때 고친다.
4. 답은 바로 `.goldstack/work/csv-export/spec.md`의 "결정" 표와 "grill 기록"에 적힌다. `verify` 같은 frontmatter 값이면 frontmatter도 고친다(gs는 표가 아니라 frontmatter를 읽는다).
5. 마지막 라운드는 티켓 분해다: 티켓 표(blocked_by, wave, 구현 모델, 리뷰 계열 — 서로 다른 계열이어야 한다)와 범위 밖 목록.
6. 확정되면 `tickets/NN-slug.md`, `.goldstack/out-of-scope/<slug>.md`를 쓰고 `gs check csv-export`가 오류·경고 없이 통과할 때까지 고친 뒤, 그 두 경로만 커밋한다. push는 하지 않는다.

```console
$ gs check csv-export
csv-export: 티켓 3장, 오류 0, 경고 0
순서: 01 02 03
지금 시작 가능: 01
```
파일 형식은 [skills/grill/templates/](../skills/grill/templates/). 중간에 세션이 끊겨도 `/grill csv-export`를 다시 부르면 spec의 기록에서 이어 간다.

**`/go csv-export`**
1. `gs check` — 오류가 있으면 보이고 "`/grill csv-export`로 고친다"며 끝낸다.
2. 현재 브랜치가 base인지 보고, grill 결과가 아직 커밋 안 됐으면 그 경로만 커밋하고, base가 원격보다 앞서기만 하면 `git push origin main`(force 아님). 뒤처졌거나 갈라졌으면 말하고 끝낸다. worker는 `origin/main` 위에서 일하므로 spec·티켓이 거기 있어야 한다.
3. `gs go csv-export`를 백그라운드로 돌리고 끝날 때까지 기다린다. 사람에게 묻지 않는다.
4. 결과: `report.md`의 세 줄 요약과 PR 링크(README "5분 따라 하기" 3).

일부 티켓만 돌릴 때(wave를 나눌 때)는 터미널에서 `gs check csv-export --only 01,02`로 범위를 보고 `gs go csv-export --only 01,02`. 범위 밖 의존은 끝났다고 본다.

## 실행 중 보기

**진행 바** — 같은 레포에서 연 Claude Code 세션이면 어느 세션이든 프롬프트 위에 한 줄이 뜬다(1초마다 갱신).
```
▓▓▓░░░░░ csv-export 1/3 · 02 리뷰 중(codex) · 03 worker 중(claude) · 12분 · 약 18분 남음
```
- `1/3`: 끝난 티켓(병합·실패·건너뜀)/전체. 막대 8칸이 그 비율이다.
- `02 리뷰 중(codex)`: 돌고 있는 티켓마다 단계(worker, 리뷰, 수정, 검증, 마무리)와 그 단계의 모델. feature 전체 마무리(보고서·PR·main 검증) 중이면 `마무리 중(claude)`.
- `12분`: 이번 실행의 경과. `약 18분 남음`: 이번 실행에서 끝난 티켓의 평균 소요 × 남은 티켓 ÷ `max_workers`. 끝난 티켓이 없으면 `남은 시간 계산 중`.
- 실행이 끝나거나 state.json이 10분 넘게 안 바뀌면 사라진다. 안 보이면 [README](../README.md#설치) 5.

**`gs status`** — 읽기 전용. 파일을 만들거나 잠그지 않으니 실행 중에 언제든 친다.
```console
$ gs status csv-export
csv-export: 실행 중(pid 48211) · 시작 14:02:10
티켓  상태     시도  경과    마지막 출력        이유
01    병합     1     9m12s   14:11:20 (8m03s 전)
02    실행 중  1     6m40s   14:19:21 (2s 전)
03    실행 중  2     3m05s   14:19:10 (13s 전)
▓▓▓░░░░░ csv-export 1/3 · 02 리뷰 중(codex) · 03 worker 중(claude) · 12분 · 약 18분 남음
```
03의 시도 2는 첫 시도가 실패해 재시도 중이라는 뜻이다(실패 이유는 끝난 시도에만 보인다). `gs status`만 치면 지금 돌고 있는 feature를 모두 보이고, 없으면 지난 실행 기록이 있는 feature 이름을 알려 준다. 첫 줄이 `중단됨(…)`이면 `gs go`가 끝을 남기지 않고 죽은 것이다. 다시 `gs go`를 돌리면 이어 간다.

**worker 화면과 로그** — herdr 안에서 돌렸으면 지금 workspace의 탭 `gs:csv-export`에 worker마다 pane이 열린다. 성공한 worker의 pane은 닫히고, 실패한 pane은 들여다볼 수 있게 남는다.
herdr 밖이면 화면 없이 돌고, 로그는 `.goldstack/work/csv-export/run/<티켓>/<시도>/worker.log`에 쌓인다. `gs go` 자신의 출력(`[02] 리뷰: codex`, `[02] 검증 통과 → integration 병합` 같은 줄)은 `/go`가 띄운 백그라운드 출력이다.

## 실패했을 때

**보고서 읽기** — `.goldstack/work/csv-export/report.md`. gs가 integration 브랜치에 커밋하고 PR 본문으로도 쓴다. 지금 작업 트리에 없으면 `git show origin/main:.goldstack/work/csv-export/report.md`(병합됐을 때) 또는 `git show gs/csv-export/integration:.goldstack/work/csv-export/report.md`.

| 절 | 볼 것 |
|---|---|
| Summary | 판단 모델이 쓴 짧은 요약: 변경의 의미, 남은 위험. 판단이지 증거가 아니다 |
| Evidence → 티켓별 결과 | 티켓마다 결과(`merged`, `failed`, `skipped`)와 이유. 단계별 소요(`worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`) |
| Evidence → 남은 리뷰 지적 | 다른 계열 reviewer의 지적 전부(재리뷰가 없어 수정을 시도한 것도 남는다). 리뷰 자체가 실패했으면 그 메모 |
| Evidence → verify 출력 | 티켓마다 가장 최근 verify 로그와 integration·main 검증 로그의 끝부분(원본 그대로) |
| Merge Danger | 마무리 결과, PR, integration·main verify 결과, 병합·revert 커밋, 되돌리는 법(명령) |

**자주 보는 이유**(티켓별 결과의 "이유", `gs status`의 마지막 열)

| 이유 | 뜻 | 할 일 |
|---|---|---|
| `검증 실패(로그 <경로>)` | 티켓을 integration에 합친 결과가 spec의 `verify`를 통과하지 못했다 | 그 `verify.log`를 읽는다 |
| `검증 시간 초과(<N>분, 로그 <경로>)` | verify가 `verify_minutes`를 넘겼다 | 시험이 멈추는지 보거나 spec의 `verify_minutes`를 늘린다 |
| `시간 초과: <N>분 동안 로그 출력·새 커밋 없음` | worker가 `idle_minutes` 동안 아무것도 안 했다 | `worker.log` 끝을 본다. 티켓이 너무 크면 나눈다 |
| `커밋 없음`, `worker 종료 코드 <N>` | worker가 커밋 없이 끝났거나 실패로 끝났다 | `worker.log`, worker의 마지막 메시지(막힌 이유) |
| `conflict`, `integration 병합 충돌` | 먼저 병합된 티켓과 같은 곳을 고쳤다 | `merge.log`. 같은 파일을 건드리는 티켓은 `blocked_by`로 줄 세운다 |
| `막힘: 02` | 02가 실패해 이 티켓은 건너뛰었다(`skipped`) | 02를 고치면 같이 다시 돈다 |
| `agy 차단 장치가 없다: …` | agy가 gs hook을 걸지 못해 worker로 띄우지 않았다 | 그 티켓의 `model`을 바꾸거나 agy를 고친다 |

실패한 티켓은 같은 모델로 한 번 자동 재시도한 뒤에도 실패한 것이다. 시도마다 증거가 `.goldstack/work/csv-export/run/<티켓>/<시도>/`에 남는다: `brief.md`, `worker.log`, `verify.log`, `merge.log`, `failure.log`, `failure-summary.md`(판단 모델의 요약), `review/`(diff·reviewer 답), `fix/`(수정 worker). 실패한 worktree(`run/wt/03`, `run/wt/03-retry-1`)도 지우지 않고 남긴다.

**마무리 결과**(보고서 Merge Danger, `■ 마무리:` 줄)

| 결과 | 뜻 |
|---|---|
| `integration·main 검증 통과, PR 병합 완료` | 끝. 실패한 티켓이 있어도 병합된 티켓은 main에 들어갔다 |
| `merged 티켓 없음 → 병합 안 함`, `integration 검증 실패 → 병합 안 함` | PR은 열렸거나 갱신됐지만 병합하지 않았다 |
| `병합 명령 뒤 PR이 아직 MERGED가 아니다. main 검증은 미실행` | 병합 큐·보호 규칙 대기. 병합된 뒤 `gs go`를 다시 돌리면 main 검증부터 이어 간다 |
| `PR …이 병합되지 않고 닫혔다 → 병합 안 함. 다음 gs go가 새 PR을 연다` | 사람이 PR을 닫았다 |
| `main 검증 실패 → revert <sha>를 main에 push함` | 병합 뒤 main 검증이 실패해 병합 커밋을 되돌렸다(force push 없음). 다음 `gs go`가 그 revert를 integration에서 다시 되돌려 feature 코드를 되살린다 |

**다시 실행** — 고칠 것이 spec·티켓이면 `/grill csv-export`로 고치고(커밋까지 한다), 그 뒤 `/go csv-export`. 코드만 다시 돌리면 되면 바로 `/go csv-export`.
- integration에 병합된 티켓은 건너뛴다(`[01] 이미 병합됨`). 실패·건너뜀 티켓은 실패 횟수를 0으로 되돌리고 다시 한다.
- `gs go`가 죽어 `running`으로 남은 티켓은 실패로 세지 않고 새로 시작한다. 살아 남은 worker가 있으면 먼저 끝낸다.
- spec·티켓을 고치고 커밋·push하지 않았으면 `gs go`가 시작 전에 거부한다(`.goldstack/work/csv-export가 origin/main와 다르다. … 먼저 커밋하고 push하라`). `/go`가 커밋·push를 대신 해 준다.
- 같은 feature에 `gs go`는 하나만 돈다. `이미 다른 gs go가 돌고 있다(pid …)`면 그 프로세스가 끝나길 기다린다.

## 기존 레포 옮기기(`gs migrate`)

goldstack v2 전에는 파일이 레포 루트의 `.work/`, `.out-of-scope/`, `.ideas/`에 있었다. v2의 `gs`는 `.goldstack/` 아래만 읽는다(옛 위치 호환 없음). 새 `gs`를 설치한 뒤(`uv tool install --reinstall .`) 옛 레포에서 한 번:
```console
$ gs migrate
옮김: .work/feat-a → .goldstack/work/feat-a
옮김: .work/feat-b → .goldstack/work/feat-b
옮김: .out-of-scope → .goldstack/out-of-scope
옮김: .ideas → .goldstack/ideas
바꿈: .gitignore (.work/*/run/ → .goldstack/work/*/run/)
만듦: .goldstack/config.toml
…
다음: git status로 확인하고 커밋하라(gs migrate는 커밋하지 않는다):
  git add -A -- .goldstack .gitignore && git commit -m "goldstack: .goldstack/로 옮김"
문서 안 상대 링크는 고치지 않았다.
```
- 추적 파일은 `git mv`로 옮겨 `git status`에 rename으로 보인다. untracked `run/`도 디렉터리째 같이 간다.
- config가 없으면 `gs init`도 한다(위 출력의 `만듦:` 줄). 만든 config를 확인한다.
- `.work/` 아래에 git worktree가 등록돼 있으면(지난 실행의 실패 worktree 등) 아무것도 옮기지 않고 목록과 `git worktree remove <경로>`, `git worktree prune` 명령을 보이며 실패한다. 미커밋 변경을 확인하고 지운 뒤 다시 돌린다.
- 옮길 자리(`.goldstack/work/<f>` 등)에 이미 파일이 있어도 아무것도 옮기지 않고 실패한다.
- 옮길 것이 없으면 `옮길 것 없음`. 두 번 돌려도 같다.
- 문서 안의 상대 링크(`../.work/…`)는 고치지 않는다. 필요하면 손으로 고친다.

옮긴 뒤 `gs check <feature>`로 feature마다 새 위치에서 통과하는지 본다.

## skill 사용 장면

`/grill`, `/go` 밖의 다섯 skill은 [mattpocock/skills](https://github.com/mattpocock/skills)를 옮긴 것이다. 각 `SKILL.md` 끝에 원본 링크가 있다.

### `/wait-what` — 설명을 못 따라갔을 때(사용자 호출)
grill 라운드 3번 질문이 "frontier 재계산 시 blocked_by 전이 폐포를…"처럼 읽혀 뜻을 모르겠다.
```
/wait-what
```
Claude가 놓친 맥락부터 짧게 깔고, 짧은 문장으로, 약어와 자기가 만든 용어를 풀고, 선택지마다 "고르면 실제로 보일 명령·파일·출력"을 붙여 다시 설명한다. 그 뒤 원래 라운드에 답하면 된다.

### `/handoff` — 다른 세션에 넘길 때(사용자 호출)
`/go`가 끝났는데 03이 실패했다. 이 세션은 문맥이 꽉 찼으니 새 세션에서 원인을 찾고 싶다.
```
/handoff 03 실패 원인을 찾아 고친다
```
`$TMPDIR`(없으면 `/tmp`)에 인계 문서를 쓰고 전체 경로를 보인다. 작업 트리에는 쓰지 않는다. 진행 중인 일, 이유, 다음 할 일, 확인 안 한 믿음 표시, "추천 skill"(예: `diagnosing-bugs`)이 들어가고, spec·티켓·report.md·PR은 옮겨 적지 않고 경로로만 가리킨다. 비밀과 `local.env` 값은 `<REDACTED>`.
새 세션에서는 "`<경로>`를 읽고 이어서 해"라고 시작한다.

### `diagnosing-bugs` — 무언가 깨졌을 때(모델 호출)
부를 필요가 없다. "`gs status`가 끝난 실행을 실행 중으로 보여. 진단해"처럼 깨졌다·실패한다·느리다고 말하면 Claude가 스스로 싣는다.
1. 먼저 이 버그에서 red가 되는 빠른 통과/실패 신호를 만든다(실패하는 시험, CLI 출력 diff, `git bisect run` 하네스 등). 사람이 클릭해야만 재현되면 `skills/diagnosing-bugs/scripts/hitl-loop.template.sh`로 사람을 단계별로 안내한다.
2. 재현·최소화 → 가설 → 계측 → 수정과 회귀 시험 → 정리.
관련 feature가 있으면 그 spec의 "결정"과 "환경 사실"을 먼저 읽는다. 출력 속 비밀은 `<REDACTED>`로 가린다.

### `/retro` — 실행을 돌아볼 때(사용자 호출)
v2 실행 중 worker가 같은 시험 실패로 두 번 재시도했다. 다음 실행이 나아지게 무엇을 바꿀지 보고 싶다.
```
/retro
```
인자가 없으면 지금 세션, 있으면 그 세션의 기록을 읽고 길 찾기, 자동 검사, 리뷰 기준, `CLAUDE.md`·`AGENTS.md`, 도구 비용, 효과 없는 지시, 정보 접근 범주로 고칠 후보를 심각한 순으로 보인다. 후보마다 세션에서 본 근거와 고칠 곳이 붙는다. **아무 파일도 바꾸지 않는다.** 사람이 고른 것만 고치거나, 원하면 `.goldstack/ideas/`에 적어 다음 `/grill`의 재료로 둔다.

### `/writing-for-agents` — agent가 읽는 문서를 쓸 때(사용자 호출)
새 skill을 만들거나 레포의 `CLAUDE.md`가 커져서 줄이고 싶다.
```
/writing-for-agents
skills/release/SKILL.md를 새로 쓰려 한다. description부터 같이 다듬자
```
문맥 포인터, 문맥 부담과 인지 부담, 정보 위계, 단계와 완료 기준, 리딩 워드, 쳐내기 기준을 문맥에 싣는다. skill이면 frontmatter와 호출 방식(사용자 호출·모델 호출) 고르기를 [SKILL-MECHANICS.md](../skills/writing-for-agents/SKILL-MECHANICS.md)에서 읽는다. `/retro`도 후보를 쓸 때 이 기준을 읽는다.
