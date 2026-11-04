# goldstack

Claude Code로 feature 하나를 끝까지 보내는 개인 운영 kit.
`/grill <feature>`로 사람과 결정을 모두 정해 spec과 티켓을 쓰고, `/go <feature>` 한 번이면 그 뒤로는 사람에게 묻지 않는다.
티켓마다 다른 모델(Claude·codex·agy)이 구현하고 다른 계열이 리뷰하며(지적을 고치면 수정 커밋을 다시 확인한다), 검증을 통과한 것만 모아 PR을 main에 병합한 뒤 다시 검증한다(실패하면 revert).

철학은 [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first"와 "never block on the human"이다. 시작 배경은 [docs/ORIGINS.md](docs/ORIGINS.md).

## 설치

필요한 것: Python 3.12+와 [uv](https://docs.astral.sh/uv/), `git`, 로그인한 `gh`(GitHub), `claude`(Claude Code). 대상 레포의 원격(`git.remote`, 기본 `origin`)은 GitHub 저장소여야 한다(PR·병합을 `gh pr … --repo <owner/repo>`로 한다). 한계(GitHub만, rebase 병합 미지원, 승인은 사람)는 [docs/guide.md](docs/guide.md#한계). 티켓이 쓰는 모델이 있으면 `codex`, `agy`. `herdr`(터미널 멀티플렉서)는 선택이다. `gs go`를 herdr 안에서 돌리면 worker마다 pane이 보이고, 아니면 worker가 화면 없는 프로세스로 돈다.

**1. `gs` CLI** — 처음 설치는 릴리스 태그에서 한다.
```sh
uv tool install git+https://github.com/goldenyoo/goldstack@v0.1.0
gs --version
```
태그 `v0.1.0`은 v8이 끝난 뒤 사람이 확인하고 만든다. 태그가 아직 없으면 `@v0.1.0` 대신 `@main`을 쓴다.
저장소가 private이면 접근 권한(collaborator)이 필요하다.

**이후 업데이트** — 태그가 아니라 main 채널이다. `gs self-update`가 CLI를 main으로 재설치하고 플러그인도 갱신한다(`--version v0.1.0`처럼 태그로 고정할 수도 있다). `gs go`·`gs doctor`는 시작할 때 설치본이 main보다 뒤처졌으면 경고하고, 이 머신에서 `gs go`가 돌고 있으면 `gs self-update`는 거부한다. 레포가 `[goldstack] requires = ">=0.1"`을 적어 두었는데 설치본이 더 낮으면 `gs check`·`gs go`가 멈춘다. 자세히는 [docs/guide.md](docs/guide.md#버전-맞추기gs-self-update-requires).

**리눅스 서버** — 맥과 같은 설치다. `herdr` 없이 돈다(worker가 화면 없는 프로세스로 돌고 `gs status`로 본다). SSH가 끊겨도 돌게 하려면 `tmux new -s gs` 안에서 `claude`를 열어 `/go`나 `/overnight`를 친다. 떼어 놓기 `Ctrl-b d`, 다시 붙기 `tmux attach -t gs`. 자세히는 [docs/guide.md](docs/guide.md#리눅스-서버에서-쓰기).

**2. Claude Code plugin** — `/grill`·`/go` 같은 skill, worker 차단 hook, 진행 바 mod가 들어 있다. Claude Code에서:
```
/plugin marketplace add goldenyoo/goldstack
/plugin install goldstack@goldstack          # user scope: 모든 프로젝트에서 쓴다
```
명령줄로는 `claude plugin marketplace add goldenyoo/goldstack && claude plugin install goldstack@goldstack`. 플러그인을 갱신하려면 `/plugin marketplace update goldstack`.

**3. 대상 레포에서 `/adopt`** — goldstack을 쓸 레포에서 Claude Code를 열고 `/adopt`. 레포를 훑어 요약 `.goldstack/profile.md`를 쓰고, 그 사이 `gs init`과 `gs doctor`(GitHub 병합 방식·base 보호·필수 승인·필수 검사를 읽어 맞는 config 줄을 보인다)를 거친다. 커밋은 하지 않는다. skill 없이 터미널에서 해도 된다. 이미 있는 파일은 그대로 둔다.
```console
$ gs init
만듦: .goldstack/config.toml
만듦: .goldstack/local.env.example
추가: .gitignore (.goldstack/local.env, .goldstack/work/*/run/)
.goldstack/config.toml을 확인하고, local.env.example을 local.env로 복사해 값을 채워라
gs doctor: you/tally (원격 origin)
병합 방식  merge 허용 → git.merge_method = "merge"
base 보호  main 직접 push 제한 없음
필수 승인  0명
필수 검사  없음
검증       spec verify 없음 → 경고: 검증 없음, 리뷰만으로 병합
```
`config.toml`의 `git.base`는 `origin/HEAD`에서 찾아 적는다(못 찾으면 `main`). 제안을 쓰려면 `gs doctor --write`. 값이 맞는지 보고, 세 파일을 커밋한다:
`git add .goldstack/config.toml .goldstack/local.env.example .gitignore && git commit -m "goldstack init"`.
squash만 허용하는 레포, 보호된 main, 의존성 설치(`[worktree] setup`), 느린 시험은 [docs/guide.md](docs/guide.md#기존-레포에-들이기)대로 한다.

**4. `local.env` 채우기(텔레그램 알림을 받을 때만)** — 비밀은 커밋하지 않는 이 파일에만 둔다. gs는 환경 변수를 보지 않는다.
```sh
cp .goldstack/local.env.example .goldstack/local.env
# TG_TOKEN=<BotFather에서 받은 봇 토큰>, TG_CHAT_ID=<알림 받을 채팅 ID>
```
그리고 `config.toml`에서 `[notify] telegram = true`. 켰는데 값이 비면 `gs check`가 경고한다.

**5. 진행 바 mod가 안 보일 때** — `gs go`가 도는 동안 Claude Code 프롬프트 위에 `▓▓▓░░░░░ <feature> 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음` 같은 줄이 떠야 한다.
- 그 Claude Code 세션이 대상 레포 안(루트나 하위 디렉터리)에서 열렸는지 본다. mod는 세션 디렉터리에서 위로 올라가며 처음 만나는 `.goldstack/work/*/run/state.json`을 읽고, 끝나지 않았고 최근 10분 안에 바뀐 실행만 그린다. `gs go`는 worker를 기다리는 동안 상태가 그대로여도 60초마다 state를 다시 쓰지만, 검증·병합·마무리를 하는 동안에는 쓰지 않는다(리뷰는 루프 밖 스레드에서 돌아 그동안에도 쓴다). 그래서 오래 걸리는 검증(기본 20분까지) 중에는 정상 실행이어도 바가 잠시 사라질 수 있다. 바가 사라졌다고 `gs go`가 죽은 것은 아니다. `gs status <feature>`가 `실행 중(pid …)`인지 `중단됨`인지로 확인한다.
- mod(hooks API)는 early-access라 Claude Code 버전에 따라 동작이 바뀔 수 있다(2.1.317에서 확인). marketplace 설치본에서 mod가 안 뜨면 레포 디렉터리를 직접 싣는다: `claude --plugin-dir /path/to/goldstack`, 또는 늘 그렇게 하려면 환경(또는 settings의 `env`)에 `CLAUDE_CODE_PLUGIN_DIRS=/path/to/goldstack`.
- 바가 없어도 실행에는 영향이 없다. 같은 줄을 `gs status <feature>`가 표 아래에 보여 준다.

**개발할 때** — 로컬 clone에서 CLI와 플러그인을 설치한다. CLI는 고정 복사다.
```sh
git clone https://github.com/goldenyoo/goldstack && cd goldstack
uv tool install --reinstall .
gs --version
```
이 로컬 설치는 설치 commit이 남지 않아 `gs go`·`gs doctor`가 `경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다`를 낸다. 설치본이 main보다 뒤처졌는지 비교할 수 없다는 뜻이고, 실행은 막지 않는다. 원격에 올라간 변경을 받아 다시 설치할 때는 `git pull` 뒤 `gs self-update --from <원격 주소>`를 친다(주소는 `git remote get-url origin`). 그 뒤 설치 commit이 남아 경고가 사라지고 이후에는 `gs self-update`만 쳐도 된다. 아직 올리지 않은 소스 변경을 시험할 때만 `uv tool install --reinstall .`를 쓴다.
Claude Code에서 로컬 디렉터리를 marketplace로 등록한다:
```
/plugin marketplace add /path/to/goldstack
/plugin install goldstack@goldstack
```
레포를 새로 받은 뒤에는 `/plugin marketplace update goldstack`.

## 5분 따라 하기

대상 레포의 base 브랜치(예: main)에서 Claude Code를 열고 시작한다. feature 이름은 `csv-export`라고 하자.

**1. `/grill csv-export`** — Claude가 레포를 먼저 읽고(사실은 묻지 않는다), 사람이 정할 것만 번호 붙여 한 번에 묻는다:
```
라운드 1
1. 출력 위치: A 표준 출력(`tally --csv a.txt > out.csv`) / B 파일 인자(`tally --csv out.csv a.txt`)
   추천 A: 다른 출력 옵션과 같은 모양이다
2. 헤더 줄: A 늘 쓴다(`file,lines,words`) / B `--no-header`로 끌 수 있게
   추천 A: 범위가 작다. 끄는 옵션은 범위 밖에 둔다
yes = 추천 전부 수락. 바꿀 것만 번호로
```
`yes`나 `2. B`처럼 답하면 "이렇게 읽었다"를 한 줄씩 되짚고 `.goldstack/work/csv-export/spec.md`에 적은 뒤 다음 라운드로 간다. 마지막 라운드에서 티켓 분해(순서, 티켓별 구현 모델과 리뷰 계열)를 확인받고 `tickets/`·`.goldstack/out-of-scope/`를 써서 `gs check`가 통과하면 커밋하고 끝낸다.

**2. `/go csv-export`** — `gs check` → base push → `gs go`를 백그라운드로 돌리고 끝날 때까지 기다린다. 중간에 아무것도 묻지 않는다. 기다리는 동안 프롬프트 위의 진행 바나 `gs status csv-export`를 본다.

**3. 결과** — 끝나면 `gs go`의 마지막 줄과 `report.md`를 읽어 세 줄 요약과 PR 링크를 보인다. main 검증까지 끝나면 gs가 최종 report.md를 main에도 push하므로(보호된 main이면 PR로) `git pull`로 받으면 된다:
```
■ 요약: 병합 3
■ 마무리: integration·main 검증 통과, PR 병합 완료
■ 보고서: .goldstack/work/csv-export/report.md · 남은 리뷰 지적 1
■ PR: https://github.com/you/tally/pull/7
```
"남은 리뷰 지적"은 재리뷰가 고쳐졌다고 확인하지 않은 지적 수다(보고만 남긴 지적 포함). 보고서 Summary 아래 `리뷰 지적: 수정됨 2 · 미해결 1`처럼 상태별 개수가 있고, 뜻과 볼 것은 [docs/guide.md](docs/guide.md#리뷰와-재리뷰)에 있다.

`notify.telegram = true`면 같은 때 텔레그램 한 통이 온다:
```
✅ csv-export · main 병합
티켓 3/3 병합 · 41분 · 남은 지적 1
PR https://github.com/you/tally/pull/7
```
티켓이 하나라도 병합되지 않았거나 마무리가 끝나지 않았으면 `❌` 한 줄이다. 예: `❌ csv-export · integration·main 검증 통과, PR 병합 완료 · 티켓 2/3 (03 실패: 검증 실패(로그 …)) · 보고서 .goldstack/work/csv-export/report.md`(병합된 두 티켓은 main에 들어갔다). 다음 할 일은 [docs/guide.md](docs/guide.md#실패했을-때).

**4. 돌아보기(선택)** — `/retro csv-export`가 실행 기록을 읽고 다음 실행을 낫게 할 후보를 제안한다. 고른 것은 아이디어 함에 들어가 다음 `/grill`의 첫 질문이 된다(아래 [아이디어 흐름](#아이디어-흐름)).

## skill

모두 이 plugin에 들어 있다. "사용자"는 사람이 `/이름`으로 부를 때만 돈다. "모델"은 Claude가 상황을 보고 스스로 부른다.

| skill | 무엇 | 언제 쓰나 | 예시 | 호출 |
|---|---|---|---|---|
| `/grill` | 라운드 질문으로 결정을 모두 받아 spec·티켓·범위 밖을 쓰고 `gs check`를 통과시킨다. 열린 아이디어가 있으면 라운드 1 첫 질문이 "이번 feature에 넣을 후보"이고, 고른 것은 `taken`이 된다 | 새 feature를 시작할 때, 이어서 정할 것이 남았을 때 | `/grill csv-export` → 첫 질문 `1. 이번 feature에 넣을 후보: 1) codex-worker-hook 2) status-review-count` 에 `1. 2`로 답 | 사용자 |
| `/go` | `gs go`로 티켓 실행부터 main 병합·재검증까지 돌리고 세 줄 요약과 PR을 보인다. feature를 여러 개 주면 앞 것이 `verified`일 때만 다음을 돌린다 | grill이 끝나 커밋된 feature를 실행할 때, 밤새 둘 이상을 이어 돌릴 때 | `/go csv-export`, `/go csv-export csv-import` | 사용자 |
| `/adopt` | 처음 들이는 레포를 훑어 `gs init`·`gs doctor`를 거치고 레포 요약 `.goldstack/profile.md`를 쓴다(있으면 갱신하고 바뀐 점을 보인다). `/grill`과 worker가 이것을 먼저 읽는다. 커밋 안 함 | 레포에 goldstack을 처음 들일 때, 레포 구조·시험 명령이 바뀌었을 때 | `/adopt` → `gs doctor` 표를 보고 "제안대로 config에 쓸까"에 답 | 사용자 |
| `/idea` | 생각 하나를 `.goldstack/ideas/<slug>.md` 아이디어 파일로 쓴다. 비슷한 열린 아이디어가 있으면 거기 덧붙일지 묻는다. 커밋 안 함 | 실행·대화 중 다음에 할 일이 떠올랐을 때 | `/idea gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다` | 사용자 |
| `/overnight` | 자러 가기 전에 한 번 부르면 feature 여러 개를 밤사이 병합까지 잇는다. 시작할 때 순서·독립 여부·사소한 수정 허락·텔레그램을 한 번에 받아 `.goldstack/overnight/<날짜>.md`에 적고, 사전 점검 뒤에는 묻지 않는다. 맥은 `caffeinate`, 리눅스는 `systemd-inhibit`으로 깨어 있게 하고 아침에 결과 한 장을 남긴다 | 여러 feature를 자는 동안 돌릴 때 | `/overnight csv-export csv-import`, 죽었으면 `/overnight resume` | 사용자 |
| `/feedback` | 사람이 쓴 한 줄을 `gs feedback`으로 goldstack 저장소 issue로 보낸다(`list`는 초안 상태, `send`는 쌓인 것 전송). `[feedback] mode = "off"`면 거부한다. gs 결함 자동 수집은 [guide](docs/guide.md#피드백-gs-결함을-goldstack에-알리기) | gs가 이상하게 동작했을 때, 불편을 알리고 싶을 때 | `/feedback gs status가 끝난 실행을 실행 중으로 보여` | 사용자 |
| `/wait-what` | 방금 설명을 맥락부터, 쉬운 말로, 선택지마다 예시를 붙여 다시 하게 한다 | Claude의 말을 못 따라갔을 때(grill 질문 포함) | `/wait-what` | 사용자 |
| `/handoff` | 지금 대화를 다른 agent가 이어받을 인계 문서로 줄여 임시 디렉터리에 쓴다 | 세션을 바꾸거나 곁가지 일을 떼어 줄 때 | `/handoff 03 실패 원인을 이어서 찾는다` | 사용자 |
| `/retro` | feature 실행 기록(report.md, state.json, worker 로그·리뷰, 다른 feature 보고서와의 반복)이나 세션 하나를 돌아보고 agent 환경(검사, 포인터, 리뷰 기준, 도구, goldstack 자체)을 고칠 후보를 심각한 순으로 제안한다. worker 로그 합계가 200KB 이상이면 먼저 한 줄로 알리고 `gs retro-log`가 모은 파일 하나를 Gemini(agy)에게 주어 요약을 맡긴다. feature면 고른 후보를 아이디어 함에 쓴다. 고르기 전에는 아무것도 바꾸지 않는다 | `/go`가 끝난 뒤, 실행이 꼬였거나 같은 실수가 반복될 때 | `/retro csv-export`(feature), `/retro`(지금 세션) | 사용자 |
| `/writing-for-agents` | agent가 읽는 문서(skill, `CLAUDE.md`·`AGENTS.md`)의 글쓰기 기준을 문맥에 싣는다 | skill이나 `CLAUDE.md`를 새로 쓰거나 고칠 때 | `/writing-for-agents` 뒤 "이 skill description을 다듬어 줘" | 사용자 |
| `diagnosing-bugs` | 실패 신호(피드백 루프)를 먼저 만들고 재현 → 가설 → 계측 → 수정 → 회귀 시험으로 버그를 잡는다 | 무언가 깨졌다·실패한다·느리다고 말할 때 | "`gs status`가 끝난 실행을 실행 중으로 보여. 진단해" | 모델 |

`/wait-what`부터 아래 다섯은 [mattpocock/skills](https://github.com/mattpocock/skills)(MIT)를 한국어로 옮겨 goldstack에 맞춘 것이다([skills/NOTICE-mattpocock.md](skills/NOTICE-mattpocock.md)). 장면별 예시는 [docs/guide.md](docs/guide.md#skill-사용-장면).

## 명령

`gs --help`가 보이는 명령 전부. skill이 대신 부르는 것도 있지만 터미널에서 직접 쳐도 된다.

| 명령 | 무엇 | 언제 쓰나 |
|---|---|---|
| `gs init` | `.goldstack/config.toml`, `local.env.example`, `.gitignore` 줄을 만들고(있는 파일은 그대로) 끝에 `gs doctor`를 한 번 돌린다 | 레포마다 한 번 |
| `gs doctor [--write]` | GitHub의 병합 방식, base 보호, 필수 승인, 필수 검사를 읽어 표와 맞는 config 줄을 보인다. 못 읽으면 `모름`. `--write`는 제안한 `git.merge_method`·`direct_push`·`wait_checks`만 config에 쓴다(`gs init` 끝에는 `--write` 없이 돈다). `worktree.setup`이 lockfile을 바꾸는 명령이면 `npm ci` 같은 명령을 권한다 | 레포에 들일 때, 저장소 설정이 바뀌었을 때 |
| `gs config <섹션.키>` | 설정 값 한 줄(`gs config git.base` → `main`) | 값 확인, skill이 base를 읽을 때 |
| `gs check <f> [--only 01,02]` | spec·티켓 그래프·config·CLI 검사. `touches` 겹침, agy 배정이 상한을 넘으면 경고 | grill 끝, `gs go` 전 |
| `gs go <f> [--only 01,02]` | 티켓 실행 → 리뷰 → 수정·재리뷰(수정 최대 2회) → integration 병합·검증 → PR 병합 → main 재검증(실패하면 revert). 지난 마무리(승인·CI 대기 등)가 남았으면 그것만 끝내고 멈추고, 남은 티켓은 다음 `gs go`가 한다. 네트워크가 끊기면 기다렸다 잇고, 상한을 넘기면 `중단(네트워크)`(종료 코드 3)로 멈춘다. 다시 치면 같은 worktree에서 잇는다 | `/go`가 부른다 |
| `gs go <a> <b> …` | 여러 feature를 차례로. 앞 것이 `verified`가 아니면 거기서 멈춘다. `--only`와 함께 못 쓴다 | 이어 돌릴 feature가 여럿일 때 |
| `gs clean <f> [--force]` | 그 feature의 worktree(`run/wt/*`)와 `gs/<f>/*` 브랜치(로컬·원격)를 지운다. 실행 기록은 남긴다 | 끝난 feature의 남은 흔적(실패 worktree, 옛 integration 브랜치)을 치울 때 |
| `gs status [<f>]` | 실행 상태 표와 진행 줄(읽기 전용) | 실행 중 언제든 |
| `gs self-update [--from <주소>] [--version <태그>]` | CLI를 main(또는 태그)으로 설치 commit이 남게 재설치하고 플러그인을 갱신한다. 이 머신에서 `gs go`가 돌면 거부한다. 로컬 설치는 `--from`이 필요하다 | 설치본이 뒤처졌다는 경고가 나올 때 |
| `gs feedback "한 줄"\|list\|send` | 피드백 초안을 쓰고 보내거나, 초안·전송 상태를 보거나, 쌓인 것을 보낸다 | gs 문제를 알릴 때 |
| `gs backlog [--all]` | 열린 아이디어, 열린 `field-report` issue, 범위 밖의 다시 볼 조건(읽기 전용) | 다음 feature를 고르기 전 |
| `gs retro-log <f>` | `.goldstack/work/<f>/run/retro-log.md` 하나(약 8만 토큰 이하)에 로그·리뷰 답·단계 시각을 모으고 경로를 출력한다 | `/retro`가 큰 로그를 agy에 맡기기 전(skill이 부른다) |
| `gs migrate` | 옛 위치(`.work/` 등)를 `.goldstack/` 아래로 옮긴다 | v2 전 레포를 옮길 때 한 번 |
| `gs hook <pretooluse\|agy-pretooluse>` | worker 차단 hook 진입점 | 직접 치지 않는다(plugin·agy가 부른다) |

```console
$ gs go csv-export csv-import
…(csv-export의 실행 출력과 ■ 요약)
■ csv-export: verified → csv-import 시작
…(csv-import의 실행 출력과 ■ 요약)
$ gs clean csv-export
지움: worktree /home/you/tally/.goldstack/work/csv-export/run/wt/03 (미커밋 변경도 지움)
지움: worktree /home/you/tally/.goldstack/work/csv-export/run/wt/03-retry-1 (미커밋 변경도 지움)
지움: worktree 2, 로컬 브랜치 2, 원격 브랜치 0 · 실행 기록은 남김
```
verified로 끝난 feature의 integration worktree·브랜치는 `gs go`가 스스로 지운다. 앞 feature가 gs 자체를 고쳐도 같은 `gs go a b` 안의 다음 feature는 옛 gs로 돈다(`gs self-update`를 하지 않는다). 자세히는 [docs/guide.md](docs/guide.md#여러-feature-이어-돌리기gs-go-a-b)·[`gs clean`](docs/guide.md#끝난-feature-치우기gs-clean).

**`gs backlog`**(명령, skill 아님) — 열린 아이디어를 심각도→날짜 순 표로, 그 아래 `.goldstack/out-of-scope/`의 "다시 볼 조건"을 보인다. 읽기 전용. 다음 feature를 고르기 전에 친다. `--all`은 taken·dropped도 보인다.
```console
$ gs backlog
아이디어 (열림 2)
medium  2026-11-03  codex-worker-hook  codex worker를 sandbox 대신 hook으로 막기   (goldstack-v2 grill 라운드 2 질문)
low     2026-11-03  status-review-count  gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다   (goldstack-v3 실행 중 대화)
범위 밖 (다시 볼 조건)
gitlab-support  GitHub 밖 레포에 goldstack을 쓰려 할 때.
```

## 모델·검증 키

모델과 검증을 고르는 키다. 전체 표는 [config](docs/guide.md#config-키), [spec](docs/guide.md#spec-frontmatter-키), [티켓](docs/guide.md#티켓-선택-키와-agy-한도).

| 어디 | 키 | 없으면 | 뜻 |
|---|---|---|---|
| config | `[tiers.claude]`, `[tiers.codex]`, `[tiers.agy]` | `gs init` 새 config에는 있다. 키가 없으면 그 계열은 `models.*`·CLI 기본값 | `small`·`medium`·`large`마다 `"모델/effort"`(effort 생략 가능) |
| config | `[tiers] review`, `rereview` | `large`, `medium` | 첫 리뷰·재리뷰의 등급 |
| config | `models.failure_summary` | `models.judge` | 재시도 brief용 실패 요약 모델. `gs init` 새 config는 `haiku` |
| config | `timeouts.network_wait_minutes` | `60` | 끊김 하나의 대기 합계. 넘기면 `중단(네트워크)` |
| spec | `verify` | 필수 | 마무리(integration, 병합 뒤 main)의 전체 검증. 아래 둘이 없으면 티켓 검증도 |
| spec | `verify_ticket` | `verify` | 티켓 검증 명령 |
| 티켓 | `verify` | spec `verify_ticket` → spec `verify` | 이 티켓만의 검증 명령. 문서·설정 티켓을 좁힐 때 쓴다 |
| 티켓 | `tier` | `medium` | `small`·`medium`·`large`. 등급표에서 이 worker의 모델·effort를 고른다. 재시도는 한 등급 올린다 |

티켓 검증은 명령과 상관없이 integration에 합친 **병합 트리**에서 돈다. worktree의 커밋 안 된 파일로는 통과할 수 없고, 검증이 트리를 바꾸면 실패다. `verify_ticket`을 따로 두기 전에 전체 시험을 프로세스로 나눠 빠르게 만들 수 있는지 먼저 본다. 이 레포는 파일마다 프로세스 하나로 순차 약 11분 걸리던 시험을 약 4분에 돌린다:
```yaml
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p
```
조건과 다른 도구의 예는 [docs/guide.md](docs/guide.md#예시-전체-시험을-프로세스로-나누기).

## 아이디어 흐름

한 실행에서 나온 생각이 다음 feature로 이어진다. `/go <f>`가 끝나면 `/retro <f>`가 그 실행 기록을 읽어 후보를 제안하고, 사람이 고른 것은 아이디어 함 `.goldstack/ideas/<slug>.md`에 파일 하나씩 들어간다(대화 중 떠오른 것은 `/idea <한 줄>`로 바로). 다음 feature 전에 `gs backlog`로 열린 아이디어와 범위 밖의 다시 볼 조건을 훑고, `/grill <다음 feature>`를 부르면 라운드 1 첫 질문이 그 아이디어 중 이번에 넣을 것을 묻는다. 고른 아이디어는 `status: taken`이 되어 목록에서 빠지고, 아이디어 파일은 `/grill`·`/go`의 커밋에 함께 담긴다. 자세히는 [docs/guide.md](docs/guide.md#아이디어-흐름), 파일 형식은 [docs/internals.md](docs/internals.md#아이디어-함).

## 추천 흐름

1. 레포마다 한 번: `/adopt`(`gs init`, `gs doctor`, profile) → `gs doctor --write` 확인 → 커밋 → 필요하면 `[worktree] setup`(텔레그램을 쓰면 `local.env`).
2. feature마다: `gs backlog`로 후보를 본다 → `/grill <f>`(첫 질문에서 넣을 아이디어를 고른다) → `/go <f>`(여럿이면 `/go <a> <b>`) → 진행 바나 `gs status <f>`로 지켜본다 → 세 줄 요약·PR·텔레그램 → `/retro <f>`로 돌아보고 고른 후보를 아이디어 함에.
3. 끝난 feature에 실패 worktree나 옛 브랜치가 남았으면 `gs clean <f>`(verified면 integration 흔적은 이미 지워져 있다).
4. 실패하면 `report.md`를 읽고, 고칠 것이 있으면 `/grill <f>`로 spec·티켓을 고친 뒤 다시 `/go <f>`(병합된 티켓은 건너뛴다). `중단(네트워크)`면 고칠 것 없이 네트워크가 돌아온 뒤 다시 돌린다.
5. 곁에서: 떠오른 생각은 `/idea <한 줄>`, 말을 놓치면 `/wait-what`, 버그는 "진단해"(`diagnosing-bugs`), 세션을 넘길 때 `/handoff`, 세션을 돌아볼 때 `/retro`, skill·`CLAUDE.md`를 쓸 때 `/writing-for-agents`.

## 문서 지도

| 문서 | 내용 |
|---|---|
| [docs/guide.md](docs/guide.md) | 상황별 사용 예시: 기존 레포에 들이기(`/adopt`, `gs doctor`, squash만 허용·보호된 main·느린 시험·전체 시험 나누기 예시, config·spec 키 표, 한계), 새 feature, 티켓 키(`tier`, `verify`, `touches`, `second_reviewer`)와 agy 한도, 리뷰와 재리뷰(지적 상태 5가지, 리뷰 중 자리, 2차 재리뷰의 재확인, 보고만 지적의 아이디어 파일, sandbox 네트워크), 실행 중 보기, 실패했을 때(네트워크 끊김 포함), 여러 feature 이어 돌리기, `gs clean`, 아이디어 흐름(`gs retro-log` 포함), 버전 맞추기(`gs self-update`, `requires`), 피드백(보내는 것·안 보내는 것·끄는 법), `/overnight`, 리눅스 서버, `gs migrate`, skill 사용 장면 |
| [docs/internals.md](docs/internals.md) | 엔진 명세: 파일 배치, config, `gs doctor`, 상태와 측정 필드, 병렬, 실패 처리, 리뷰(재리뷰와 state 필드, 두 리뷰 합치기, 리뷰 스레드와 자리, agy 횟수), 네트워크 끊김(대기, `중단(네트워크)`, 리뷰·판단 호출), 마무리(순서와 재개 뒤 멈춤, squash 확인·revert·되살림, CI 대기, 보호된 base, 준비 실패, integration-final 건너뛰기)와 자동 정리, `gs clean`, 진행 계산(ETA 표본), 알림, 아이디어 함(보고만 지적 파일, `gs retro-log`), 피드백 수집, 버전·self-update, Actions 시험, 모델 어댑터(조사로 정한 worker 명령), plugin·hook·mod, 시험 seam |
| [.goldstack/ideas/README.md](.goldstack/ideas/README.md) | 아이디어 파일 형식 |
| [skills/grill/templates/](skills/grill/templates/) | spec·티켓·범위 밖 파일 형식 |
| [docs/ORIGINS.md](docs/ORIGINS.md) | 시작 배경과 요구사항, 지난 실패 목록 |
| [docs/research/](docs/research/) | 참고한 kit 분석(pstack, mattpocock/skills, 비교표), agy·어댑터 조사, worker 플러그인 격리·codex hook 실험 기록 |
| [docs/trials/](docs/trials/) | skill 시험 기록 |
| [LICENSE](LICENSE) | MIT |
