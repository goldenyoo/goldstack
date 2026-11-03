# goldstack

Claude Code로 feature 하나를 끝까지 보내는 개인 운영 kit.
`/grill <feature>`로 사람과 결정을 모두 정해 spec과 티켓을 쓰고, `/go <feature>` 한 번이면 그 뒤로는 사람에게 묻지 않는다.
티켓마다 다른 모델(Claude·codex·agy)이 구현하고 다른 계열이 리뷰하며, 검증을 통과한 것만 모아 PR을 main에 병합한 뒤 다시 검증한다(실패하면 revert).

철학은 [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first"와 "never block on the human"이다. 시작 배경은 [docs/ORIGINS.md](docs/ORIGINS.md).

## 설치

필요한 것: Python 3.12+와 [uv](https://docs.astral.sh/uv/), `git`, 로그인한 `gh`(GitHub), `claude`(Claude Code). 대상 레포의 원격(`git.remote`, 기본 `origin`)은 GitHub 저장소여야 한다(PR·병합을 `gh pr … --repo <owner/repo>`로 한다). 티켓이 쓰는 모델이 있으면 `codex`, `agy`. `herdr`(터미널 멀티플렉서)는 선택이다. `gs go`를 herdr 안에서 돌리면 worker마다 pane이 보이고, 아니면 worker가 화면 없는 프로세스로 돈다.

**1. `gs` CLI** — 이 레포를 받아 설치한다. main을 새로 받을 때마다 다시 실행한다(고정 복사로 설치된다).
```sh
git clone https://github.com/goldenyoo/goldstack && cd goldstack
uv tool install --reinstall .
gs --help
```

**2. Claude Code plugin** — `/grill`·`/go` 같은 skill, worker 차단 hook, 진행 바 mod가 들어 있다. Claude Code에서:
```
/plugin marketplace add /path/to/goldstack   # 이 레포 디렉터리를 로컬 marketplace로 등록
/plugin install goldstack@goldstack          # user scope: 모든 프로젝트에서 쓴다
```
명령줄로는 `claude plugin marketplace add /path/to/goldstack && claude plugin install goldstack@goldstack`. 레포를 새로 받은 뒤에는 `/plugin marketplace update goldstack`.

**3. 대상 레포에서 `gs init`** — goldstack을 쓸 레포 루트에서 한 번 돌린다. 이미 있는 파일은 그대로 둔다.
```console
$ gs init
만듦: .goldstack/config.toml
만듦: .goldstack/local.env.example
추가: .gitignore (.goldstack/local.env, .goldstack/work/*/run/)
.goldstack/config.toml을 확인하고, local.env.example을 local.env로 복사해 값을 채워라
```
`config.toml`의 `git.base`는 `origin/HEAD`에서 찾아 적는다(못 찾으면 `main`). 값이 맞는지 보고, 세 파일을 커밋한다:
`git add .goldstack/config.toml .goldstack/local.env.example .gitignore && git commit -m "goldstack init"`.

**4. `local.env` 채우기(텔레그램 알림을 받을 때만)** — 비밀은 커밋하지 않는 이 파일에만 둔다. gs는 환경 변수를 보지 않는다.
```sh
cp .goldstack/local.env.example .goldstack/local.env
# TG_TOKEN=<BotFather에서 받은 봇 토큰>, TG_CHAT_ID=<알림 받을 채팅 ID>
```
그리고 `config.toml`에서 `[notify] telegram = true`. 켰는데 값이 비면 `gs check`가 경고한다.

**5. 진행 바 mod가 안 보일 때** — `gs go`가 도는 동안 Claude Code 프롬프트 위에 `▓▓▓░░░░░ <feature> 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음` 같은 줄이 떠야 한다.
- 그 Claude Code 세션이 대상 레포 안(루트나 하위 디렉터리)에서 열렸는지 본다. mod는 세션 디렉터리에서 위로 올라가며 처음 만나는 `.goldstack/work/*/run/state.json`을 읽고, 끝나지 않았고 최근 10분 안에 바뀐 실행만 그린다. `gs go`는 상태가 그대로여도 60초마다 state를 다시 쓰므로, 10분 넘게 안 바뀌었다면 `gs go`가 죽은 것이다.
- mod(hooks API)는 early-access라 Claude Code 버전에 따라 동작이 바뀔 수 있다(2.1.317에서 확인). marketplace 설치본에서 mod가 안 뜨면 레포 디렉터리를 직접 싣는다: `claude --plugin-dir /path/to/goldstack`, 또는 늘 그렇게 하려면 환경(또는 settings의 `env`)에 `CLAUDE_CODE_PLUGIN_DIRS=/path/to/goldstack`.
- 바가 없어도 실행에는 영향이 없다. 같은 줄을 `gs status <feature>`가 표 아래에 보여 준다.

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

**3. 결과** — 끝나면 `gs go`의 마지막 줄과 `report.md`를 읽어 세 줄 요약과 PR 링크를 보인다. main 검증까지 끝나면 gs가 최종 report.md를 main에도 push하므로 `git pull`로 받으면 된다:
```
■ 요약: 병합 3
■ 마무리: integration·main 검증 통과, PR 병합 완료
■ 보고서: .goldstack/work/csv-export/report.md · 남은 리뷰 지적 1
■ PR: https://github.com/you/tally/pull/7
```
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
| `/go` | `gs go`로 티켓 실행부터 main 병합·재검증까지 돌리고 세 줄 요약과 PR을 보인다 | grill이 끝나 커밋된 feature를 실행할 때 | `/go csv-export` | 사용자 |
| `/idea` | 생각 하나를 `.goldstack/ideas/<slug>.md` 아이디어 파일로 쓴다. 비슷한 열린 아이디어가 있으면 거기 덧붙일지 묻는다. 커밋 안 함 | 실행·대화 중 다음에 할 일이 떠올랐을 때 | `/idea gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다` | 사용자 |
| `/wait-what` | 방금 설명을 맥락부터, 쉬운 말로, 선택지마다 예시를 붙여 다시 하게 한다 | Claude의 말을 못 따라갔을 때(grill 질문 포함) | `/wait-what` | 사용자 |
| `/handoff` | 지금 대화를 다른 agent가 이어받을 인계 문서로 줄여 임시 디렉터리에 쓴다 | 세션을 바꾸거나 곁가지 일을 떼어 줄 때 | `/handoff 03 실패 원인을 이어서 찾는다` | 사용자 |
| `/retro` | feature 실행 기록(report.md, state.json, worker 로그·리뷰, 다른 feature 보고서와의 반복)이나 세션 하나를 돌아보고 agent 환경(검사, 포인터, 리뷰 기준, 도구, goldstack 자체)을 고칠 후보를 심각한 순으로 제안한다. feature면 고른 후보를 아이디어 함에 쓴다. 고르기 전에는 아무것도 바꾸지 않는다 | `/go`가 끝난 뒤, 실행이 꼬였거나 같은 실수가 반복될 때 | `/retro csv-export`(feature), `/retro`(지금 세션) | 사용자 |
| `/writing-for-agents` | agent가 읽는 문서(skill, `CLAUDE.md`·`AGENTS.md`)의 글쓰기 기준을 문맥에 싣는다 | skill이나 `CLAUDE.md`를 새로 쓰거나 고칠 때 | `/writing-for-agents` 뒤 "이 skill description을 다듬어 줘" | 사용자 |
| `diagnosing-bugs` | 실패 신호(피드백 루프)를 먼저 만들고 재현 → 가설 → 계측 → 수정 → 회귀 시험으로 버그를 잡는다 | 무언가 깨졌다·실패한다·느리다고 말할 때 | "`gs status`가 끝난 실행을 실행 중으로 보여. 진단해" | 모델 |

`/wait-what`부터 아래 다섯은 [mattpocock/skills](https://github.com/mattpocock/skills)(MIT)를 한국어로 옮겨 goldstack에 맞춘 것이다([skills/NOTICE-mattpocock.md](skills/NOTICE-mattpocock.md)). 장면별 예시는 [docs/guide.md](docs/guide.md#skill-사용-장면).

**`gs backlog`**(명령, skill 아님) — 열린 아이디어를 심각도→날짜 순 표로, 그 아래 `.goldstack/out-of-scope/`의 "다시 볼 조건"을 보인다. 읽기 전용. 다음 feature를 고르기 전에 친다. `--all`은 taken·dropped도 보인다.
```console
$ gs backlog
아이디어 (열림 2)
medium  2026-11-03  codex-worker-hook  codex worker를 sandbox 대신 hook으로 막기   (goldstack-v2 grill 라운드 2 질문)
low     2026-11-03  status-review-count  gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다   (goldstack-v3 실행 중 대화)
범위 밖 (다시 볼 조건)
gitlab-support  GitHub 밖 레포에 goldstack을 쓰려 할 때.
```

## 아이디어 흐름

한 실행에서 나온 생각이 다음 feature로 이어진다. `/go <f>`가 끝나면 `/retro <f>`가 그 실행 기록을 읽어 후보를 제안하고, 사람이 고른 것은 아이디어 함 `.goldstack/ideas/<slug>.md`에 파일 하나씩 들어간다(대화 중 떠오른 것은 `/idea <한 줄>`로 바로). 다음 feature 전에 `gs backlog`로 열린 아이디어와 범위 밖의 다시 볼 조건을 훑고, `/grill <다음 feature>`를 부르면 라운드 1 첫 질문이 그 아이디어 중 이번에 넣을 것을 묻는다. 고른 아이디어는 `status: taken`이 되어 목록에서 빠지고, 아이디어 파일은 `/grill`·`/go`의 커밋에 함께 담긴다. 자세히는 [docs/guide.md](docs/guide.md#아이디어-흐름), 파일 형식은 [docs/internals.md](docs/internals.md#아이디어-함).

## 추천 흐름

1. 레포마다 한 번: `gs init` → config 확인 → 커밋(텔레그램을 쓰면 `local.env`).
2. feature마다: `gs backlog`로 후보를 본다 → `/grill <f>`(첫 질문에서 넣을 아이디어를 고른다) → `/go <f>` → 진행 바나 `gs status <f>`로 지켜본다 → 세 줄 요약·PR·텔레그램 → `/retro <f>`로 돌아보고 고른 후보를 아이디어 함에.
3. 실패하면 `report.md`를 읽고, 고칠 것이 있으면 `/grill <f>`로 spec·티켓을 고친 뒤 다시 `/go <f>`(병합된 티켓은 건너뛴다).
4. 곁에서: 떠오른 생각은 `/idea <한 줄>`, 말을 놓치면 `/wait-what`, 버그는 "진단해"(`diagnosing-bugs`), 세션을 넘길 때 `/handoff`, 세션을 돌아볼 때 `/retro`, skill·`CLAUDE.md`를 쓸 때 `/writing-for-agents`.

## 문서 지도

| 문서 | 내용 |
|---|---|
| [docs/guide.md](docs/guide.md) | 상황별 사용 예시: 새 feature, 다른 레포에 들이기, 실행 중 보기, 실패했을 때, 아이디어 흐름, `gs migrate`, skill 사용 장면 |
| [docs/internals.md](docs/internals.md) | 엔진 명세: 파일 배치, config, 상태, 병렬, 실패 처리, 리뷰, 마무리, 진행 계산, 알림, 아이디어 함, 모델 어댑터, plugin·hook·mod, 시험 seam |
| [.goldstack/ideas/README.md](.goldstack/ideas/README.md) | 아이디어 파일 형식 |
| [skills/grill/templates/](skills/grill/templates/) | spec·티켓·범위 밖 파일 형식 |
| [docs/ORIGINS.md](docs/ORIGINS.md) | 시작 배경과 요구사항, 지난 실패 목록 |
| [docs/research/](docs/research/) | 참고한 kit 분석(pstack, mattpocock/skills, 비교표), agy·어댑터 조사 |
| [docs/trials/](docs/trials/) | skill 시험 기록 |
| [LICENSE](LICENSE) | MIT |
