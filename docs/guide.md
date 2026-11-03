# goldstack 사용 가이드

상황별로 무엇을 치고 무엇이 보이는지 적는다. 설치는 [README](../README.md#설치), 엔진이 안에서 하는 일은 [internals.md](internals.md).
예시의 feature 이름은 `csv-export`, base 브랜치는 `main`, 원격은 `origin`이다. 실제 값은 `gs config git.base`, `gs config git.remote`가 알려 준다.

- [다른 레포에 처음 들이기](#다른-레포에-처음-들이기)
- [새 feature](#새-feature)
- [티켓 선택 키와 agy 한도(`touches`, `second_reviewer`, `[agy] max_calls_per_run`)](#티켓-선택-키와-agy-한도)
- [실행 중 보기](#실행-중-보기)
- [실패했을 때](#실패했을-때)
- [여러 feature 이어 돌리기(`gs go a b`)](#여러-feature-이어-돌리기gs-go-a-b)
- [끝난 feature 치우기(`gs clean`)](#끝난-feature-치우기gs-clean)
- [아이디어 흐름(`/retro` → `/idea` → `gs backlog` → `/grill`)](#아이디어-흐름)
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

**2. config 채우기** — `gs init`이 모든 키를 기본값으로 쓴다. 빠진 키, 0 이하인 `timeouts.*`, 음수인 `agy.max_calls_per_run`, 빈 모델 이름(`models.codex`만 빈 값 허용)은 오류, 모르는 키는 경고다. `[agy]` 섹션만은 없어도 된다(v4 전에 만든 config는 상한 3으로 읽는다).
```toml
[git]
remote = "origin"             # PR·병합·push 대상 원격. GitHub URL이어야 한다(PR 저장소 owner/repo를 여기서 푼다)
base = "main"                 # PR 대상 브랜치. gs init이 refs/remotes/origin/HEAD에서 찾는다(못 찾으면 main)

[models]
judge = "opus"                # 실패 요약·리뷰 분류·보고서용 claude -p --model
claude_review = "opus"        # reviewer가 claude일 때 --model
agy = "gemini-4-argon-high"   # agy worker·reviewer --model
codex = ""                    # 비우면 codex 기본 모델

[agy]
max_calls_per_run = 3         # gs go 한 번에 gs가 띄우는 agy 호출 상한. 0이면 agy를 띄우지 않는다

[timeouts]
review_minutes = 30           # reviewer 호출 한 번
judge_minutes = 10            # 리뷰 분류·보고서 요약 호출 한 번
summary_seconds = 60          # 재시도 brief용 실패 요약 호출 한 번

[notify]
telegram = false              # true면 gs go가 끝날 때 한 통
```
값 하나를 확인할 때는 `gs config git.base`(→ `main`), `gs config notify.telegram`(→ `false`). `/go` skill도 이것으로 base를 읽는다.
feature마다 다른 값(`verify`, `max_workers`, `idle_minutes`, `verify_minutes`)은 config가 아니라 각 feature의 spec frontmatter에 둔다.

**3. `.gitignore`** — `gs init`이 아래 두 패턴 줄을 덧붙인다(주석 줄은 설명용이고 gs init은 쓰지 않는다). 이미 있는 줄은 건드리지 않는다.
```
# 텔레그램 토큰 같은 비밀
.goldstack/local.env
# 실행 흔적: state.json, 로그, 티켓 worktree
.goldstack/work/*/run/
```
`.gitignore`의 `#`은 줄 맨 앞에서만 주석이다. 패턴 뒤에 붙이면 패턴의 일부가 되어 그 줄이 아무것도 무시하지 않는다.
`run/` 아래에는 worker worktree(`run/wt/NN`)가 생긴다. 이 줄이 없으면 `git add -A`에 worktree가 섞인다.

**4. 텔레그램(선택)** — `cp .goldstack/local.env.example .goldstack/local.env` 뒤 값을 채운다(따옴표 없이 `KEY=value`).
```
# BotFather에서 받은 봇 토큰
TG_TOKEN=123456:ABC...
# 알림 받을 채팅 ID
TG_CHAT_ID=987654321
```
주석은 줄 맨 앞 `#`만 인정한다. 값 뒤에 붙인 `# ...`는 값의 일부가 된다.
채팅 ID를 모르면 봇에게 아무 메시지나 보낸 뒤 `https://api.telegram.org/bot<TG_TOKEN>/getUpdates`의 `chat.id`를 본다. 그리고 config에서 `telegram = true`.
gs는 이 파일만 읽는다(환경 변수는 보지 않는다). worker는 이 파일을 읽을 수 없다(차단 hook).

**5. 확인하고 커밋** — `gs check <feature>`는 spec·티켓과 함께 환경도 본다. feature가 아직 없어도 `gs check x`를 돌리면("feature 디렉터리가 없다" 오류는 무시) `git`·`gh`·원격·텔레그램 문제가 먼저 보인다. 나오는 줄:
- ``필요한 CLI `codex`가 PATH에 없다``(오류): `git`, `gh`, `claude`(판단 모델: 실패 요약·리뷰 분류·보고서)와 범위 안 티켓의 `model`·`reviewer`가 쓰는 CLI가 있어야 한다.
- ``원격 `origin`의 URL `…`은 GitHub 저장소 형식이 아니다``(오류): gs는 `git.remote`의 URL에서 owner/repo를 풀어 모든 `gh pr` 명령에 `--repo`로 넘긴다. GitHub 밖 원격에서는 `gs go`도 시작하지 않는다.
- `notify.telegram이 켜져 있지만 .goldstack/local.env에 TG_TOKEN이 없다`(경고).

```sh
git add .goldstack/config.toml .goldstack/local.env.example .gitignore
git commit -m "goldstack init"
```

## 새 feature

base 브랜치에서 Claude Code를 연다. 순서는 `/grill` → `/go`이고, 둘 다 사용자가 부르는 skill이다.

**`/grill csv-export`**
1. Claude가 레포·문서·도구 버전과 `gs backlog`(열린 아이디어, 범위 밖의 다시 볼 조건)를 직접 읽고 돌려 본 것을 spec "환경 사실"에 날짜와 함께 적는다. 찾을 수 있는 것은 묻지 않는다.
2. 사람이 정할 결정을 라운드마다 한 메시지에 번호 붙여 묻는다. 질문마다 선택지와 그 선택지의 구체 예시(실제로 보일 명령·파일·출력), 추천과 이유가 붙고, 끝에 `yes = 추천 전부 수락. 바꿀 것만 번호로`. 열린 아이디어가 있으면 라운드 1의 첫 질문은 "이번 feature에 넣을 후보"다(아래 [아이디어 흐름](#아이디어-흐름)).
3. 답하는 법: `yes`(추천 전부), `2. B`(2번만 B), `3. 왜 B가 아니야?`(되묻기: 답을 듣고 같은 라운드를 다시 확정한다). 짧은 답이면 Claude가 "이렇게 읽었다"를 답마다 한 줄로 보이니, 어긋나면 그때 고친다.
4. 답은 바로 `.goldstack/work/csv-export/spec.md`의 "결정" 표와 "grill 기록"에 적힌다. `verify` 같은 frontmatter 값이면 frontmatter도 고친다(gs는 표가 아니라 frontmatter를 읽는다).
5. 마지막 라운드는 티켓 분해다: 티켓 표(blocked_by, wave, 구현 모델, 리뷰 계열 — 서로 다른 계열이어야 한다, 건드릴 파일 `touches`)와 범위 밖 목록. 확정되면 `touches`가 티켓 frontmatter에 들어간다(아래 [티켓 선택 키](#티켓-선택-키와-agy-한도)).
6. 확정되면 `tickets/NN-slug.md`, `.goldstack/out-of-scope/<slug>.md`를 쓰고 `gs check csv-export`가 오류·경고 없이 통과할 때까지 고친다. 라운드 1에서 고른 아이디어 파일은 `status: "taken"`, `feature: "csv-export"`로 바꾼다. 그 뒤 `.goldstack/work/csv-export`, `.goldstack/out-of-scope`, `.goldstack/ideas`만 커밋한다(없는 디렉터리는 뺀다). push는 하지 않는다.

```console
$ gs check csv-export
csv-export: 티켓 3장, 오류 0, 경고 0
순서: 01 02 03
지금 시작 가능: 01
```
파일 형식은 [skills/grill/templates/](../skills/grill/templates/). 중간에 세션이 끊겨도 `/grill csv-export`를 다시 부르면 spec의 기록에서 이어 간다.

**`/go csv-export`**
1. `gs check` — 오류가 있으면 보이고 "`/grill csv-export`로 고친다"며 끝낸다.
2. 현재 브랜치가 base인지 보고, grill 결과(`.goldstack/work/csv-export`, `.goldstack/out-of-scope`, `.goldstack/ideas`)가 아직 커밋 안 됐으면 그 경로만 커밋하고, base가 원격보다 앞서기만 하면 `git push origin main`(force 아님). 뒤처졌거나 갈라졌으면 말하고 끝낸다. worker는 `origin/main` 위에서 일하므로 spec·티켓이 거기 있어야 한다.
3. `gs go csv-export`를 백그라운드로 돌리고 끝날 때까지 기다린다. 사람에게 묻지 않는다.
4. 결과: `report.md`의 세 줄 요약과 PR 링크(README "5분 따라 하기" 3). 끝나면 `/retro csv-export`로 실행을 돌아볼 수 있다([아이디어 흐름](#아이디어-흐름)).

일부 티켓만 돌릴 때(wave를 나눌 때)는 터미널에서 `gs check csv-export --only 01,02`로 범위를 보고 `gs go csv-export --only 01,02`. 범위 밖 의존은 끝났다고 본다.

## 티켓 선택 키와 agy 한도

티켓 frontmatter의 필수 키는 `id`, `title`, `blocked_by`, `model`, `reviewer`다([템플릿](../skills/grill/templates/ticket.md)). v4부터 두 선택 키가 있다. 둘 다 없어도 옛 티켓은 그대로 통과한다.

### `touches` — 같은 파일을 건드리는 티켓 찾기
grill의 티켓 분해 라운드 표에 `touches` 열이 보이고, 확정되면 grill이 티켓마다 적는다. 사람이 직접 쓸 일은 대개 없고, 표에서 틀린 경로만 고쳐 답한다.
```yaml
---
id: "02"
title: "CSV 헤더 줄"
blocked_by: []
touches: ["src/tally/cli.py", "tests/test_csv*.py"]
model: codex
reviewer: claude
---
```
- 값: 레포 루트 기준 경로 목록. glob을 쓸 수 있다(`*`·`?`·`[…]`는 경로 한 부분, `**`는 0개 이상의 부분). 절대 경로와 `..`는 오류다.
- 겹침: 두 티켓에 같은 경로가 있거나 glob이 서로 맞는 경로가 있으면(`src/**`와 `src/tally/cli.py`) 겹친다.
- 순서: `blocked_by`를 따라가 한쪽이 다른 쪽에 닿으면(직접이든 간접이든) 순서가 있다.

겹치는데 순서가 없으면 `gs check`가 티켓 쌍마다 경로 하나를 들어 경고한다:
```console
$ gs check csv-export
경고: 01·02가 src/tally/cli.py를 함께 건드리는데 순서가 없다
csv-export: 티켓 3장, 오류 0, 경고 1
순서: 01 02 03
지금 시작 가능: 01 02
```
뜻: 01과 02가 동시에 돌 수 있고, 나중에 병합되는 쪽이 같은 줄을 고쳤으면 `conflict`로 실패해 재시도를 쓴다. 경고라서 `gs go`를 막지는 않는다. 고치는 법은 둘 중 하나다: 한쪽에 순서를 준다(02에 `blocked_by: ["01"]`), 또는 실제로는 다른 곳이면 `touches`를 좁힌다. grill은 경고가 없어질 때까지 고친 뒤 커밋한다. `touches`가 없거나 `[]`인 티켓은 이 검사에서 빠진다.

### `second_reviewer` — 위험한 티켓에 Gemini 한 번 더
`reviewer`는 그대로 두고, 필요한 티켓에만 한 줄 더한다(템플릿에는 없는 키라 grill이 그 티켓에만 적는다). 값은 `claude|codex|agy` 중 `model`·`reviewer`와 모두 다른 계열이라, 남는 계열 하나다. claude 구현·codex 리뷰 티켓이면 `agy`(Gemini)가 된다. 같은 계열이면 `gs check` 오류:
```
오류: .goldstack/work/csv-export/tickets/04-cleanup.md: 리뷰는 다른 계열이어야 한다: reviewer과 second_reviewer가 둘 다 `codex`
```
언제 붙이나: 틀리면 비싼 티켓. 파일·브랜치를 지우는 코드, 병합·revert, 차단 hook, 비밀 처리, 데이터 마이그레이션처럼 리뷰 하나가 놓친 것이 바로 사고가 되는 곳이다. 문서, 출력 문구, 시험으로 다 확인되는 작은 변경에는 붙이지 않는다(agy 한도를 쓰고 지적만 늘어난다).
```yaml
---
id: "04"
title: "옛 출력 파일 지우기"
blocked_by: ["02"]
touches: ["src/tally/cleanup.py", "tests/test_cleanup.py"]
model: claude
reviewer: codex
second_reviewer: agy
---
```
두 리뷰는 동시에 돌고, 지적을 합쳐 수정 worker를 한 번만 띄운다(재리뷰 없음). 한쪽이 실패·시간 초과여도 다른 쪽 결과로 간다. `gs go` 출력:
```
[04] 리뷰: codex+agy
[04] 리뷰 끝(codex): 지적 2개(fix 1, report 1)
[04] 리뷰 끝(agy): 지적 1개(fix 1, report 0)
```
보고서 "남은 리뷰 지적"에는 리뷰마다 계열이 붙는다: `- 04 리뷰(codex) [medium] src/tally/cleanup.py:12: …`, `- 04 리뷰(agy) [high] …`. 원본은 `run/04/<시도>/review/`(첫 리뷰)와 `run/04/<시도>/review-agy/`(두 번째 리뷰).

### `[agy] max_calls_per_run` — Gemini 호출 상한
```toml
[agy]
max_calls_per_run = 3
```
`gs go` 한 번(feature 하나)에서 gs가 띄우는 agy 호출 수의 상한이다. 1회는 agy worker 한 번(재시도·수정 worker도 각각 1회) 또는 agy 리뷰 한 번이다. 실행마다 0부터 센다(`gs go a b`면 feature마다 따로). 섹션이 없으면 3, `0`이면 agy를 띄우지 않는다. `/retro`의 agy 요약과 `gs check`의 agy 차단 장치 확인(`agy -p /hooks`, 모델 호출 없음)은 세지 않는다.
- **`gs check`**: 범위 안 티켓의 `model`·`reviewer`·`second_reviewer` 중 agy인 것을 센다(티켓마다 첫 호출만. 재시도·수정은 미리 세지 않는다). 상한을 넘으면 경고:
  ```
  경고: 범위 안 agy 배정 4회가 상한 agy.max_calls_per_run=3회를 넘는다
  ```
- **실행 중 상한에 닿으면** 멈추지 않고 이어 간다. agy 리뷰는 띄우지 않고 `건너뜀(한도)`으로 적는다(`[04] 리뷰 끝(agy): 지적 0개(fix 0, report 0) — 건너뜀(한도): 이번 실행의 agy 호출이 상한 3/3에 닿았다`. 리뷰가 하나뿐이면 `(agy)` 없이 `[04] 리뷰 끝: …`). 다른 리뷰가 있으면 그것으로, 없으면 verify만으로 병합한다. agy 구현 티켓은 worker를 띄우지 않고 재시도 없이 실패한다(이유 `agy 한도: …`, 아래 [자주 보는 이유](#실패했을-때)). agy 수정 worker는 띄우지 않고 리뷰한 구현을 병합·검증한다.
- **보고서**: Evidence 끝에 `agy 사용: 2/3`(이번 실행 호출 수/상한).

언제 바꾸나: `second_reviewer: agy` 티켓이 상한보다 많은 feature면 그 수만큼 올린다(경고가 사라진다). Gemini 사용량이 빠듯한 날은 낮추거나 `0`으로 둔다. `0`인데 agy 배정이 있으면 `gs check`가 같은 경고를 낸다.

## 실행 중 보기

**진행 바** — 같은 레포에서 연 Claude Code 세션이면 어느 세션이든(레포 하위 디렉터리에서 연 세션도) 프롬프트 위에 한 줄이 뜬다(1초마다 갱신).
```
▓▓▓░░░░░ csv-export 1/3 · 02 리뷰 중(codex) · 03 worker 중(claude) · 12분 · 약 18분 남음
```
- `1/3`: 끝난 티켓(병합·실패·건너뜀)/전체. 막대 8칸이 그 비율이다.
- `02 리뷰 중(codex)`: 돌고 있는 티켓마다 단계(worker, 리뷰, 수정, 검증, 마무리)와 그 단계의 모델. feature 전체 마무리(보고서·PR·main 검증) 중이면 `마무리 중(claude)`.
- `12분`: 이번 실행의 경과. `약 18분 남음`: 이번 실행에서 끝난 티켓의 평균 소요 × 남은 티켓 ÷ `max_workers`.
- 이번 실행에서 끝난 티켓이 아직 없으면 이 레포의 **다른 feature** 실행 기록(`.goldstack/work/*/run/state.json`)에서 병합된 티켓의 소요 중앙값으로 처음부터 예측하고, 그 사실을 꼬리표로 단다:
  ```
  ░░░░░░░░ csv-import 0/4 · 01 worker 중(codex) · 02 worker 중(claude) · 3분 · 약 26분 남음(이전 실행 기준)
  ```
  `(이전 실행 기준)` = "이번 feature의 티켓은 아직 하나도 안 끝났고, 지난 feature들의 티켓 크기로 어림했다"는 뜻이다. 티켓 크기가 feature마다 다르니 거친 값으로 본다. 이번 실행에서 티켓 하나가 끝나면(병합·실패) 꼬리표가 빠지고 이번 실행 평균으로 바뀐다. `run/`은 gitignore라 기록은 실행한 머신에만 있다. 다른 feature 기록도 없으면(이 레포의 첫 feature, 새 머신) `남은 시간 계산 중`.
- `gs go`는 worker를 기다리는 동안 상태가 그대로여도 60초마다 state.json을 다시 써서(heartbeat) worker가 오래 돌아도 바가 남는다. 실행이 끝나거나 state.json이 10분 넘게 안 바뀌면 사라진다. 리뷰·검증·병합·마무리는 `gs go`가 직접 기다리느라 그동안 heartbeat가 멈추므로, 10분 넘는 리뷰(기본 제한 30분)나 검증(기본 20분) 중에는 정상 실행이어도 바가 사라졌다가 그 단계가 끝나면 돌아온다. 죽었는지는 `gs status <feature>`의 `실행 중(pid …)`/`중단됨`으로 본다. 안 보이면 [README](../README.md#설치) 5.

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

**보고서 읽기** — `.goldstack/work/csv-export/report.md`. gs가 integration 브랜치에 커밋하고 PR 본문으로도 쓴다. 마무리가 `verified`(main 검증 통과)나 `reverted`(main 검증 실패로 revert)로 끝나면 main 검증 결과까지 담긴 최종판을 커밋 `gs: csv-export 최종 보고서(병합 후)` 하나로 main에도 push한다. 그러니 `git pull` 뒤 작업 트리의 report.md가 최종판이다. 그 push가 두 번 거부되면 `■ 경고: 최종 보고서를 main에 push하지 못했다…`만 남고(결과·종료 코드는 그대로), main에는 병합 직전 판이 남는다. 그때는 `git show gs/csv-export/integration:.goldstack/work/csv-export/report.md`가 최종판이다.

| 절 | 볼 것 |
|---|---|
| Summary | 판단 모델이 쓴 짧은 요약: 변경의 의미, 남은 위험. 판단이지 증거가 아니다. 병합 여부는 쓰지 않는다 |
| 마무리 상태 줄(Summary 바로 아래) | gs가 state에서 쓴 한 줄. 예 `마무리: verified · PR https://github.com/you/tally/pull/7 병합 · main 검증 통과`, `마무리: reverted · main 검증 실패 → revert 1a2b3c4d`, `마무리: not_merged · integration 검증 실패` |
| Evidence → 티켓별 결과 | 티켓마다 결과(`merged`, `failed`, `skipped`)와 이유. 단계별 소요(`worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`, 0분인 단계는 빼고 모두 1분 미만이면 `모두 1분 미만`). 미커밋 변경 때문에 남긴 worktree(`--only` 범위 밖 티켓 것도) |
| Evidence → 남은 리뷰 지적 | 다른 계열 reviewer의 지적 전부(재리뷰가 없어 수정을 시도한 것도 남는다). `second_reviewer`가 있으면 리뷰마다 `04 리뷰(codex)`, `04 리뷰(agy)`로 나뉜다. 리뷰 자체가 실패했거나 `건너뜀(한도)`이면 그 메모 |
| Evidence 끝 `agy 사용: N/상한` | 이번 실행에서 gs가 띄운 agy 호출 수 |
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
| `agy 한도: 이번 실행의 agy 호출이 상한 3/3에 닿아 worker를 띄우지 않았다(config agy.max_calls_per_run)` | 이번 실행의 agy 호출이 [상한](#agy-max_calls_per_run--gemini-호출-상한)에 닿았다. 재시도하지 않는다 | 상한을 올리거나 그 티켓의 `model`을 바꿔 다시 `gs go` |

실패한 티켓은 같은 모델로 한 번 자동 재시도한 뒤에도 실패한 것이다. 시도마다 증거가 `.goldstack/work/csv-export/run/<티켓>/<시도>/`에 남는다: `brief.md`, `worker.log`, `verify.log`, `merge.log`, `failure.log`, `failure-summary.md`(판단 모델의 요약), `review/`(diff·reviewer 답), `fix/`(수정 worker). 실패한 worktree(`run/wt/03`, `run/wt/03-retry-1`)도 지우지 않고 남긴다. 다 봤으면 [`gs clean`](#끝난-feature-치우기gs-clean)으로 지운다.

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

## 여러 feature 이어 돌리기(`gs go a b`)

grill이 끝난 feature가 여럿이면(밤새 돌려 둘 때) 한 번에 줄 세운다. Claude Code에서 `/go csv-export csv-import`, 터미널에서 `gs go csv-export csv-import`. `/go`는 feature마다 `gs check`와 커밋·push를 한 뒤 `gs go csv-export csv-import`를 한 번 띄우고, 끝나면 실행된 feature마다 세 줄 요약과 PR을 보인다.
1. 시작 전에 모든 feature를 `gs check`한다. 하나라도 오류면 아무것도 시작하지 않는다(종료 1). 뒤 feature의 오류 때문에 앞 것만 돌고 끝나는 일이 없다.
2. 앞 feature를 평소처럼 main 검증까지 끝낸다.
3. 종료 코드가 0이고 마무리가 `verified`면 다음으로 간다:
   ```
   ■ 요약: 병합 3
   ■ 마무리: integration·main 검증 통과, PR 병합 완료
   ■ 보고서: .goldstack/work/csv-export/report.md · 남은 리뷰 지적 1
   ■ PR: https://github.com/you/tally/pull/7
   ■ csv-export: verified → csv-import 시작
   ```
4. 아니면 거기서 멈추고 남은 feature를 보인다. 종료 코드는 멈춘 feature의 것이다:
   ```
   ■ csv-export: reverted → 여기서 멈춤(남은: csv-import)
   ```

**멈추는 조건** — 앞 feature의 종료 코드가 0이 아니거나 마무리가 `verified`가 아니면 멈춘다. 그러니 다음도 멈춘다:
- 티켓 하나라도 실패·건너뜀(병합된 티켓은 main에 들어가 마무리가 `verified`여도): `■ csv-export: verified → 여기서 멈춤(남은: csv-import)`.
- `not_merged`(integration 검증 실패, merged 티켓 없음), `merge_pending`(병합 큐 대기), `closed`, `reverted`(main 검증 실패로 revert).
- `gs go`가 시작 전에 거부(미커밋 spec, 다른 `gs go`가 잠금): 종료 코드가 1이라 state에 지난 실행의 `verified`가 남아 있어도 멈춘다. state.json을 못 읽으면 `■ csv-export: unknown → 여기서 멈춤(남은: csv-import)`.

멈췄으면 앞 feature를 [실패했을 때](#실패했을-때)대로 고친 뒤 같은 줄을 다시 친다. 모두 병합돼 정리된 앞 feature는 `■ 이미 끝남: csv-export (verified)`로 바로 넘어간다. `--only`는 여러 feature와 함께 못 쓴다(`gs: error: 여러 feature와 --only는 함께 쓸 수 없다`).

**gs 재설치 한계** — gs는 `uv tool install`로 복사 설치되어 있고 `gs go a b`는 한 프로세스로 끝까지 돈다. 그래서 앞 feature가 gs 자체(goldstack 레포의 `src/gs/`, worker 차단 hook이 부르는 `gs hook`)를 고쳐 main에 병합해도 **다음 feature는 시작할 때의 옛 gs로 돈다.** 다음 feature가 앞 feature의 gs 변경에 기대면 이어 돌리지 말고 나눈다:
```sh
gs go goldstack-v4
git pull && uv tool install --reinstall .   # 새 gs로 바꾼다
gs go goldstack-v5
```
goldstack 밖의 레포(gs를 고치지 않는 feature)에는 해당하지 않는다.

## 끝난 feature 치우기(`gs clean`)

실행이 끝나도 흔적이 남는다: 실패한 티켓의 worktree(`run/wt/03`, `run/wt/03-retry-1`)와 브랜치(`gs/csv-export/03`, `gs/csv-export/03-retry-1`), 미커밋 변경 때문에 남긴 worktree, `reverted`로 끝난 feature의 integration worktree와 로컬·원격 `gs/csv-export/integration`. 다 봤으면 지운다.
```console
$ gs clean csv-export
지움: worktree /home/you/tally/.goldstack/work/csv-export/run/wt/03 (미커밋 변경도 지움)
지움: worktree /home/you/tally/.goldstack/work/csv-export/run/wt/integration (미커밋 변경도 지움)
지움: worktree 2, 로컬 브랜치 3, 원격 브랜치 1 · 실행 기록은 남김
```

| 지우는 것 | 남기는 것 |
|---|---|
| `run/wt/` 아래 전부(티켓·재시도·integration worktree, **미커밋 변경 포함**, git 등록이 풀린 잔여 디렉터리도) | `run/state.json`, `run/<NN>/<시도>/`(brief, `worker.log`, `review/`, `verify.log` …), `run/finish/` |
| 로컬 브랜치 `gs/csv-export/*` | spec·티켓·`report.md`(커밋된 것), main의 병합 커밋 |
| `git.remote`의 원격 브랜치 `gs/csv-export/*` | 열린·닫힌 PR(GitHub에 그대로) |

- 실행 중이면 거부한다(`--force`로도): `gs clean: 이미 다른 gs go가 돌고 있다(pid 48211)`. 검사와 삭제를 `gs go`와 같은 잠금 안에서 한다.
- 마무리가 `verified`·`reverted`가 아니면 거부한다: `gs clean: 마무리가 verified·reverted가 아니다(not_merged). --force가 필요하다`(실행 기록이 없으면 `(없음)`). 버릴 feature면 남긴 worktree의 미커밋 변경을 확인하고 `gs clean csv-export --force`. 그 뒤 다시 `gs go`하면 main에 들어가지 않은 integration이 사라졌으므로 티켓이 처음부터 다시 돈다.
- 하나를 지우다 실패하면 `경고: 정리 실패: …`를 쓰고 나머지를 계속한 뒤 종료 1.
- 정리한 뒤 같은 feature로 `gs go`를 쳐도 다시 만들지 않는다: 모든 티켓이 병합된 끝난 실행이면 `■ 이미 끝남: csv-export (verified)`. 실패 티켓이 남았거나 새 티켓을 더했으면 평소처럼 이어 가고, 병합된 티켓은 건너뛴다.

**자동 정리** — 마무리가 `verified`로 끝나면 `gs go`가 main에 최종 보고서 push를 시도한 뒤 그 feature의 integration worktree(`run/wt/integration`)와 로컬·원격 `gs/csv-export/integration`을 스스로 지운다. 출력은 `지움: worktree …/run/wt/integration (미커밋 변경도 지움)` 한 줄이고 실패해도 `경고: 정리 실패: …`만 남는다(결과·종료 코드는 그대로). 원격 삭제만 실패했으면 다음 `gs go csv-export`가 `■ 이미 끝남` 뒤 다시 시도한다. 실패한 티켓의 worktree·브랜치는 자동으로 지우지 않는다(`gs clean`). `reverted`·`not_merged`·`merge_pending`으로 끝난 feature는 원인을 볼 수 있게 integration을 남긴다.

## 아이디어 흐름

실행에서 나온 생각은 아이디어 함 `.goldstack/ideas/`에 파일로 쌓였다가 다음 feature의 grill에서 후보가 된다. `/go csv-export`가 끝나면 `/retro csv-export`가 그 실행 기록(report.md, state.json, worker 로그, 리뷰, 다른 feature 보고서와의 반복)을 읽고 고칠 후보를 제안하고, 사람이 고른 것을 아이디어 파일로 쓴다. 실행 중 대화에서 떠오른 생각은 `/idea <한 줄>`로 바로 넣는다. 다음 feature를 시작하기 전에 `gs backlog`로 열린 아이디어와 범위 밖의 다시 볼 조건을 훑고, `/grill <다음 feature>`를 부르면 라운드 1의 첫 질문으로 그 열린 아이디어 가운데 이번에 넣을 것을 묻는다. 고른 아이디어는 `status: taken`이 되어 다음 `gs backlog`에서 빠진다. 아이디어 파일은 커밋하지 않고 두면 `/grill`·`/go`의 커밋이 함께 담는다.

**`/retro csv-export`** — feature 실행을 돌아볼 때. 인자가 `.goldstack/work/` 아래 feature 이름이면 실행 기록을, 아니면 세션을 읽는다(아래 [`/retro`](#retro--실행을-돌아볼-때사용자-호출)). 후보를 번호 붙여 보이고, 다른 feature 보고서에도 같은 실패가 있으면 `[반복]`을 단다. 파일은 사람이 "1, 3"처럼 고른 뒤에만 쓴다.

**`/idea <한 줄>`** — 생각 하나를 바로 적을 때.
```
/idea gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다
```
먼저 열린 아이디어에서 비슷한 것(같은 문제, 같은 곳)을 찾는다. 있으면 그 slug와 첫 줄을 보이고 "덧붙일까, 새 파일로 쓸까"를 묻는다. 덧붙이면 그 파일 끝에 `- 2026-11-03 <근거> (출처: …)` 줄이 붙는다. 없으면 slug·severity·source를 문맥에서 정해 새 파일을 쓰고 한 줄로 알린다:
```
.goldstack/ideas/status-review-count.md · 2026-11-03 · low · goldstack-v3 실행 중 대화 · open
```
severity는 `high`(결과·기록이 틀리거나 안전 구멍), `medium`(반복되는 손일·불편), `low`(다듬기). 커밋은 하지 않는다.

**`gs backlog [--all]`** — 다음 feature를 고르기 전에. 읽기 전용이고 늘 종료 0이다.
```console
$ gs backlog
아이디어 (열림 2)
medium  2026-11-03  codex-worker-hook  codex worker를 sandbox 대신 hook으로 막기   (goldstack-v2 grill 라운드 2 질문)
low     2026-11-03  status-review-count  gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다   (goldstack-v3 실행 중 대화)
범위 밖 (다시 볼 조건)
gitlab-support  GitHub 밖 레포에 goldstack을 쓰려 할 때.
same-file-serialization-check  v0 06처럼 blocked_by 누락 충돌로 티켓이 또 버려지면.
```
열린 아이디어를 severity(high→low) → 날짜(오래된 것 먼저) → slug 순으로 보이고, 아래에 `.goldstack/out-of-scope/*.md`마다 `**다시 볼 조건**:` 문장을 보인다. 조건이 맞았으면 그 개념을 다음 grill에서 다시 꺼낸다. `--all`은 taken·dropped도 보이고 status 열을 더한다. 형식이 틀린 아이디어 파일은 `경고: <파일>: <이유>`로 알리고 목록에서 뺀다(`gs check`는 아이디어를 보지 않는다). 파일 형식은 `.goldstack/ideas/README.md`와 [internals.md](internals.md#아이디어-함).

**`/grill`의 후보 질문** — 열린 아이디어가 있을 때 라운드 1의 첫 질문:
```
라운드 1
1. 이번 feature에 넣을 후보(여러 개 가능, 없으면 "없음"):
   1) codex-worker-hook — codex worker를 sandbox 대신 hook으로 막기 (medium)
   2) status-review-count — gs status가 끝난 티켓의 리뷰 지적 수 (low)
   추천 2: 이번 feature와 같은 파일(status.py)을 고친다
2. …
yes = 추천 전부 수락. 바꿀 것만 번호로
```
`1. 1,2`처럼 고르면 그 아이디어들이 이번 feature의 결정 표로 들어가고, grill이 끝날 때 그 파일이 `status: "taken"`, `feature: "<이번 feature>"`로 바뀐다. 열린 아이디어가 없으면 이 질문은 없다.

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

`/grill`, `/go`, `/idea` 밖의 다섯 skill은 [mattpocock/skills](https://github.com/mattpocock/skills)를 옮긴 것이다. 각 `SKILL.md` 끝에 원본 링크가 있다. `/idea`·`gs backlog`와 `/retro <feature>`는 [아이디어 흐름](#아이디어-흐름).

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
`csv-export` 실행에서 worker가 같은 시험 실패로 두 번 재시도했다. 다음 실행이 나아지게 무엇을 바꿀지 보고 싶다.
```
/retro csv-export
```
인자가 `.goldstack/work/` 아래 feature 이름이면 **feature 실행**을 읽는다: `report.md`, `run/state.json`, `run/<NN>/<시도>/`의 `worker.log`·`review/`·`fix/`, spec의 grill 기록, 다른 feature의 `report.md`(같은 실패가 전에도 있었나), `~/.claude/usage-data/report-*.html`(`/insights` 보고서, 있으면). `run/`은 실행한 머신에만 있으니 다른 머신에서 돌린 feature면 report.md만 읽고 그렇다고 말한다. 인자가 없으면 지금 세션, feature가 아닌 인자면 그 세션의 기록을 읽는다.

**큰 로그는 Gemini가 요약한다** — `worker.log` 합계(`cat .goldstack/work/csv-export/run/*/*/worker.log | wc -c`)가 200KB(204800바이트) 이상이면 Claude가 로그를 다 읽지 않고 긴 문맥에 강한 Gemini(agy)에게 요약을 맡긴다. 부르기 전에 한 줄로 알린다:
```
agy로 로그 7개 요약(한도 1회, gs 상한에는 안 셈)
```
그리고 레포 루트에서 한 번만 부른다(`--sandbox`라 읽기 전용, 모델은 `gs config models.agy`):
```
agy -p "<프롬프트>" --sandbox --dangerously-skip-permissions --disable-slash-commands --model "$model"
```
프롬프트에는 `worker.log` 전부, 리뷰 답 `review.txt` 전부, `run/state.json`의 경로가 들어가고, 티켓·시도별 실패 이유, 재시도 횟수, 반복된 리뷰 지적, 오래 걸린 단계를 로그 경로·줄 번호와 함께 요약하게 한다. Claude는 그 요약과 `report.md`·`state.json`으로 후보를 정하고, 근거로 인용할 곳만 로그를 직접 연다. agy가 없거나 실패하면(종료 코드, 빈 답) 다시 부르지 않고 그렇다고 한 줄 말한 뒤 로그마다 끝부분과 오류 줄을 직접 읽는다. 200KB 미만이면 agy를 부르지 않는다. 이 호출은 gs가 아니라 skill이 부르므로 [`[agy] max_calls_per_run`](#agy-max_calls_per_run--gemini-호출-상한)에 세지 않는다.
길 찾기, 자동 검사, 리뷰 기준, `CLAUDE.md`·`AGENTS.md`, 도구 비용, 효과 없는 지시, goldstack 자체(`gs`, skill, spec·티켓 형식), 정보 접근 범주로 고칠 후보를 심각한 순으로 보인다. 후보마다 본 근거와 고칠 곳이 붙고, 다른 feature에도 있던 실패면 `[반복]`이 붙는다. **사람이 고르기 전에는 아무 파일도 바꾸지 않는다.** feature 회고면 고른 후보를 `/idea` 형식으로 `.goldstack/ideas/`에 쓰고(`source: /retro csv-export`), 세션 회고면 고른 것만 고치고 사람이 원하는 후보만 아이디어 함에 적는다.

### `/writing-for-agents` — agent가 읽는 문서를 쓸 때(사용자 호출)
새 skill을 만들거나 레포의 `CLAUDE.md`가 커져서 줄이고 싶다.
```
/writing-for-agents
skills/release/SKILL.md를 새로 쓰려 한다. description부터 같이 다듬자
```
문맥 포인터, 문맥 부담과 인지 부담, 정보 위계, 단계와 완료 기준, 리딩 워드, 쳐내기 기준을 문맥에 싣는다. skill이면 frontmatter와 호출 방식(사용자 호출·모델 호출) 고르기를 [SKILL-MECHANICS.md](../skills/writing-for-agents/SKILL-MECHANICS.md)에서 읽는다. `/retro`도 후보를 쓸 때 이 기준을 읽는다.
