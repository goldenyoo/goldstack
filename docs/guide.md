# goldstack 사용 가이드

상황별로 무엇을 치고 무엇이 보이는지 적는다. 설치는 [README](../README.md#설치), 엔진이 안에서 하는 일은 [internals.md](internals.md).
예시의 feature 이름은 `csv-export`, base 브랜치는 `main`, 원격은 `origin`이다. 실제 값은 `gs config git.base`, `gs config git.remote`가 알려 준다.

- [기존 레포에 들이기(`/adopt`, `gs doctor`, `[worktree] setup`)](#기존-레포에-들이기)
  - [예시: squash만 허용](#예시-squash만-허용) · [보호된 main + 필수 승인](#예시-보호된-main--필수-승인) · [느린 시험](#예시-느린-시험verify_ticket-verify_retries) · [전체 시험 나누기](#예시-전체-시험을-프로세스로-나누기)
  - [config 키](#config-키) · [spec frontmatter 키](#spec-frontmatter-키) · [한계](#한계)
- [새 feature](#새-feature)
- [티켓 선택 키와 agy 한도(`tier`, `verify`, `touches`, `second_reviewer`, `[agy] max_calls_per_run`)](#티켓-선택-키와-agy-한도)
- [리뷰와 재리뷰(수정 최대 2회, 보고서의 지적 상태 5가지)](#리뷰와-재리뷰)
- [실행 중 보기](#실행-중-보기)
- [실패했을 때](#실패했을-때) · [네트워크가 끊겼을 때](#네트워크가-끊겼을-때)
- [여러 feature 이어 돌리기(`gs go a b`)](#여러-feature-이어-돌리기gs-go-a-b)
- [끝난 feature 치우기(`gs clean`)](#끝난-feature-치우기gs-clean)
- [아이디어 흐름(`/retro` → `/idea` → `gs backlog` → `/grill`)](#아이디어-흐름)
- [피드백: gs 결함을 goldstack에 알리기](#피드백-gs-결함을-goldstack에-알리기) · [`/overnight`: 자는 동안 이어 돌리기](#overnight-자는-동안-이어-돌리기)
- [버전 맞추기(`gs self-update`, `requires`)](#버전-맞추기gs-self-update-requires)
- [리눅스 서버에서 쓰기](#리눅스-서버에서-쓰기)
- [기존 레포 옮기기(`gs migrate`)](#기존-레포-옮기기gs-migrate)
- [skill 사용 장면](#skill-사용-장면)

## 기존 레포에 들이기

이미 진행 중인 레포(병합 방식, main 보호, CI, 의존성 설치, 느린 시험이 제각각)에 goldstack을 처음 들이는 순서다. 아래 출력은 가짜 `gh`로 `gs`를 돌려 얻은 실제 형식이다. PR 주소·이름을 예시로 바꾸고 앞뒤 줄은 줄였다.

**1. 설치** — `gs` CLI와 plugin을 머신에 한 번 설치한다(README ["설치"](../README.md#설치) 1–2). 대상 레포의 원격은 GitHub여야 한다([한계](#한계)).

**2. `/adopt`** — 대상 레포에서 Claude Code를 열고 `/adopt`. 레포를 훑고, `.goldstack/config.toml`이 없으면 `gs init`을 돌리고, `gs doctor`를 보이고, 레포 요약 `.goldstack/profile.md`(구조, 빌드·시험 명령과 잰 시간, 관례, 주의점, CI)를 쓴다. 사람에게 묻는 것은 "제안대로 config에 쓸까"뿐이다. 다시 부르면 profile을 갱신하고 바뀐 점을 보인다. 커밋은 하지 않는다. `/grill`이 profile을 가장 먼저 읽고, worker brief가 "먼저 읽어라"로 가리킨다.

`gs doctor`는 터미널에서 직접 쳐도 된다. 저장소 설정을 읽어 표와 맞는 config 줄을 보인다(읽기 전용):
```console
$ gs doctor
gs doctor: you/tally (원격 origin)
병합 방식  squash만 허용(gs 지원 방식 중) → git.merge_method = "squash"
base 보호  main 직접 push 금지 → git.direct_push = false
필수 승인  1명 → gs는 PR을 열고 승인을 기다린다(병합 대기)
필수 검사  build, test → git.wait_checks = true
검증       spec verify 없음 → 경고: 검증 없음, 리뷰만으로 병합
```
- **병합 방식**: merge 커밋을 허용하면 `merge`를 제안한다(squash도 함께 허용해도). merge가 꺼져 있고 squash가 허용이면 `squash`. 둘 다 꺼져 있으면(rebase만) `경고: gs가 지원하지 않는 병합 방식`이고 제안이 없다.
- **`모름(<이유>)`**: 읽지 못한 항목이다. 제안도 쓰기도 하지 않으니, 아는 값이면 config를 손으로 고친다. 보호 규칙을 읽는 classic API는 관리자 권한이 필요해 권한이 없으면 rulesets API로 넘어가는데, 거기에도 규칙이 없으면 세 줄이 모두 `모름`이다. 보호가 전혀 없는 브랜치도 classic API가 404라서 같다:
  ```
  base 보호  모름(gh: Must have admin rights to Repository. (HTTP 403))
  ```
- **검증**: `.goldstack/work/*/spec.md`마다 한 줄(`검증       csv-export verify = npm test`). spec이 없거나 `verify`가 `true`·`:`면 `spec verify 없음 → 경고: 검증 없음, 리뷰만으로 병합`이다. 시험이 정말 없는 레포는 spec에 `verify: "true"`로 그 사실을 적는다(이 값은 늘 통과하므로 리뷰만으로 병합한다).
- 원격이 GitHub가 아니면 첫 줄이 `gs doctor: GitHub 원격 아님 (원격 origin): …`이고 네 줄이 `모름`이다. `gs check`·`gs go`는 이 원격에서 오류로 멈춘다.

**3. `gs doctor --write` 확인·커밋** — 제안을 config에 쓰게 했으면 표 아래에 바뀐 키마다 한 줄이 더 나온다:
```console
$ gs doctor --write
…(위와 같은 표)
git.merge_method: "merge" → "squash" (squash만 허용(gs 지원 방식 중))
git.direct_push: true → false (main 직접 push 금지)
git.wait_checks: false → true (build, test)
```
쓰는 규칙: `git.merge_method`·`git.direct_push`·`git.wait_checks` 중 **제안이 있는 키만**, 값이 다를 때만 고친다. 다른 줄과 주석은 그대로 둔다. `모름`과 "제안 없음"(직접 push 제한 없음, 필수 검사 없음)은 쓰지 않으니 이미 있는 값을 되돌리지 않는다. 다만 merge가 허용된 저장소에서 config를 손으로 `squash`로 바꿔 두면 `--write`가 `merge`로 되돌린다. 이때는 `--write` 없이 `gs doctor`만 쓴다.

`git diff .goldstack/config.toml`로 확인하고 커밋한다(보호된 main이면 이 커밋은 첫 feature의 grill PR에 함께 올린다. [아래](#예시-보호된-main--필수-승인)):
```sh
git add .goldstack/config.toml .goldstack/local.env.example .gitignore
git commit -m "goldstack init"
```
`.goldstack/profile.md`는 여기 넣지 않아도 된다. 다음 `/grill`·`/go`의 커밋 경로에 들어 있다.

**4. `[worktree] setup` 채우기** — gs가 만드는 worktree에는 커밋된 파일만 있다. `node_modules`, 가상환경, `.env`처럼 커밋하지 않는 것이 있어야 시험이 돌면 준비 명령을 한 줄 적는다.
```toml
[worktree]
setup = "npm ci"

[timeouts]
setup_minutes = 15            # 준비 명령 한 번의 상한(기본 15)
```
- 티켓, integration, 병합 뒤 base 검증 worktree마다 worker·verify 전에 `bash -c`로 돈다. 그 worktree가 현재 디렉터리이고, gs가 직접 돌리므로 worker 차단 hook 밖이다. 비어 있으면 돌지 않는다.
- 복사 목록 키는 없다. 복사도 이 한 줄로 한다. 주 레포의 `.env`를 복사하는 예(TOML 작은따옴표는 안쪽 `"`를 그대로 둔다):
  ```toml
  setup = 'npm ci && cp "$(git rev-parse --git-common-dir)/../.env" .env'
  ```
- 산출물(`node_modules`, `.env`)은 `.gitignore`에 있어야 한다. 없으면 worker의 `git add -A`에 섞여 들어간다.
- **lockfile을 바꾸지 않는 명령을 쓴다**: `npm ci`, `yarn --frozen-lockfile`, `uv sync --locked`. setup이 추적 파일을 바꾸면 gs가 setup 직후(실패·시간 초과여도) 되돌리고 경고한다:
  ```
  경고: setup이 추적 파일을 바꿨다 → 되돌림: package-lock.json
  ```
  실패로 치지 않으므로 티켓·병합·revert에는 영향이 없고, 설치 산출물은 그대로 둔다. 같은 줄이 `setup.log`와 보고서(티켓이면 티켓별 결과의 이유, integration·base면 Merge Danger)에 남는다. 다만 되돌린 lockfile과 방금 설치한 산출물이 어긋난 채 시험이 돌 수 있으니, 이 경고를 보면 명령을 고친다. `gs doctor`는 setup에 `npm install`·`npm i`나 잠금 옵션 없는 `yarn`이 있으면 표 끝에 줄을 더하고(`--write`는 고치지 않는다), `/adopt`도 같은 것을 권한다:
  ```
  setup  lockfile을 바꾸지 않는 명령 권장: npm ci · yarn --frozen-lockfile · uv sync --locked
  ```
- 시간이 worktree 수만큼 든다(티켓 수 + 재시도 + 2). 캐시를 쓰는 설치 명령이 좋다.
- 돌 때 출력은 `■ integration 준비 중`, `[01] 준비 중`, `■ main 준비 중`이다. 실패는 위치마다 다르다: 티켓이면 `[01] 실패: 준비 실패`(재시도 없음), integration이면 `■ 마무리: 준비 실패 → 병합 안 함`, 병합 뒤 base면 `■ 마무리: base 미검증(준비 실패)`(revert하지 않고 다음 `gs go`가 base 검증부터 다시 한다). 자세히는 [internals](internals.md#준비-실패-위치별-처리).

고쳤으면 커밋한다(`git commit -am "goldstack: worktree 준비 명령"`).

**5. 첫 `/grill`** — 이제 평소처럼 `/grill <feature>` → `/go <feature>`다([새 feature](#새-feature)). spec에 `verify`를 정할 때 `.goldstack/profile.md`의 시험 시간을 보고, 느리면 먼저 [전체 시험을 나눠](#예시-전체-시험을-프로세스로-나누기) 줄이고, 그래도 느리면 [느린 시험 예시](#예시-느린-시험verify_ticket-verify_retries)대로 한다. 레포의 조건에 맞는 예시를 아래에서 고른다.

### 예시: squash만 허용

저장소가 squash 병합만 허용한다. config:
```toml
[git]
merge_method = "squash"
```
`gs go`는 PR을 `gh pr merge <url> --squash --match-head-commit <검증한 head>`로 병합한다. 출력은 merge 때와 같고, main에는 커밋이 하나 들어간다. 티켓별 `gs-ticket` 줄은 다음 실행이 병합된 티켓을 알아보는 표시다.
```console
$ git log -2 --format='%h %s%n%b' origin/main
5677e8e gs: csv-export 최종 보고서(병합 후)

ce0c5fd csv-export: gs go (#7)
01 CSV 헤더 줄
02 CSV 행 출력

gs-ticket: csv-export/01
gs-ticket: csv-export/02
```
병합 뒤 gs는 squash 커밋의 tree가 검증한 integration의 tree와 같은지 본다. main 검증이 실패하면 그 커밋 하나를 revert한다:
```
■ main 검증: npm test
■ 최종 보고서를 main에 push했다(de7c5c0a)
■ 요약: 병합 2
■ 마무리: main 검증 실패 → revert 56e0ce620d98867f7f3cfbad4cada7a262fd750b를 main에 push함
```
**되살린 feature를 squash로 병합할 때** — main에서 되돌린 feature를 다음 PR이 다시 들이면, squash 본문에 새 티켓과 함께 되살린 티켓을 적고 끝에 어떤 revert를 되돌렸는지 남긴다. 이 줄 덕분에 state가 없는 새 clone에서도 gs가 같은 revert를 또 되살리지 않고, 되살린 티켓을 병합된 것으로 알아본다:
```
7bd21a0 csv-export: gs go (#9)
01 CSV 헤더 줄
02 CSV 행 출력
03 CSV 구분자 옵션

gs-ticket: csv-export/01
gs-ticket: csv-export/02
gs-ticket: csv-export/03

This reverts commit 56e0ce620d98867f7f3cfbad4cada7a262fd750b.
```

**실행 중에 main이 움직이면 멈춘다** — integration은 실행을 시작할 때 main을 합친다. PR 병합 전에 다른 사람의 커밋이 main에 들어가면 squash 커밋 tree에 검증하지 않은 내용이 섞이므로, gs는 main 검증도 revert도 하지 않고 멈춘다. 다시 `gs go`해도 같은 오류다:
```
■ 마무리: 마무리 실패: squash 커밋 bc58fbbe…의 tree가 검증한 integration d059e174…의 tree와 다르다(PR 병합 사이에 main가 움직였을 수 있다). 검증하지 않은 내용이 main에 들어갔으니 사람이 main를 확인하라
gs go: git 오류: squash 커밋 bc58fbbe…
```
feature는 이미 main에 들어가 있다. main을 직접 확인한 뒤 빠져나오는 법은 `gs clean csv-export --force` → `gs go csv-export`다. 병합된 티켓은 main의 `gs-ticket` 줄로 알아보고 건너뛰며, 최신 main을 다시 검증하고 보고서를 새 PR로 올린다. 이때 main 검증이 실패해도 gs가 되돌리는 것은 그 보고서 병합뿐이다. feature의 squash 커밋은 사람이 revert한다. 커밋이 잦은 레포에서 merge 커밋을 허용할 수 있으면 `merge_method = "merge"`가 낫다(이 검사가 없고, 병합 뒤 main을 다시 검증한다).

### 예시: 보호된 main + 필수 승인

main에 직접 push가 막혀 있고 PR에 승인 1명, 필수 검사 `build`·`test`가 있다. config:
```toml
[git]
direct_push = false
wait_checks = true

[timeouts]
checks_minutes = 60           # CI 대기 한 번의 상한(기본 60)
checks_grace_seconds = 60     # 검사가 하나도 안 보일 때 등록을 기다리는 시간(기본 60)
```

**spec·티켓은 먼저 사람이 PR로 올린다** — `gs go`는 spec·티켓이 원격 main에 있어야 시작한다. `/go`의 `git push origin main`은 보호에 막히고, `direct_push = false`는 이 push를 바꾸지 않는다. 그래서 `/grill`이 커밋한 뒤 그 커밋(들여올 때의 config·`.gitignore` 커밋 포함)을 브랜치로 올려 사람이 병합한다:
```sh
git switch -c grill/csv-export       # 로컬 main의 커밋을 브랜치로
git push -u origin grill/csv-export
gh pr create --fill --base main      # 승인·병합은 사람이 한다
# 병합된 뒤 로컬 main을 원격에 맞춘다(squash면 안 그러면 갈라져 /go가 멈춘다)
git switch main && git fetch origin && git reset --keep origin/main
```
그 뒤 `/go csv-export`. 로컬 main이 원격과 같으니 push할 것이 없다.

**feature PR** — 티켓이 끝나면 PR을 열고 CI를 기다린다. 필수 검사가 끝나면 병합을 시도하고, 승인이 없어 막히면 PR을 열어 둔 채 끝난다(종료 1, 알림):
```
■ integration-final: 보고서만 바뀜, 건너뜀
■ PR #7: CI 검사 대기 중(build ✓, test …)
■ PR #7: CI 검사 대기 중(build ✓, test ✓)
■ 요약: 병합 3
■ 마무리: 사람 승인 필요: https://github.com/you/tally/pull/7. main 검증은 미실행
■ 보고서: .goldstack/work/csv-export/report.md · 남은 리뷰 지적 1
■ PR: https://github.com/you/tally/pull/7
```
```
❌ csv-export · 사람 승인 필요: https://github.com/you/tally/pull/7. main 검증은 미실행 · 티켓 3/3 · 보고서 .goldstack/work/csv-export/report.md
```
CI 대기 중에는 진행 바가 `▓▓▓▓▓▓▓▓ csv-export 3/3 · CI 대기 중 · 31분 · 마무리 중`이다(마무리 시간을 아는 레포에서 아직 남았으면 `약 4분 남음`처럼 시간을 보인다. 어림이 끝났으면 `마무리 중`). 검사가 실패하거나 시간을 넘기면 병합하지 않고 `■ 마무리: CI 실패: build, test` 또는 `■ 마무리: CI 대기 시간 초과`로 끝난다. 고치는 커밋을 PR 브랜치에 넣거나 CI를 다시 돌린 뒤 `gs go`하면 검사를 다시 읽어 이어 간다(head가 바뀌었으면 그 head를 먼저 `verify`한다).

**CI가 아직 안 떴을 때** — PR을 막 열면 검사가 등록되기 전일 수 있다. 보호 규칙에서 필수 검사 이름을 읽었으면(`build`, `test`) 그 이름이 나타나 끝날 때까지 기다린다(`timeouts.checks_minutes`까지, 아직 없는 이름은 `…`로 보인다). 읽지 못했으면(보호 규칙을 읽는 API에 권한이 없거나 규칙이 없으면) 검사가 하나도 안 보이는 동안 `timeouts.checks_grace_seconds`(기본 60초)까지 기다리고, 그 안에 하나라도 보이면 끝날 때까지 기다린다. 끝까지 없으면 병합을 시도한다:
```
■ PR #7: CI 검사 대기 중(검사 없음)
■ PR #7: 검사 없음 → 병합
```
CI가 늦게 뜨는 저장소면 값을 올리고, 기다릴 필요가 없으면 `0`으로 둔다. revert·보고서 PR의 CI 대기에도 같게 적용된다.

**승인 뒤** — GitHub에서 승인하고(병합까지 해도 된다) 터미널에서 `gs go csv-export`를 다시 친다. worker는 다시 돌지 않는다. `/go`로 치려면 먼저 `git pull --ff-only`다. PR이 병합되면 로컬 main이 원격보다 뒤처져 `/go`가 멈춘다. main을 검증하고 최종 보고서를 `gs/csv-export/report` PR로 올리는데, 이 PR에도 승인이 필요하면 또 멈춘다:
```
[01] 이미 병합됨
■ main 검증: npm test
■ main에 직접 push하지 않는다: report PR https://github.com/you/tally/pull/8
■ 요약: 이미 병합 3
■ 마무리: 사람 승인 필요: https://github.com/you/tally/pull/8
```
PR #8을 승인하고 한 번 더 치면 끝난다(종료 0):
```
■ 최종 보고서를 PR https://github.com/you/tally/pull/8로 main에 병합했다(f3dcd7e1)
■ 요약: 이미 병합 3
■ 마무리: integration·main 검증 통과, PR 병합 완료
```
보고서 PR을 기다리는 동안(phase `report_pending`) 코드는 이미 main에 있고 검증도 끝났다. 그래도 종료 1이라 `gs go a b`는 `■ csv-export: report_pending → 여기서 멈춤(남은: csv-import)`으로 멈춘다. 보고서를 main에 남길 필요가 없으면 PR을 그대로 둬도 코드에는 영향이 없다.

**재개는 거기서 멈춘다** — 지난 마무리(승인·CI 대기, 병합 뒤 main 검증, 보고서 PR 등)를 이어 가는 `gs go`는 그것만 끝낸다. 새 worker도 두 번째 PR도 없다. 재개가 `verified`로 끝나도 티켓이 남아 있으면(기다리는 사이 티켓을 더했거나, 지난 실행에서 실패·건너뜀이었거나, `--only` 범위를 넓혔으면) 그 실행은 멈추고 남은 티켓은 다음 `gs go`가 맡는다:
```
[01] 이미 병합됨
■ 최종 보고서를 PR https://github.com/you/tally/pull/8로 main에 병합했다(f3dcd7e1)
■ 남은 티켓 1개 → 다음 gs go
■ 요약: 이미 병합 3, 대기 1
■ 마무리: integration·main 검증 통과, PR 병합 완료
```
종료 코드는 1이고(`reverted`로 끝나도 같다) 텔레그램에도 `남은 티켓 1개 → 다음 gs go`가 붙는다. 같은 명령을 한 번 더 치면 main(최종 보고서 포함)을 합친 integration에서 남은 티켓을 돌리고 새 PR을 연다. 그래서 새 PR이 report.md에서 충돌하지 않는다. 승인이 아직이면 티켓도 시작하지 않고 그대로 기다린다.

**main 검증이 실패하면** — revert도 PR(`gs/csv-export/revert`)이다. 승인이 필요하면 **되돌리기 전에 멈추므로 깨진 코드가 main에 남아 있다.** 알림을 보면 바로 승인한다:
```
■ main 검증: npm test
■ main에 직접 push하지 않는다: revert PR https://github.com/you/tally/pull/8
■ 마무리: 사람 승인 필요: https://github.com/you/tally/pull/8
```
승인 뒤 `gs go`는 revert를 병합하고 마무리를 `main 검증 실패 → revert <sha>를 PR https://github.com/you/tally/pull/8로 main에 병합함`으로 적은 뒤 보고서 PR로 간다. 그러니 feature 하나에 사람 승인은 보통 2번(feature, 보고서), revert가 있으면 3번이다.

**revert PR이 승인을 기다리는 동안 main이 바뀌면** — 사람이 그 사이 main을 고쳤을 수 있다. 다음 `gs go`는 revert PR이 이미 병합됐는지 먼저 보고, 병합됐으면 재검증 없이 `reverted`로 끝낸다. 아직이고 main이 검증 실패 때 그대로면 PR을 다시 읽고 기다린다. main이 움직였으면 옛 revert를 병합하지 않고 최신 main을 다시 검증한다(`main-recheck`):
- **통과** — 되돌릴 필요가 없다. gs가 그 revert PR을 닫고 `gs/csv-export/revert` 원격 브랜치를 지운 뒤 `verified`로 끝낸다. `■ 최신 main 재검증 통과: revert PR #8을 닫았다`가 나오고 마무리와 보고서에 닫은 PR 번호가 남는다. PR을 닫지 못하면 열린 PR이 남았다고 마무리에 적고 그 PR은 병합하지 않으며, 다음 `gs go`가 닫기를 다시 시도한다. PR은 닫았는데 원격 브랜치를 지우지 못하면 PR은 이미 닫힌 상태이고, 다음 `gs go`는 브랜치 삭제만 다시 시도한다.
- **실패** — 최신 main 위에 revert를 다시 만들어 같은 `gs/csv-export/revert` 브랜치를 갱신한다. 옛 revert 커밋은 쓰지 않는다. 다시 만든 PR이 승인을 기다리면 지금처럼 `revert_pending`으로 멈춘다.

사람이 revert PR을 병합하지 않고 닫았고 main이 그대로면 gs는 PR을 다시 연다(이 동작은 그대로다).

**승인·CI를 기다릴 때 report.md** — 기다리는 PR의 head를 바꾸지 않으려고 feature PR 대기 중에는 보고서를 다시 쓰지 않는다. 그래서 report.md·PR 본문의 마무리 줄은 `마무리: preparing · 병합 전`이다. 지금 상태는 `■ 마무리:` 줄, 알림, `jq .finish .goldstack/work/csv-export/run/state.json`으로 본다.

### 예시: 느린 시험(`verify_ticket`, `verify_retries`)

전체 시험이 40분이고 가끔 flaky하다. 티켓마다 40분을 쓰지 않고 빠른 검사만 돌리고, 전체는 integration과 main에서만 돌린다. spec frontmatter:
```yaml
---
feature: csv-export
verify: npm test
verify_ticket: npm run test:unit
verify_minutes: 60
verify_retries: 1
idle_minutes: 30
---
```
- `verify_ticket`: 티켓마다 worker가 커밋 전에 돌리고(brief에 이 명령이 들어간다. 개발 중에는 관련 시험만 돌리라고 함께 적혀 있다), gs가 그 티켓을 integration에 합친 **병합 트리**에서 다시 돌린다. worktree의 커밋 안 된 파일로는 통과할 수 없다. 검증이 트리를 바꾸면(gitignore 밖에 쓰면) `검증 중 worktree가 바뀌었다`로 실패하니 출력은 gitignore 안이나 레포 밖으로 보낸다(`uv build -o "$(mktemp -d)"`).
- 티켓 하나만 다르게 돌리려면 [티켓 `verify`](#verify--이-티켓만의-검증-명령)를 쓴다.
- `verify`: integration, 보고서 커밋 뒤 integration-final, 병합 뒤 main에서 돌린다. 바뀐 것이 `report.md`뿐이면 integration-final은 건너뛴다.
- `verify_retries`: 실패하면(시간 초과 포함) 그만큼 다시 돌린다. 한 번의 상한은 `verify_minutes`라 최악은 (1 + `verify_retries`) × `verify_minutes`다. 모든 검증 지점에 같이 적용된다.
- `idle_minutes`: worker가 출력 없이 시험을 돌리는 시간보다 길게 둔다.

```
[01] 검증: npm run test:unit
[01] 검증 통과 → integration 병합
■ integration 검증: npm test
■ integration-final: 보고서만 바뀜, 건너뜀
■ main 검증: npm test
```
재시도로 통과하면 실패가 아니지만 보고서 Evidence에 남는다(`report.md`의 verify 출력). 라벨은 `ticket-01`, `integration`, `integration-final`, `main` 등이다:
```
티켓 검증 명령: `npm run test:unit`

integration-final: 보고서만 바뀜, 건너뜀

flaky: main 재시도 1번 만에 통과
```
주의: 빠른 검사가 놓친 실패는 integration의 전체 `verify`에서 잡힌다. gs는 원인 티켓을 되짚거나 고치지 않으므로 재시도 없이 feature 전체가 `integration 검증 실패 → 병합 안 함`으로 끝난다. 보고서 Evidence의 "검증 실패"에 로그 경로, 실패 줄(최대 10줄), `후보 티켓(추정)`이 있다. 후보는 실패 줄에 나온 경로·이름과 티켓의 `touches`·변경 파일을 맞춰 본 것이라 틀릴 수 있다. 로그를 읽고 `/grill`로 고칠 티켓을 더해 다시 돌린다. 그래서 `verify_ticket`은 자주 깨지는 쪽을 덮는 검사로 고른다.

### 예시: 전체 시험을 프로세스로 나누기

`verify_ticket`으로 좁히면 놓친 실패가 마무리까지 간다. 시험이 파일별로 독립이면 전체를 나눠 돌리는 쪽이 먼저다. 이 레포의 spec frontmatter:
```yaml
verify: ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
```
시험 파일마다 프로세스 하나, 동시 6개다. 파일 하나라도 실패하면 `xargs`가 0 아닌 코드로 끝나 `&&` 뒤로 가지 않고 검증 실패가 된다. 이 레포에서 순차 약 11–12분이 약 4분이 됐다(`.goldstack/profile.md`의 측정, 다른 실행 없이 1회).
- **프로세스로 나눈다.** 시험이 `os.environ`·현재 디렉터리를 바꾸면 스레드로는 나눌 수 없다.
- **파일끼리 겹치는 자원이 없어야 한다.** 고정 포트, 같은 임시 경로, 공유 DB를 쓰는 시험은 먼저 분리한다. 나눠 돌린 결과를 여러 번 재 보고 쓴다.
- **가장 느린 파일이 하한이다.** 프로세스를 늘려도 그 밑으로 안 내려간다. 한 파일이 크게 차지하면 그 파일을 쪼갠다.
- **동시 worker만큼 곱해진다.** `max_workers: 3`이면 worker들의 커밋 전 검증이 겹쳐 최대 18프로세스(`-P 6` × 3)다. `-P`는 코어 수와 `max_workers`를 보고 정한다.
- 다른 도구는 같은 일을 하는 옵션을 쓴다: `pytest -n 6`(pytest-xdist), `jest --maxWorkers=6`, `go test -p 6 ./...`.

### config 키

`.goldstack/config.toml`. `gs init`이 전부 기본값으로 쓴다. 값 하나는 `gs config <섹션.키>`(`gs config git.merge_method` → `squash`, 등급표의 칸은 못 읽으니 파일을 본다). `/go` skill은 이것으로 `git.base`·`git.remote`를 읽는다. `gs go`는 시작할 때 한 번 읽는다.

| 키 | 기본 | 누가 쓰나 |
|---|---|---|
| `git.remote` | `"origin"` | `gs go`(fetch, push, PR 저장소 owner/repo), `gs doctor`(읽을 저장소), `/go`. GitHub URL이어야 한다 |
| `git.base` | `origin/HEAD`의 브랜치, 못 찾으면 `"main"`(`gs init`이 적는다) | `gs go`(PR 대상, worker·integration 출발점, 재검증), `gs doctor`(보호 규칙을 읽을 브랜치), `/go` |
| `git.merge_method` | `"merge"` | `gs go` 마무리: PR 병합·확인·revert. `merge` 또는 `squash`. `gs doctor --write`가 고친다 |
| `git.direct_push` | `true` | `gs go` 마무리: `false`면 revert·최종 보고서를 PR로. `gs doctor --write`가 고친다 |
| `git.wait_checks` | `false` | `gs go` 마무리: `true`면 CI를 기다린 뒤 병합. `gs doctor --write`가 고친다 |
| `worktree.setup` | `""` | `gs go`: worktree마다 worker·verify 전에 돌린다. 비면 안 돈다. 사람이 채운다 |
| `models.judge` | `"opus"` | 판단 모델 `claude -p --model`: 리뷰 분류(1차 재리뷰의 새 지적 포함), 보고서 요약 |
| `models.failure_summary` | `gs init` `"haiku"`, 키가 없으면 `models.judge` | 재시도 brief용 실패 요약의 `claude -p --model` |
| `models.claude_review` | `"opus"` | `tiers.claude` 표가 없을 때 claude reviewer(재리뷰 포함) `--model` |
| `models.agy` | `"gemini-4-argon-high"` | `tiers.agy` 표가 없을 때 agy worker·reviewer `--model`. `/retro`의 로그 요약은 표와 상관없이 이 값 |
| `models.codex` | `""` | `tiers.codex` 표가 없을 때 codex worker·reviewer `--model`. 비우면 codex 기본 모델 |
| `tiers.claude`·`tiers.codex`·`tiers.agy`의 `small`·`medium`·`large` | `gs init`이 쓴다, 키가 없으면 표 없음 | `"모델/effort"`(effort 생략 가능). worker·reviewer의 `--model`과 effort 인자. 값·없을 때 동작은 [`tier`](#tier--티켓-크기에-맞는-모델effort) |
| `tiers.review` | `"large"` | 첫 리뷰의 등급. 리뷰어 계열의 표가 있을 때만 |
| `tiers.rereview` | `"medium"` | 재리뷰의 등급. 리뷰어 계열의 표가 있을 때만 |
| `agy.max_calls_per_run` | `3` | `gs go`(호출 세기), `gs check`(경고). `0`이면 agy를 띄우지 않는다 |
| `timeouts.review_minutes` | `30` | 첫 리뷰의 reviewer 호출 한 번. 넘기면 기다렸다 다시 부른다(`network_wait_minutes`까지) |
| `timeouts.rereview_minutes` | `10` | 재리뷰의 reviewer 호출 한 번(리뷰어·회차마다). 넘기면 기다렸다 다시 부른다(`network_wait_minutes`까지) |
| `timeouts.judge_minutes` | `10` | 리뷰 분류·보고서 요약 호출 한 번. 넘기면 기다렸다 다시 부른다(`network_wait_minutes`까지) |
| `timeouts.summary_seconds` | `60` | 재시도 brief용 실패 요약 호출 한 번. 넘기면 기다렸다 다시 부른다(`network_wait_minutes`까지) |
| `timeouts.network_wait_minutes` | `60` | 끊김 하나의 대기 합계(분), codex `Reconnecting`을 참는 시간. 넘기면 [`중단(네트워크)`](#네트워크가-끊겼을-때). 시간 초과까지 쓴 호출 시간은 합계에 들지 않는다 |
| `timeouts.checks_minutes` | `60` | PR 하나의 CI 대기 한 번(`gs go`마다 새로 잰다). `git.wait_checks`일 때만 |
| `timeouts.checks_grace_seconds` | `60` | CI 대기에서 검사가 하나도 안 보일 때 등록을 기다리는 시간. 지나면 검사 없음으로 보고 병합을 시도한다. `0`이면 기다리지 않는다. 필수 검사 이름을 읽었으면 쓰지 않는다. `git.wait_checks`일 때만 |
| `timeouts.setup_minutes` | `15` | `worktree.setup` 한 번 |
| `notify.telegram` | `false` | `gs go`가 끝날 때 한 통, `gs check`(값이 비면 경고) |
| `goldstack.requires` | 없음(검사 안 함) | `gs check`·`gs go`: 설치한 gs가 이 최소 버전(`">=0.1"`)보다 낮으면 오류로 거부하고 `gs self-update`를 안내한다. 형식이 틀리면 config 오류 |
| `feedback.mode` | 절이 없으면 `off`, `gs init`이 만든 config는 `draft` | `off` 아무것도 안 쓴다 · `draft` 로컬 초안만 쌓는다 · `auto` GitHub issue로 보낸다. [피드백](#피드백-gs-결함을-goldstack에-알리기) |
| `feedback.detail` | `errors` | `errors`는 가린 오류 줄 최대 20줄을 보낸다. `minimal`은 오류 줄 없이 항목만 |
| `feedback.repo` | `gs init`이 `goldenyoo/goldstack`을 적는다 | issue를 올릴 저장소 |
| `feedback.max_per_day` | `5` | 하루에 새로 올리는 issue 최대 수 |

검사: 형이 틀린 값, 0 이하인 `timeouts.*`(`checks_grace_seconds`만 `0`을 허용하고 음수는 오류), 음수인 `agy.max_calls_per_run`, 빈 모델 이름(`models.codex`만 빈 값 허용), `merge`·`squash` 밖의 `git.merge_method`, 등급표의 빠진 칸·틀린 형식(공백, 슬래시 둘 이상, 없는 effort), `small`·`medium`·`large` 밖의 `tiers.review`·`rereview`는 오류, 모르는 키는 경고다. effort는 `low`·`medium`·`high`·`xhigh`·`max`이고 codex는 `none`·`minimal`도 받는다. 빠진 키도 오류지만 옛 config를 위해 `git.merge_method`·`direct_push`·`wait_checks`, `models.failure_summary`, `timeouts.checks_minutes`·`setup_minutes`·`rereview_minutes`·`checks_grace_seconds`·`network_wait_minutes`, `[worktree]`, `[agy]`, `[tiers]`는 없으면 기본값으로 읽는다.

### spec frontmatter 키

feature마다 다른 값은 config가 아니라 `.goldstack/work/<feature>/spec.md` frontmatter에 둔다. `/grill`이 적고 `gs check`·`gs go`가 읽는다. `: `나 ` # `가 든 값은 따옴표로 감싼다.

| 키 | 기본 | 누가 쓰나 |
|---|---|---|
| `feature` | 필수 | `gs check`: 디렉터리 이름과 같아야 한다 |
| `verify` | 필수 | `gs go`: integration, integration-final, 병합 뒤 base 검증. 티켓 `verify`도 `verify_ticket`도 없으면 티켓 검증과 worker brief도. 비어 있지 않은 셸 한 줄 |
| `verify_ticket` | 없음 | 티켓 `verify`가 없는 티켓의 검증과 worker brief가 `verify` 대신 이것을 쓴다. 병합 트리에서 돈다(티켓 worktree가 아니다). 비어 있지 않은 셸 한 줄 |
| `verify_retries` | `0` | 모든 검증 지점에서 실패 시 다시 돌리는 횟수. 0 이상 정수 |
| `verify_minutes` | `20` | 검증 명령 한 번의 상한(`verify`, `verify_ticket`, 티켓 `verify` 모두). 1 이상 정수 |
| `idle_minutes` | `20` | 로그 출력·새 커밋 없는 worker를 끝내는 시간. 1 이상 정수 |
| `max_workers` | `3` | 동시 worker 수. 1 이상 정수. 리뷰 중인 티켓은 자리를 차지하지 않는다(worker 최대 `max_workers` + 리뷰 중인 티켓 최대 `max_workers`) |

그 밖의 키는 경고다. 티켓 frontmatter 키는 [아래](#티켓-선택-키와-agy-한도).

### 한계

- **GitHub만.** PR·병합을 `gh`로 한다. GitHub 밖 원격은 `gs check`·`gs go`가 오류로 멈추고 `gs doctor`가 `GitHub 원격 아님`으로 알린다(범위 밖 `gitlab-support`).
- **rebase 병합 미지원.** `git.merge_method`는 `merge`·`squash`뿐이다. `rebase`는 config 오류이고, rebase만 허용하는 저장소는 `gs doctor`가 경고만 하며 PR 병합이 거부된다. 병합 커밋을 확인·revert하는 기준이 rebase에서는 성립하지 않는다.
- **승인은 사람.** gs는 PR을 승인하지 않는다. 승인에 막히면 `사람 승인 필요: <PR>`로 멈추고 알린 뒤, 승인 뒤의 `gs go`가 이어 간다. 기다려 주는 프로세스가 없으니 사람이 다시 친다.
- **CI 실패를 고치지 않는다.** 병합하지 않고 PR을 열어 둔 채 멈춘다(범위 밖 `ci-fix-tickets`).
- **보호된 main의 grill 커밋은 사람 몫이다.** `direct_push = false`는 `gs go`의 revert·보고서에만 적용된다. spec·티켓은 [PR로 먼저 올린다](#예시-보호된-main--필수-승인).
- **squash는 실행 중 main이 움직이면 멈춘다**([위](#예시-squash만-허용)).
- **필수 검사 이름을 모르면 CI 등록을 짧게만 기다린다.** 보호 규칙에서 이름을 읽지 못했는데 `timeouts.checks_grace_seconds`(기본 60초) 안에 검사가 하나도 안 보이면 검사 없음으로 보고 병합을 시도한다([위](#예시-보호된-main--필수-승인)). 필수 검사면 GitHub가 병합을 거부해 `merge_pending`으로 멈추고, 필수가 아닌 검사는 기다리지 못할 수 있다.
- **리뷰는 병합을 막지 않는다.** 병합 관문은 `verify`다. 수정은 티켓당 최대 2회이고, 그래도 남은 지적은 `미해결`로 병합된다([리뷰와 재리뷰](#리뷰와-재리뷰)). 보고서의 개수 줄을 보고 사람이 다음 티켓을 정한다.

### `gs init`이 만드는 것

`/adopt`가 대신 부르지만 직접 쳐도 된다. 레포 루트(또는 그 안 어디서든. 위로 `.git`을 찾는다)에서:
```console
$ gs init
만듦: .goldstack/config.toml
만듦: .goldstack/local.env.example
추가: .gitignore (.goldstack/local.env, .goldstack/work/*/run/)
.goldstack/config.toml을 확인하고, local.env.example을 local.env로 복사해 값을 채워라
gs doctor: you/tally (원격 origin)
…(gs doctor 표. 읽기만 한다)
```
없는 파일만 만들고, 있는 파일은 `그대로 둠: …`으로 알린다. 두 번 돌려도 같다. 커밋은 하지 않는다. 끝에 `gs doctor`가 한 번 돈다(`--write` 없이).
`config.toml`이 없으면 `gs check`·`gs go`·`gs config`·`gs doctor`는 `.goldstack/config.toml이 없다. gs init을 먼저 실행하라` 오류로 멈춘다.

**`.gitignore`** — `gs init`이 아래 두 패턴 줄을 덧붙인다(주석 줄은 설명용이고 gs init은 쓰지 않는다). 이미 있는 줄은 건드리지 않는다.
```
# 텔레그램 토큰 같은 비밀
.goldstack/local.env
# 실행 흔적: state.json, 로그, 티켓 worktree
.goldstack/work/*/run/
```
`.gitignore`의 `#`은 줄 맨 앞에서만 주석이다. 패턴 뒤에 붙이면 패턴의 일부가 되어 그 줄이 아무것도 무시하지 않는다.
`run/` 아래에는 worker worktree(`run/wt/NN`)가 생긴다. 이 줄이 없으면 `git add -A`에 worktree가 섞인다.

**텔레그램(선택)** — `cp .goldstack/local.env.example .goldstack/local.env` 뒤 값을 채운다(따옴표 없이 `KEY=value`).
```
# BotFather에서 받은 봇 토큰
TG_TOKEN=123456:ABC...
# 알림 받을 채팅 ID
TG_CHAT_ID=987654321
```
주석은 줄 맨 앞 `#`만 인정한다. 값 뒤에 붙인 `# ...`는 값의 일부가 된다.
채팅 ID를 모르면 봇에게 아무 메시지나 보낸 뒤 `https://api.telegram.org/bot<TG_TOKEN>/getUpdates`의 `chat.id`를 본다. 그리고 config에서 `telegram = true`.
gs는 이 파일만 읽는다(환경 변수는 보지 않는다). worker는 이 파일을 읽을 수 없다(차단 hook).
`gs notify <파일>`은 그 파일 내용을 같은 텔레그램으로 보낸다(3900자에서 자른다). `notify.telegram`이 꺼져 있어도 사람이 친 명령이라 보낸다. `gs notify --check`는 토큰만 확인한다(`getMe`). 성공이면 종료 0, 값이 없거나 실패하면 이유 한 줄과 종료 1이다. `/overnight`이 아침 보고를 보낼 때 쓴다.

**환경 확인** — `gs check <feature>`는 spec·티켓과 함께 환경도 본다. feature가 아직 없어도 `gs check x`를 돌리면("feature 디렉터리가 없다" 오류는 무시) `git`·`gh`·원격·텔레그램 문제가 먼저 보인다. 나오는 줄:
- ``필요한 CLI `codex`가 PATH에 없다``(오류): `git`, `gh`, `claude`(판단 모델: 실패 요약·리뷰 분류·보고서)와 범위 안 티켓의 `model`·`reviewer`가 쓰는 CLI가 있어야 한다.
- ``원격 `origin`의 URL `…`은 GitHub 저장소 형식이 아니다``(오류): gs는 `git.remote`의 URL에서 owner/repo를 풀어 모든 `gh pr` 명령에 `--repo`로 넘긴다. GitHub 밖 원격에서는 `gs go`도 시작하지 않는다.
- `notify.telegram이 켜져 있지만 .goldstack/local.env에 TG_TOKEN이 없다`(경고).

## 새 feature

base 브랜치에서 Claude Code를 연다. 순서는 `/grill` → `/go`이고, 둘 다 사용자가 부르는 skill이다.

**`/grill csv-export`** — 인자가 공백 없는 한 단어면 feature 이름이다. 공백이 있으면(`/grill CSV로 내보내기 추가`) 이름이 아니라 요청으로 읽고, 라운드 1에서 feature 이름을 제안한다. 확정 전에는 `.goldstack/work/<이름>/` 경로를 만들지 않는다.
1. Claude가 `.goldstack/profile.md`(있으면 가장 먼저, 없고 처음 쓰는 레포면 `/adopt`를 권한다), 레포·문서·도구 버전과 `gs backlog`(열린 아이디어, 범위 밖의 다시 볼 조건)를 직접 읽고 돌려 본 것을 spec "환경 사실"에 날짜와 함께 적는다. 찾을 수 있는 것은 묻지 않는다.
2. 사람이 정할 결정을 라운드마다 한 메시지에 번호 붙여 묻는다. 질문마다 선택지와 그 선택지의 구체 예시(실제로 보일 명령·파일·출력), 추천과 이유가 붙고, 끝에 `yes = 추천 전부 수락. 바꿀 것만 번호로`. 열린 아이디어가 있으면 라운드 1의 첫 질문은 "이번 feature에 넣을 후보"다(아래 [아이디어 흐름](#아이디어-흐름)).
3. 답하는 법: `yes`(추천 전부), `2. B`(2번만 B), `3. 왜 B가 아니야?`(되묻기: 답을 듣고 같은 라운드를 다시 확정한다). 짧은 답이면 Claude가 "이렇게 읽었다"를 답마다 한 줄로 보이니, 어긋나면 그때 고친다.
4. 답은 바로 `.goldstack/work/csv-export/spec.md`의 "결정" 표와 "grill 기록"에 적힌다. `verify` 같은 frontmatter 값이면 frontmatter도 고친다(gs는 표가 아니라 frontmatter를 읽는다).
5. 마지막 라운드는 티켓 분해다: 티켓 표(blocked_by, wave, 구현 모델, 리뷰 계열 — 서로 다른 계열이어야 한다, 건드릴 파일 `touches`)와 범위 밖 목록. 확정되면 `touches`가 티켓 frontmatter에 들어간다(아래 [티켓 선택 키](#티켓-선택-키와-agy-한도)).
6. 확정되면 `tickets/NN-slug.md`, `.goldstack/out-of-scope/<slug>.md`를 쓰고 `gs check csv-export`가 오류·경고 없이 통과할 때까지 고친다. 라운드 1에서 고른 아이디어 파일은 `status: "taken"`, `feature: "csv-export"`로 바꾼다. 그 뒤 `.goldstack/work/csv-export`, `.goldstack/out-of-scope`, `.goldstack/ideas`, `.goldstack/profile.md`만 커밋한다(없는 디렉터리는 뺀다). push는 하지 않는다.

```console
$ gs check csv-export
csv-export: 티켓 3장, 오류 0, 경고 0
순서: 01 02 03
지금 시작 가능: 01
실측(지난 실행): small 9분(14) · medium 38분(14) · large 69분(13)
공통 모델: 판단 claude opus · 실패 요약 claude haiku
01 small 구현 codex gpt-6-luna/medium · 수정 codex gpt-6-luna/medium · 수리 codex gpt-6-luna/medium · 첫 리뷰 claude opus/xhigh · 재리뷰 claude sonnet/high
02 medium 구현 claude sonnet/high · 수정 claude sonnet/high · 수리 claude sonnet/high · 첫 리뷰 codex gpt-6.1-sol/high · 재리뷰 codex gpt-6.1-sol/medium
03 large 구현 claude opus/xhigh · 수정 claude opus/xhigh · 수리 claude opus/xhigh · 첫 리뷰 codex gpt-6.1-sol/high + agy gemini-4-argon-high · 재리뷰 codex gpt-6.1-sol/medium + agy gemini-4-argon-medium
```
오류가 없으면 `gs check`는 `순서`와 `지금 시작 가능` 뒤에 세 가지를 더 보인다.
- `실측(지난 실행): small 9분(14) · …` — 같은 레포 다른 feature의 지난 `run/state.json`에서 병합된 티켓의 등급별 소요 중앙값(괄호는 표본 수)이다. 소요는 티켓의 첫 단계 시작부터 끝까지이고 재시도를 포함한다. 등급이 없는 옛 티켓과 읽을 수 없는 state는 건너뛴다. 표본이 없으면 `실측 기록 없음`이다. `/grill`은 티켓 표의 예상에 그 티켓 tier의 중앙값을 쓰고, 값이 없으면 `–`로 둔다.
- `공통 모델: 판단 claude … · 실패 요약 claude …` — 지적 분류·보고서 Summary에 쓰는 `models.judge`와 실패 요약에 쓰는 `models.failure_summary`다.
- 티켓마다 한 줄 — 등급과 구현·수정·수리·첫 리뷰·재리뷰의 계열 모델/effort다(두 번째 리뷰어가 있으면 `+`로 잇는다). 실행이 쓰는 선택 함수와 같은 값이고, 재시도·승급은 미리 알 수 없어 넣지 않는다. 그 계열의 `[tiers]` 표가 없으면 모델은 `CLI 기본값`이다. `/grill`은 이 값을 spec의 티켓 표(구현·수정·수리·첫 리뷰·재리뷰 열)와 그 아래 `계열:`(고른 이유)·`공통 모델:` 줄에 그대로 옮긴다.

파일 형식은 [skills/grill/templates/](../skills/grill/templates/). 중간에 세션이 끊겨도 `/grill csv-export`를 다시 부르면 spec의 기록에서 이어 간다.

**`/go csv-export`**
1. `gs check` — 오류가 있으면 보이고 "`/grill csv-export`로 고친다"며 끝낸다.
2. 현재 브랜치가 base인지 보고, grill 결과(`.goldstack/work/csv-export`, `.goldstack/out-of-scope`, `.goldstack/ideas`, `.goldstack/profile.md`)가 아직 커밋 안 됐으면 그 경로만 커밋하고, base가 원격보다 앞서기만 하면 `git push origin main`(force 아님). 뒤처졌거나 갈라졌으면 말하고 끝낸다. worker는 `origin/main` 위에서 일하므로 spec·티켓이 거기 있어야 한다. 보호된 main이면 이 push가 막히니 [먼저 PR로 올린다](#예시-보호된-main--필수-승인).
3. `gs go csv-export`를 백그라운드로 돌리고 끝날 때까지 기다린다. 사람에게 묻지 않는다.
4. 결과: `report.md`의 세 줄 요약과 PR 링크(README "5분 따라 하기" 3).
5. 회고: 끝난 feature마다 subagent가 `/retro`와 같은 방식으로 실행을 읽어 고칠 후보만 번호 붙여 돌려준다. 세션이 후보를 보이고, 사람이 고른 것만 아이디어 파일로 쓴다. 고르지 않으면 아무것도 쓰지 않는다. subagent가 실패하면 다시 부르지 않고 `/retro csv-export`로 따로 돌리라고만 말한다([아이디어 흐름](#아이디어-흐름)). 1~4단계는 사람에게 묻지 않고, 묻는 건 끝난 뒤인 이 단계뿐이다. `/overnight`은 사람이 없어 이 단계를 돌리지 않고 아침 보고에 `회고: /retro csv-export` 한 줄만 적는다.

일부 티켓만 먼저 돌려 볼 때는 터미널에서 `gs check csv-export --only 01,02`로 범위를 보고 `gs go csv-export --only 01,02`. 범위 밖 의존은 끝났다고 본다. **`--only`는 병합하지 않고 멈춘다.** 티켓을 돌려 integration에 병합·검증까지만 하고, 범위가 모든 티켓이어도 PR을 만들지 않고 base를 바꾸지 않으며 최종 보고서도 쓰지 않는다. 끝에 `■ --only 범위만 돌았다: 병합하지 않음 → 이어서 gs go csv-export`가 나온다(범위 안 티켓이 모두 병합됐으면 종료 0, 아니면 1). base 병합은 옵션 없는 `gs go csv-export`가 한다. 이미 병합된 티켓은 다시 돌지 않고 남은 티켓만 돌린 뒤 PR을 병합하며, 보고서 표에 `--only`로 돌린 티켓도 나온다. 반쪽 기능이 main에 들어가지 않는다.

## 티켓 선택 키와 agy 한도

티켓 frontmatter 키([템플릿](../skills/grill/templates/ticket.md)). 선택 키가 없어도 옛 티켓은 그대로 통과한다. 그 밖의 키는 `gs check` 경고다.

| 키 | 기본 | 누가 쓰나 |
|---|---|---|
| `id`, `title`, `blocked_by`, `model`, `reviewer` | 필수 | `gs check`, `gs go`. `model`·`reviewer`는 `claude`·`codex`·`agy` 중 서로 다른 계열 |
| `tier` | `medium` | worker의 모델·effort를 등급표에서 고른다. `small`·`medium`·`large` |
| `verify` | spec `verify_ticket` → spec `verify` | 이 티켓의 worker brief와 병합 트리 검증. 비어 있지 않은 셸 한 줄 |
| `touches` | `[]` | `gs check`의 겹침 경고 |
| `second_reviewer` | 없음 | 두 번째 리뷰어. `model`·`reviewer`와 다른 계열 |

### `tier` — 티켓 크기에 맞는 모델·effort
`/grill`이 티켓 표에 등급과 이유 한 줄을 적어 확인받는다. 문서는 `small`, 재개 흐름처럼 틀리면 비싼 티켓은 `large`다. 실제 이름은 티켓이 아니라 config에 둔다. `gs init` 새 config의 값:
```toml
[tiers]
review = "large"      # 첫 리뷰
rereview = "medium"   # 재리뷰

[tiers.claude]
small = "sonnet/medium"
medium = "sonnet/high"
large = "opus/xhigh"

[tiers.codex]
small = "gpt-6-luna/medium"
medium = "gpt-6.1-sol/medium"
large = "gpt-6.1-sol/high"

[tiers.agy]
small = "gemini-3.8-flash-medium"   # agy는 모델 이름에 effort가 들어 있어 뒤를 생략했다
medium = "gemini-4-argon-medium"
large = "gemini-4-argon-high"
```
모델 이름은 계정·CLI 버전에 달렸다(`agy models`, codex 모델 목록). 쓰는 CLI에 있는 이름으로 고친다. 실제 인자는 `--model <모델>`에 claude·agy면 `--effort <effort>`, codex면 `-c model_reasoning_effort=<effort>`다.
- **worker**: 티켓 `tier`, 없으면 `medium`. 수정 worker도 그 시도의 등급이다.
- **실패 재시도**: 한 단계 올린다(`small`→`medium`→`large`, `large`는 그대로). 네트워크로 끊겨 다시 띄울 때는 올리지 않는다.
- **리뷰어**: 티켓 `tier`와 상관없이 첫 리뷰 `tiers.review`, 재리뷰 `tiers.rereview`다.
- **표가 없는 계열**: `tier`와 승급을 무시하고 옛 선택으로 돈다: claude worker는 CLI 기본값, claude reviewer는 `models.claude_review`, codex·agy는 `models.codex`·`models.agy`, effort는 CLI 기본값. 그 계열이 범위 안 티켓의 `model`이면 `gs check`가 경고한다:
  ```
  경고: .goldstack/config.toml: `tiers.codex` 표가 없다. 모델·effort가 사용자 설정을 따른다
  ```
실제로 쓴 모델·effort는 보고서 Evidence의 "실행 측정"에 시도·리뷰마다 남는다. 빈 값은 `CLI 기본값`으로 보인다.

### `verify` — 이 티켓만의 검증 명령
worker brief와 gs의 티켓 검증이 이 명령을 쓴다. 우선순위는 티켓 `verify` → spec `verify_ticket` → spec `verify`이고, 어느 것이든 [병합 트리](#예시-느린-시험verify_ticket-verify_retries)에서 돈다. integration·main 마무리는 늘 spec `verify`다.
```yaml
---
id: "05"
title: "사용법 문서"
blocked_by: []
touches: ["README.md", "docs/**"]
tier: small
verify: "npm run lint:docs"
model: claude
reviewer: codex
---
```
문서·설정 티켓만 좁힌다. 코드 티켓은 키를 비워 전체 검증을 받는다. 단 spec에 `verify_ticket`이 있으면 코드 티켓도 그 값을 물려받으니, 그 티켓이 전체 검증을 받아야 하면 spec `verify`를 그대로 적는다. 다른 명령을 쓴 티켓은 보고서 verify 출력에 `티켓 검증 명령(05): …`로 보인다.

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
두 리뷰는 동시에 돌고, 지적을 합쳐 수정 worker를 하나만 띄운다. 그 뒤 재리뷰는 지적을 낸 리뷰어가 각자 자기 지적을 확인한다(둘 다 냈으면 동시에, [리뷰와 재리뷰](#리뷰와-재리뷰)). 한쪽이 실패해도 다른 쪽 결과로 간다(시간 초과·일시 오류는 기다렸다 다시 부른다). `gs go` 출력:
```
[04] 리뷰: codex+agy
[04] 리뷰 끝(codex): 지적 2개(fix 1, report 1)
[04] 리뷰 끝(agy): 지적 1개(fix 1, report 0)
```
보고서 "리뷰 지적"에는 리뷰마다 계열이 붙는다: `- 04 리뷰(codex) [medium] src/tally/cleanup.py:12: … — 상태: 미해결`, `- 04 리뷰(agy) [high] … — 상태: 수정됨(재리뷰 확인)`. 원본은 `run/04/<시도>/review/`(첫 리뷰), `run/04/<시도>/review-agy/`(두 번째 리뷰), `run/04/<시도>/rereview1-codex/`(재리뷰). 각 디렉터리에는 리뷰어 stdout 원본이 파싱 전 그대로 `reviewer.stdout`으로 남는다(재호출은 `reviewer.2.stdout`처럼 번호가 붙어 앞 것을 덮지 않는다).

### `[agy] max_calls_per_run` — Gemini 호출 상한
```toml
[agy]
max_calls_per_run = 3
```
`gs go` 한 번(feature 하나)에서 gs가 띄우는 agy 호출 수의 상한이다. 1회는 agy worker 한 번(재시도·수정 worker·2차 수정 worker·끊겨서 다시 띄운 worker도 각각 1회), agy 리뷰 한 번, agy 재리뷰 한 번(회차마다, 끊겨서 다시 부른 호출도) 중 하나다. 실행마다 0부터 센다(`gs go a b`면 feature마다 따로). 섹션이 없으면 3, `0`이면 agy를 띄우지 않는다. `/retro`의 agy 요약과 `gs check`의 agy 차단 장치 확인(`agy -p /hooks`, 모델 호출 없음)은 세지 않는다.
- **`gs check`**: 범위 안 티켓의 `model`·`reviewer`·`second_reviewer` 중 agy인 것을 센다(티켓마다 첫 호출만. 재시도·수정·재리뷰는 미리 세지 않는다). 상한을 넘으면 경고:
  ```
  경고: 범위 안 agy 배정 4회가 상한 agy.max_calls_per_run=3회를 넘는다
  ```
- **실행 중 상한에 닿으면** 멈추지 않고 이어 간다. agy 리뷰는 띄우지 않고 `건너뜀(한도)`으로 적는다(`[04] 리뷰 끝(agy): 지적 0개(fix 0, report 0) — 건너뜀(한도): 이번 실행의 agy 호출이 상한 3/3에 닿았다`. 리뷰가 하나뿐이면 `(agy)` 없이 `[04] 리뷰 끝: …`). 다른 리뷰가 있으면 그것으로, 없으면 verify만으로 병합한다. agy 구현 티켓은 worker를 띄우지 않고 재시도 없이 실패한다(이유 `agy 한도: …`, 아래 [자주 보는 이유](#실패했을-때)). agy 재리뷰는 띄우지 않고 그 지적을 `확인 못 함(한도)`로 적는다. agy 수정 worker는 띄우지 않고 지금 브랜치의 구현을 병합·검증한다. 그 지적은 `수정 못 함(한도)`이고, 1차 재리뷰가 안 고쳐졌다고 본 지적은 `미해결`이다.
- **보고서**: Evidence 끝에 `agy 사용: 2/3`(이번 실행 호출 수/상한).

언제 바꾸나: `second_reviewer: agy` 티켓이 상한보다 많은 feature면 그 수만큼 올린다(경고가 사라진다). 경고가 없어도 재리뷰까지 세면 더 쓸 수 있다: agy가 지적을 내면 그 티켓에서 최대 3회(리뷰 1 + 재리뷰 2), agy 구현 티켓은 재시도 없이 최대 3회(worker 1 + 수정 2)다. Gemini 사용량이 빠듯한 날은 낮추거나 `0`으로 둔다. `0`인데 agy 배정이 있으면 `gs check`가 같은 경고를 낸다.

## 리뷰와 재리뷰

worker가 끝나면 병합 전에 다른 계열 리뷰어가 티켓 diff를 보고, 판단 모델이 지적마다 `fix`(고친다)·`report`(보고만)를 정한다. 리뷰어는 전체 시험 대신 지적을 확인할 좁은 재현만 돌린다. `fix`가 있으면 이렇게 간다. `verify`는 마지막에 한 번 돈다.

1. **수정** — 같은 구현 모델의 수정 worker가 같은 브랜치에서 `fix` 지적을 고치고 커밋한다.
2. **재리뷰** — 지적을 낸 리뷰어가 수정 커밋의 diff만 다시 본다: 지적마다 고쳐졌는가(근거와 함께), 수정이 새로 만든 문제가 있는가. `second_reviewer`까지 둘 다 지적했으면 동시에 각자 자기 지적을, 한쪽만 냈으면 그쪽만 본다. 한 번의 상한은 `timeouts.rereview_minutes`(기본 10분)다.
3. **2차 수정** — 아직 안 고쳐진 지적이 있거나, 새 문제 중 판단 모델이 `fix`로 본 것이 있으면 한 번 더 고친다. 둘 다 없으면 바로 5로 간다.
4. **2차 재리뷰** — 2차 수정이 받은 지적과 함께, 앞서 `수정됨`이던 지적도 최종 커밋에서 다시 확인한다(그 지적을 낸 리뷰어도 부른다). 2차 수정이 1차 수정을 되돌렸으면 그 지적은 `미해결`이 되고, 최종 커밋을 보지 못하면 `확인 못 함`이 된다. 2차 수정이 없던 티켓은 이 재확인이 없고 호출 수도 그대로다. 여기서 나온 새 문제는 고치지 않고 `보고만`으로 남긴다.
5. **병합** — 더 고치지 않는다(수정은 티켓당 최대 2회). 최신 integration을 합쳐 티켓 검증을 통과하면 남은 지적이 있어도 병합한다.

수정 worker가 실패하면(종료 코드, 멈춤, 커밋 없음) 그 수정만 버리고 재리뷰를 건너뛰어 병합·검증으로 간다. 2차 수정이 실패해도 1차 수정은 남는다. 어느 경우든 티켓 실패로 세지 않는다.

리뷰어는 병합될 커밋만 읽는다. worker가 미커밋 변경을 남겼으면 그 커밋의 임시 worktree에서 리뷰하고, 남은 변경은 티켓 worktree에 그대로 둔다. 리뷰하는 동안 티켓 브랜치에 커밋이 더 생기면 한 번 다시 리뷰한다(`[04] 병합 전 대조: …`). catch-up으로 합친 최신 integration은 worker 변경이 아니라 세지 않는다.

**리뷰 중에도 일은 이어진다** — 리뷰·판단·재리뷰는 루프 밖 스레드에서 돈다. 한 티켓의 리뷰가 도는 동안 다른 worker가 끝나면 바로 처리되고 준비된 티켓이 시작된다. 병합과 검증은 여전히 한 번에 하나라서, 두 티켓의 리뷰가 함께 끝나도 차례로 병합된다. 리뷰 중인 티켓은 `max_workers` 자리를 차지하지 않는다: worker는 최대 `max_workers`개, 리뷰 중인 티켓도 최대 `max_workers`개다. 수정 worker는 worker 자리를 쓰고, 자리가 없으면 기다린다. `gs status`와 진행 바는 리뷰 중인 티켓을 그대로 `04 리뷰 중(codex)`로 보인다. `gs go`가 루프를 떠나면(`중단(네트워크)`, Ctrl-C, 뜻밖의 오류) 돌던 리뷰어를 끝내고, 다음 `gs go`가 끝나지 않은 리뷰를 처음부터 다시 한다.

**sandbox에서 못 도는 검증** — codex worker는 네트워크가 꺼진 sandbox에서 돌아 `uv build`처럼 네트워크가 필요한 단계를 못 돌릴 수 있다. 지시문이 worker에게 그 단계와 이유를 마지막 메시지에 적고 변경을 커밋하라고 한다(다른 실패는 지금처럼 고친다). gs가 커밋된 내용을 sandbox 밖 병합 트리에서 다시 검증한다. 리뷰어는 네트워크가 필요한 단계를 worker가 못 돌린 것만으로는 지적하지 않고, 다른 실패를 네트워크 탓으로 돌린 것은 지적한다. 새 config 키는 없다.

리뷰어·판단 모델 호출이 끊기거나 시간을 넘기면 실패가 아니다: 기다렸다 다시 부르고, 상한을 넘기면 [`중단(네트워크)`](#네트워크가-끊겼을-때)로 멈춘다. 끊겼다는 이유로 리뷰 없이 병합하지 않는다.

```
[04] 리뷰: codex+agy
[04] 리뷰 끝(codex): 지적 3개(fix 2, report 1)
[04] 리뷰 끝(agy): 지적 1개(fix 1, report 0)
[04] 수정 worker 시작: 지적 3개 (claude, pid 54959, 로그 …/run/04/1/fix/worker.log)
[04] 수정 worker 끝: 종료 코드 0, 새 커밋 1
[04] 수정 커밋 1개(fix 지적 codex-1, codex-2, agy-1): 재리뷰로 확인한다
[04] 재리뷰 1차: codex+agy
[04] 재리뷰 1차: resolved 1 · unresolved 1 · unchecked 0 · 새 지적 1 (codex)
[04] 재리뷰 1차: resolved 1 · unresolved 0 · unchecked 0 · 새 지적 0 (agy)
[04] 2차 수정 worker 시작: 지적 2개 (claude, pid 55043, 로그 …/run/04/1/fix2/worker.log)
```
진행 바에는 `04 재리뷰 중(codex+agy)`, `04 수정 2 중(claude)`로 보인다.

**보고서의 지적 상태** — Summary의 마무리 상태 줄 바로 아래에 상태별 개수가 한 줄 붙는다(0개인 상태는 빠지고, 지적이 없으면 줄이 없다). Evidence의 "리뷰 지적"에는 지적마다 상태가 붙는다:
```
마무리: verified · PR https://github.com/you/tally/pull/7 병합 · main 검증 통과
리뷰 지적: 수정됨 1 · 미해결 1 · 보고만 1 · 수정 못 함 1 · 확인 못 함 1
```
```
- 04 리뷰(codex) [medium] src/tally/cleanup.py:12: 지우기 전에 경로를 확인하지 않는다 — 상태: 미해결
  근거: …; 판단: …; 재리뷰 근거: 12줄에 검사가 아직 없다
```

| 상태 | 뜻 | 사람이 볼 것 |
|---|---|---|
| `수정됨(재리뷰 확인)` | 지적을 낸 리뷰어가 수정 커밋에서 근거를 대고 고쳐졌다고 확인했다 | 없다. 믿기 어려우면 `재리뷰 근거`만 읽는다 |
| `미해결` | 리뷰어가 아직 안 고쳐졌다고 봤다. 고치지 못한 채 병합됐다 | **가장 먼저 본다.** `재리뷰 근거`를 읽고 맞으면 `/grill`로 고칠 티켓을 더한다 |
| `보고만` | 고치지 않기로 했다: 판단 모델이 `report`로 봤거나(근거 없음, 범위 밖 등) 2차 재리뷰의 새 문제다 | `판단`을 읽고 동의하는지 본다. 2차 재리뷰의 새 문제는 판단 모델이 보지 않았으니 지적을 직접 읽는다. high·medium은 아이디어 파일로도 남는다(아래) |
| `수정 못 함(<이유>)` | 고칠 지적인데 수정이 들어가지 않았다. 이유: `한도`(agy 상한), `띄우지 못함: …`, `수정 worker 실패: …` | 지적이 코드에 그대로 있다고 보고 읽는다. `수정 worker 실패: 커밋 없음`이면 worker가 지적을 틀렸다고 봤을 수 있으니 `run/<NN>/<시도>/fix/worker.log`의 마지막 메시지를 본다. 한도면 `agy.max_calls_per_run`을 올린다 |
| `확인 못 함(<이유>)` | 수정 커밋은 들어갔지만 고쳐졌는지 모른다. 이유: `한도`, `재리뷰 실패`(답 형식 오류, 판정·근거 없음 등). 옛 실행에는 `시간 초과`도 있다 | 지적과 수정 커밋을 직접 대조한다. 로그는 `run/<NN>/<시도>/rereview<회차>-<계열>/reviewer.log` |

**보고만 지적은 아이디어 파일로 남는다** — 상태가 `보고만`인 high·medium 지적마다 `.goldstack/ideas/<feature>-<티켓>-<번호>.md`가 하나씩 생기고 보고서 커밋에 함께 들어가 main에 올라간다. 다른 머신에서도 `gs backlog`에 열린 아이디어(`source: <feature> 리뷰 <티켓>`)로 보이고 다음 `/grill`의 후보가 된다. low는 보고서에만 남는다. 이미 있는 파일은 다시 쓰지 않으므로 재개해도 두 번 생기지 않고, `taken`·`dropped`와 직접 고친 내용이 남는다. 필요 없으면 지우지 말고 `status: "dropped"`로 둔다. 파일을 쓰지 못해도 마무리 결과는 바뀌지 않고 경고만 남는다.

`수정됨`이 아닌 넷을 다 합친 수가 `■ 보고서: … · 남은 리뷰 지적 N`과 텔레그램의 `남은 지적 N`이다(`보고만`도 센다). 이 기능이 생기기 전에 돈 실행의 state를 읽으면 `확인 못 함(재리뷰 없음)`, `수정 못 함(수정 버림)`, `수정 못 함(수정 기록 없음)`으로 보일 수 있다.

### 검증 실패 수리

티켓 검증이 실패하면(검증 시간 초과는 제외, 수리 없이 바로 아래 재시도로 간다) 시도 하나에 한 번, 새 worktree로 처음부터 다시 하기 전에 **수리 worker**가 같은 브랜치·worktree에서 돈다. 구현 모델이 그대로이고, brief에 실패한 `verify.log` 경로만 더해 그 실패의 원인만 고치게 한다. 출력은 `[03] 검증 실패… → 새 시도 대신 같은 브랜치에서 수리한다`, `[03] 수리 worker 시작`이다.
- 커밋을 남기면 구현과 다른 계열 리뷰어가 `tiers.rereview` 등급으로 수리 커밋의 diff만 본다. 지적은 보고서에만 남고 고치지 않는다. 그 뒤 gs가 다시 병합·검증한다.
- 커밋이 없으면(불안정한 시험이라 고칠 것이 없다고 본 경우), worker가 실패했으면, 띄우지 못했으면 재리뷰 없이 바로 다시 검증한다.
- 다시 검증이 통과하면 병합한다. 또 실패하면 그 시도가 실패로 끝나고, 이 시도는 지금처럼 다음 등급의 새 worktree에서 처음부터 다시 한다(수리는 새 시도에서 한 번 더 돈다).
- 수리 worker와 [수정 worker](#리뷰와-재리뷰)의 brief는 전체 검증 대신 고친 곳에 닿는 좁은 시험만 시킨다. 전체 검증은 gs가 병합 트리에서 하기 때문이다. 첫 구현 worker는 그대로 전체 검증을 한 번 돌린다.
- 보고서 티켓별 결과의 이유 칸에 `수리: 시도 1 커밋 1개 → 다시 검증 통과` 같은 줄이 붙는다. gs가 죽거나 끊겨도 다음 `gs go`가 수리를 같은 worktree에서 잇는다.

## 실행 중 보기

**진행 바** — 같은 레포에서 연 Claude Code 세션이면 어느 세션이든(레포 하위 디렉터리에서 연 세션도) 프롬프트 위에 한 줄이 뜬다(1초마다 갱신).
```
▓▓▓░░░░░ csv-export 1/3 · 02 리뷰 중(codex) · 03 worker 중(claude) · 12분 · 약 18분 남음
```
- `1/3`: 끝난 티켓(병합·실패·건너뜀)/전체. 막대 8칸이 그 비율이다.
- `02 리뷰 중(codex)`: 돌고 있는 티켓마다 단계(준비, worker, 리뷰, 수정, 재리뷰, 수정 2, 검증, 마무리)와 그 단계의 모델(`03 재리뷰 중(codex+agy)`). feature 전체 마무리(보고서·PR·main 검증) 중이면 `마무리 중(claude)`, CI를 기다리면 `CI 대기 중`, integration이나 base worktree를 준비하면 `준비 중`.
- `네트워크 대기(2회, 3분 뒤)`: 끊겨서 기다리는 중이고, 두 번째 대기이며 3분 뒤 다시 부른다. `네트워크 회복 확인(2회)`는 다시 띄운 worker가 일시 오류 없이 도는지 보는 중이다. 둘 다 그동안 새 worker·리뷰를 시작하지 않는다([네트워크가 끊겼을 때](#네트워크가-끊겼을-때)).
- `12분`: 이번 실행의 경과. `약 18분 남음`: 남은 티켓을 의존과 `max_workers`대로 자리에 넣어 본 일정의 길이에 마무리 시간을 더한 값이다. 티켓 하나의 예상 소요는 이번 실행에서 끝난 티켓의 평균이고(등급별 평균은 쓰지 않는다), 돌고 있는 티켓은 예상에서 이미 쓴 시간을 뺀다(예상을 넘겼으면 1분으로 센다). 직렬로 이어진 티켓은 자리가 남아도 나뉘지 않는다. 마무리 시간은 이 레포의 다른 feature 실행에서 끝까지 마친 것(`verified`·`reverted`)의 마지막 티켓 종료부터 실행 종료까지 중앙값이다. 재시도와 수정은 예측하지 않으니 어려운 실행은 실제보다 짧게 말할 수 있다.
- 마무리 시간 기록이 없으면 티켓 일정만 센 값에 `+ 마무리`를 붙인다(`약 18분 남음 + 마무리`). 티켓이 모두 끝나 마무리(보고서·PR·main 검증·CI 대기) 중이면 기록이 있고 어림이 남았을 때만 `약 4분 남음`, 아니면 `마무리 중`이다. `약 0분 남음`은 나오지 않는다.
- 이번 실행에서 끝난 티켓이 아직 없으면 이 레포의 **다른 feature** 실행 기록(`.goldstack/work/*/run/state.json`)에서 병합된 티켓의 소요 중앙값으로 처음부터 예측하고, 그 사실을 꼬리표로 단다:
  ```
  ░░░░░░░░ csv-import 0/4 · 01 worker 중(codex) · 02 worker 중(claude) · 3분 · 약 26분 남음(이전 실행 기준)
  ```
  `(이전 실행 기준)` = "이번 feature의 티켓은 아직 하나도 안 끝났고, 지난 feature들의 티켓 크기로 어림했다"는 뜻이다(일정과 마무리 계산은 같다). 티켓 크기가 feature마다 다르니 거친 값으로 본다. 이번 실행에서 티켓 하나가 끝나면(병합·실패) 꼬리표가 빠지고 이번 실행 평균으로 바뀐다. `run/`은 gitignore라 기록은 실행한 머신에만 있다. 다른 feature 기록도 없으면(이 레포의 첫 feature, 새 머신) `남은 시간 계산 중`.
- `gs go`는 worker를 기다리는 동안 상태가 그대로여도 60초마다 state.json을 다시 써서(heartbeat) worker가 오래 돌아도 바가 남는다. 실행이 끝나거나 state.json이 10분 넘게 안 바뀌면 사라진다. 리뷰·재리뷰는 루프 밖 스레드에서 돌아 그동안에도 heartbeat가 계속된다. 검증·병합·마무리는 `gs go`가 직접 기다리느라 heartbeat가 멈추므로, 10분 넘는 검증(기본 20분) 중에는 정상 실행이어도 바가 사라졌다가 그 단계가 끝나면 돌아온다. 죽었는지는 `gs status <feature>`의 `실행 중(pid …)`/`중단됨`으로 본다. 안 보이면 [README](../README.md#설치) 5.

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
03의 시도 2는 첫 시도가 실패해 재시도 중이라는 뜻이다(실패 이유는 끝난 시도에만 보인다). `gs status`만 치면 지금 돌고 있는 feature를 모두 보이고, 없으면 지난 실행 기록이 있는 feature 이름을 알려 준다. 첫 줄이 `중단됨(…)`이면 `gs go`가 끝을 남기지 않고 죽은 것이고, `중단(네트워크)(…) · 다음 gs go가 이어 간다`면 대기 상한을 넘겨 스스로 멈춘 것이다. 둘 다 다시 `gs go`를 돌리면 이어 간다.

**worker 화면과 로그** — herdr 안에서 돌렸으면 지금 workspace의 탭 `gs:csv-export`에 worker마다 pane이 열린다. 성공한 worker의 pane은 닫히고, 실패한 pane은 들여다볼 수 있게 남는다.
herdr 밖이면 화면 없이 돌고, 로그는 `.goldstack/work/csv-export/run/<티켓>/<시도>/worker.log`에 쌓인다. `gs go` 자신의 출력(`[02] 리뷰: codex`, `[02] 검증 통과 → integration 병합` 같은 줄)은 `/go`가 띄운 백그라운드 출력이다.

## 실패했을 때

**보고서 읽기** — `.goldstack/work/csv-export/report.md`. gs가 integration 브랜치에 커밋하고 PR 본문으로도 쓴다. 마무리가 `verified`(main 검증 통과)나 `reverted`(main 검증 실패로 revert)로 끝나면 main 검증 결과까지 담긴 최종판을 커밋 `gs: csv-export 최종 보고서(병합 후)` 하나로 main에도 push한다(`git.direct_push = false`면 [PR로 올린다](#예시-보호된-main--필수-승인)). 그러니 `git pull` 뒤 작업 트리의 report.md가 최종판이다. 그 push가 두 번 거부되면 `■ 경고: 최종 보고서를 main에 push하지 못했다…`만 남고(결과·종료 코드는 그대로), main에는 병합 직전 판이 남는다. 최종판은 PR 본문에 있고(gs가 같은 내용으로 갱신한다), 로컬에서는 state에 남은 커밋으로 본다. `verified`면 [자동 정리](#끝난-feature-치우기gs-clean)가 integration 브랜치를 이미 지웠으므로 브랜치 이름으로는 못 찾는다:
```console
$ head=$(jq -r .finish.head .goldstack/work/csv-export/run/state.json)
$ git show "$head:.goldstack/work/csv-export/report.md"
```
`finish.head`는 최종 보고서를 커밋한 integration의 끝이다. 브랜치가 지워진 뒤에는 어디에도 닿지 않는 커밋이라 `git gc`가 지우기(기본 2주) 전까지만 보인다. `reverted`면 integration이 남아 있으니 `git show gs/csv-export/integration:.goldstack/work/csv-export/report.md`도 된다.

| 절 | 볼 것 |
|---|---|
| Summary | 판단 모델이 쓴 짧은 요약: 변경의 의미, 남은 위험. 판단이지 증거가 아니다. 병합 여부는 쓰지 않는다 |
| `문서 미반영: <티켓>`(있을 때만, 제목 바로 아래) | 코드 티켓이 병합됐는데 `touches`에 `docs/`나 `CHANGELOG.md`가 든 티켓이 `failed`·`skipped`로 남았다는 표시다. 문서 티켓마다 한 줄이다. 코드만 main에 들어가고 문서는 빠졌으니 그 티켓을 다시 돌리거나 직접 문서를 고친다. 실패한 티켓을 되돌려 다시 돌려도 이 줄은 마무리가 끝날 때까지 남는다 |
| 마무리 상태 줄(Summary 바로 아래) | gs가 state에서 쓴 한 줄. 예 `마무리: verified · PR https://github.com/you/tally/pull/7 병합 · main 검증 통과`, `마무리: reverted · main 검증 실패 → revert 1a2b3c4d`, `마무리: not_merged · integration 검증 실패` |
| 지적 개수 줄(마무리 상태 줄 아래) | `리뷰 지적: 수정됨 1 · 미해결 1 · …`. 상태마다 뜻과 볼 것은 [리뷰와 재리뷰](#리뷰와-재리뷰) |
| Evidence → 남은 위험(있을 때만, 맨 앞) | `- 01: 플러그인 격리 못 함: …`. claude worker의 플러그인 끄기가 빠진 채 돌았다는 뜻이다(worker를 막지는 않는다). `claude plugin list`가 되는지 본다 |
| Evidence → 실행 측정 | gs 버전·설치 commit, 일시 오류 수·대기 시간(전체, 티켓별), 표: worker 시도별 실제 모델·effort·소요·처리 대기, 리뷰어별 소요·결과 대기·지적·채택(fix, 해결 수와 다르다), 리뷰 호출별 시간(재호출 포함), gs 검증별 티켓 시도·재시도·명령·integration head·티켓 head·소요·결과(integration head는 검증한 integration 끝이라 같은 티켓의 여러 검증이 같을 수 있다), 마무리 단계별 시간. `결과 대기(초)`는 리뷰 호출이 돌아온 뒤 `gs go`가 그 결과를 받기까지다. 검증이 `gs go`를 붙잡는 동안 끝난 리뷰가 기다린 시간이고, 기록이 없는 옛 실행은 `기록 없음`이다. 어디서 시간을 썼는지 볼 때 읽는다. 뜻은 [internals](internals.md#상태) |
| Evidence → 검증 실패(마무리 전체 검증이 실패했을 때만) | 실패한 단계(`integration`, `integration-final`), 로그 경로, 실패 줄 최대 10줄, `후보 티켓(추정)`. 추정이라 틀릴 수 있다. 로그로 확인하고 `/grill`로 고칠 티켓을 더한다 |
| Evidence → 티켓별 결과 | 티켓마다 결과(`merged`, `failed`, `skipped`)와 이유. 단계별 소요(`worker 9분 · 리뷰 4분 · 수정 2분 · 재리뷰 1분 · 검증 3분`, 0분인 단계는 빼고 모두 1분 미만이면 `모두 1분 미만`). 미커밋 변경 때문에 남긴 worktree(`--only` 범위 밖 티켓 것도). `경고: setup이 추적 파일을 바꿨다 → 되돌림: …`, 플러그인 격리 경고 |
| Evidence → 리뷰 지적 | 다른 계열 reviewer의 지적 전부와 지적마다의 상태·근거·판단·재리뷰 근거. 리뷰어가 `checked`(확인한 완료 조건·돌린 명령과 결과)를 냈으면 `04 리뷰(codex) checked(믿을 수 없는 자료)` 목록이 붙는다. 리뷰어가 쓴 글이라 증거가 아니라 단서로 읽는다. 고쳐졌다고 확인된 지적도 `수정됨(재리뷰 확인)`으로 남는다. `second_reviewer`가 있으면 리뷰마다 `04 리뷰(codex)`, `04 리뷰(agy)`로 나뉜다. 리뷰 자체가 실패했거나 `건너뜀(한도)`이면 그 메모, 수정·재리뷰 경과 메모 |
| Evidence 끝 `agy 사용: N/상한` | 이번 실행에서 gs가 띄운 agy 호출 수 |
| Evidence → verify 출력 | 티켓마다 가장 최근 verify 로그와 integration·main 검증 로그의 끝부분(원본 그대로) |
| Merge Danger | 마무리 결과, PR, integration·main verify 결과, 병합·revert 커밋, 아직 남은 오류(뒤에 성공하면 지워진다), integration·main worktree의 setup 추적 파일 경고, 되돌리는 법(명령) |

**자주 보는 이유**(티켓별 결과의 "이유", `gs status`의 마지막 열)

| 이유 | 뜻 | 할 일 |
|---|---|---|
| `검증 실패(로그 <경로>)` | 티켓을 integration에 합친 결과가 티켓 검증 명령을 통과하지 못했다 | 그 `verify.log`를 읽는다 |
| `검증 시간 초과(<N>분, 로그 <경로>)` | verify가 `verify_minutes`를 넘겼다 | 시험이 멈추는지 보거나 spec의 `verify_minutes`를 늘린다 |
| `네트워크 대기: <이유>`, `중단(네트워크)` | 끊겨서 기다리는 중이거나 상한을 넘겨 멈췄다. 실패가 아니다 | [네트워크가 끊겼을 때](#네트워크가-끊겼을-때) |
| `시간 초과: <N>분 동안 로그 출력·새 커밋 없음` | worker가 `idle_minutes` 동안 아무것도 안 했다 | `worker.log` 끝을 본다. 티켓이 너무 크면 나눈다 |
| `커밋 없음`, `worker 종료 코드 <N>` | worker가 커밋 없이 끝났거나 실패로 끝났다 | `worker.log`, worker의 마지막 메시지(막힌 이유) |
| `conflict`, `integration 병합 충돌` | 먼저 병합된 티켓과 같은 곳을 고쳤다 | `merge.log`. 같은 파일을 건드리는 티켓은 `blocked_by`로 줄 세운다 |
| `막힘: 02` | 02가 실패해 이 티켓은 건너뛰었다(`skipped`) | 02를 고치면 같이 다시 돈다 |
| `준비 실패` | `worktree.setup`이 실패했거나 `timeouts.setup_minutes`를 넘겼다. 재시도하지 않는다 | `run/<티켓>/<시도>/setup.log`(보고서 Evidence에 끝부분). 명령·설치를 고쳐 다시 `gs go` |
| `agy 차단 장치가 없다: …` | agy가 gs hook을 걸지 못해 worker로 띄우지 않았다 | 그 티켓의 `model`을 바꾸거나 agy를 고친다 |
| `agy 한도: 이번 실행의 agy 호출이 상한 3/3에 닿아 worker를 띄우지 않았다(config agy.max_calls_per_run)` | 이번 실행의 agy 호출이 [상한](#agy-max_calls_per_run--gemini-호출-상한)에 닿았다. 재시도하지 않는다 | 상한을 올리거나 그 티켓의 `model`을 바꿔 다시 `gs go` |

실패한 티켓은 같은 계열에서 등급을 한 단계 올려(표가 없으면 같은 모델로) 한 번 자동 재시도한 뒤에도 실패한 것이다(`준비 실패`와 `agy 한도`는 재시도하지 않는다). 실패 원인이 티켓 검증이면 새 시도 전에 [수리 worker](#검증-실패-수리)가 한 번 먼저 돈다. 재시도한 모델은 보고서 "실행 측정"에 있다. 시도마다 증거가 `.goldstack/work/csv-export/run/<티켓>/<시도>/`에 남는다: `brief.md`, `setup.log`, `worker.log`, `verify.log`, `merge.log`, `failure.log`, `failure-summary.md`(`models.failure_summary`의 요약), `review/`(diff·reviewer 답), `fix/`·`fix2/`(수정 worker, 끊겨서 다시 띄웠으면 `fix-net1/` 등), `rereview1-<계열>/`·`rereview2-<계열>/`(재리뷰). 실패한 worktree(`run/wt/03`, `run/wt/03-retry-1`)도 지우지 않고 남긴다. 다 봤으면 [`gs clean`](#끝난-feature-치우기gs-clean)으로 지운다.

**마무리 결과**(보고서 Merge Danger, `■ 마무리:` 줄)

| 결과 | 뜻 |
|---|---|
| `integration·main 검증 통과, PR 병합 완료` | 끝. 실패한 티켓이 있어도 병합된 티켓은 main에 들어갔다 |
| `merged 티켓 없음 → 병합 안 함`, `integration 검증 실패 → 병합 안 함` | PR은 열렸거나 갱신됐지만 병합하지 않았다 |
| `병합 명령 뒤 PR이 아직 MERGED가 아니다. main 검증은 미실행` | 병합 큐·보호 규칙 대기. 병합된 뒤 `gs go`를 다시 돌리면 main 검증부터 이어 간다 |
| `사람 승인 필요: <PR>. main 검증은 미실행` | feature PR이 승인에 막혔다(`merge_pending`). 승인 뒤 `gs go` |
| `사람 승인 필요: <PR>` | `gs/<f>/revert` 또는 `gs/<f>/report` PR이 승인에 막혔다(`revert_pending`, `report_pending`). 승인 뒤 `gs go`. revert면 깨진 코드가 아직 main에 있다 |
| `report PR 확인 실패: …`, `revert PR 확인 실패: …` | PR 생성 응답이 실패·비었거나 조회가 실패해, PR이 생겼는지 모른 채 멈췄다(`report_pending`, `revert_pending`). 그대로 `gs go`하면 `gs/<f>/report`·`revert` 브랜치의 PR을 찾아 이어 간다 |
| `CI 실패: <이름>`, `CI 대기 시간 초과` | `git.wait_checks`의 검사가 실패했거나 `timeouts.checks_minutes`를 넘겼다(`checks_failed`, `checks_timeout`). PR은 열려 있다. 고치거나 CI를 다시 돌리고 `gs go` |
| `준비 실패 → 병합 안 함` | integration worktree의 `worktree.setup`이 실패했다(`setup_failed`). worker를 띄우지 않았고 PR도 없다. `run/integration/<시도>/setup.log`를 읽고 고쳐 `gs go` |
| `base 미검증(준비 실패)` | 병합 뒤 base worktree의 `worktree.setup`이 실패했다(`base_unverified`). 병합은 됐고 revert하지 않았다. `run/finish/setup.log`를 읽고 고쳐 `gs go`하면 base 검증부터 다시 한다 |
| `마무리 실패: squash 커밋 …의 tree가 검증한 integration …의 tree와 다르다…` | 실행 중 main이 움직였다. [squash 예시](#예시-squash만-허용)대로 main을 확인하고 빠져나온다 |
| `PR …이 병합되지 않고 닫혔다 → 병합 안 함. 다음 gs go가 새 PR을 연다` | 사람이 PR을 닫았다 |
| `main 검증 실패 → revert <sha>를 main에 push함` | 병합 뒤 main 검증이 실패해 병합 커밋을 되돌렸다(force push 없음). gs는 그 revert를 되돌린 커밋을 integration에 합쳐 둔다. 고칠 티켓을 더해 `gs go`하면 그 PR이 feature 코드를 되살린다 |
| `중단(네트워크)` | 대기 상한을 넘겨 티켓 단계에서 멈췄다(종료 코드 3). 마무리를 하지 않았다. 네트워크가 돌아오면 `gs go` |

### push 설정이 바뀌어 멈췄을 때

`gs go`는 worker를 띄우기 전에 원격의 URL·pushurl, 실제 push 주소, `core.hooksPath`를 기록하고, push마다 대조한다. 다르면 push하지 않고 종료 1로 멈춘다.

```text
gs go: git 오류: push 설정이 실행 시작 때와 달라 push하지 않았다(원격 `origin`). worker나 검증 명령이 바꿨을 수 있다.
- remote.origin.pushurl: (없음) → https://example.test/x.git (local)
- 실제 push 주소: https://github.com/owner/repo.git → https://example.test/x.git
되돌리기(레포에서):
  git config --local --unset-all remote.origin.pushurl
의도한 변경이면 `.goldstack/work/<feature>/run/state.json`의 `push_record`를 지우고 `gs go`를 다시 돌린다(지금 값을 새로 기록한다).
```

- 내가 바꾼 것이 아니면 먼저 어느 티켓이 바꿨는지 `run/<티켓>/<시도>/worker.log`에서 찾는다. 그 티켓의 커밋에 설정을 바꾸는 코드가 있을 수 있다.
- 되돌린 뒤 `gs go`를 다시 돌리면 멈춘 곳부터 잇는다. 병합한 티켓을 다시 돌리지 않는다.
- 주소에 인증 정보(`https://…@`)가 있으면 메시지에 싣지 않는다. 바뀐 값은 `***`로 가리고, 되돌리는 명령은 원래 값을 실행할 때 `state.json`에서 읽는다. 그대로 실행하면 된다. `url.*` 규칙의 키에 인증 정보가 있으면 명령 대신 고칠 곳을 알려 준다.
- 저장소를 옮겼거나 `worktree.setup`이 값을 바꾸는 경우(husky의 `core.hooksPath` 등)처럼 의도한 변경이면 메시지의 마지막 줄대로 한다.
- 바꾸는 쪽을 먼저 막는 것은 worker 차단 hook이다. worker의 `git remote` 변경, `git config` 쓰기, 자기 브랜치 밖의 ref 옮기기는 hook에서 막힌다. 설정이 필요한 명령 하나는 `git -c 키=값 <명령>`으로 하면 된다.
- `gs clean`도 같은 대조를 한다. 다르면 원격 브랜치는 지우지 않고 경고를 쓴 뒤 종료 1이다.

### 네트워크가 끊겼을 때

**무엇이 끊김인가** — 모델 CLI가 낸 연결 실패, DNS 오류, 5xx, 429다. 인증 오류, 구독 사용량 한도, 없는 모델 이름, 모르는 오류는 평소의 실패다(worker는 재시도, 리뷰는 `리뷰 실패`). 리뷰어·판단 모델의 시간 초과는 끊김으로 본다. worker가 출력 없이 `idle_minutes`를 넘긴 멈춤은 평소의 실패다.

**스스로 하는 일** — 사람이 할 일은 없다.
```
[02] 일시 오류(connection_failed): 실패로 세지 않는다. 네트워크 대기(1회, 1분 뒤)
[02] 네트워크 끊김 뒤 같은 worktree에서 다시 시작 (claude, pid 54960, 로그 …/run/02/2/worker.log)
■ 네트워크 회복: 다른 티켓 시작을 재개한다
```
1. **실패로 세지 않는다.** 재시도 횟수와 등급이 그대로이고, 실패 요약도 부르지 않는다.
2. **기다린다.** 1→2→5→10→10…분, 합계 `timeouts.network_wait_minutes`(기본 60)까지. 다시 부르는 것이 곧 회복 확인이다. 호스트를 따로 찌르지 않는다.
3. **같은 worktree에서 새 worker로 잇는다.** 커밋 안 된 작업도 남아 있고, brief에 "지난 시도가 네트워크로 끊겼다. `git status`와 `git diff`로 남은 변경을 보고 이어라"가 붙는다. 세션을 이어 가는 것은 아니다.
4. **그동안 새 worker·리뷰를 시작하지 않는다.** 도는 worker는 그대로 돌고, 성공으로 끝난 worker의 리뷰는 회복 뒤로 미룬다. 다시 띄운 worker가 5분 넘게 일시 오류 없이 돌거나 끝나면 회복이다(회복은 다시 띄운 worker로만 판정한다). 회복 뒤 30분 안에 다시 끊기면 같은 끊김으로 합계를 잇고, 그보다 오래 정상으로 돌았으면 새 끊김으로 새로 센다.

리뷰·재리뷰·판단 호출은 같은 일정으로 다시 부른다(합계는 호출마다 따로다). 리뷰어가 계속 시간 초과면 호출 시간까지 더해져, 기본값으로 첫 리뷰 하나가 약 6시간(호출 10번 × 30분 + 대기 60분)까지 간 뒤 중단된다. codex worker는 끊겨도 죽지 않고 `Reconnecting`을 찍으며 기다리므로, 그 상태가 상한을 넘기면 중단한다.

**`중단(네트워크)`** — 상한을 넘기면 실행을 멈춘다. 돌던 worker를 끝내고, 티켓은 `대기`로 두고, 보고서·PR·병합을 하지 않으며, 끊겼다는 이유로 리뷰 없이 병합하지 않는다. 종료 코드는 3이다.
```
[01] 중단(네트워크): worker를 끝낸다
■ 네트워크 중단 이유: 대기 합계가 상한 60분을 넘었다(timeouts.network_wait_minutes)
■ 중단(네트워크): 다음 gs go가 이어 간다
■ 요약: 병합 1, 대기 2
■ 마무리: 중단(네트워크)
```
```
❌ csv-export · 중단(네트워크) · 티켓 1/3 · 보고서 .goldstack/work/csv-export/report.md
```
마무리를 하지 않았으니 `■ 보고서:` 줄과 알림의 경로에는 파일이 없거나 지난 실행의 것이 있다. 지금 상태는 `gs status csv-export`로 본다.

**이어 가기** — 네트워크가 돌아오면 `gs go csv-export`(또는 `/go`)를 다시 친다. 끊긴 worker는 같은 worktree에서 잇고, worker가 끝나 있던 티켓은 리뷰·재리뷰부터 하고, 대기 합계는 새로 센다. 그 worktree를 지웠거나 브랜치가 달라졌으면 경고하고 새로 시작한다. agy worker는 다시 띄울 때도 호출로 세므로 [상한](#agy-max_calls_per_run--gemini-호출-상한)에 닿으면 `agy 한도`로 실패한다. 이 상한은 `agy.max_calls_per_run`으로 올린다. 대기 합계의 상한은 `timeouts.network_wait_minutes`로 올린다.

끊김을 자주 보면 보고서 "실행 측정"의 일시 오류 수·대기 시간을 본다. 마무리 단계의 push·`gh` 오류는 기다리지 않는다. 지금처럼 멈추고 다음 `gs go`가 잇는다.

### 다시 실행

고칠 것이 spec·티켓이면 `/grill csv-export`로 고치고(커밋까지 한다), 그 뒤 `/go csv-export`. 코드만 다시 돌리면 되면 바로 `/go csv-export`.
- integration에 병합된 티켓은 건너뛴다(`[01] 이미 병합됨`). 실패·건너뜀 티켓은 실패 횟수를 0으로 되돌리고 다시 한다.
- `gs go`가 죽어 `running`으로 남은 티켓은 실패로 세지 않고 새로 시작한다. 살아 남은 worker가 있으면 먼저 끝낸다.
- 지난 마무리가 끝나지 않았으면(승인·CI 대기, main 검증 전 등) 그것만 끝내고 멈춘다. 실패·건너뜀 티켓이 있으면 `■ 남은 티켓 N개 → 다음 gs go`이니 [한 번 더 친다](#예시-보호된-main--필수-승인).
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
- 재개한 마무리가 `verified`로 끝났지만 그 feature에 티켓이 남음(`■ 남은 티켓 N개 → 다음 gs go`): 출력은 위와 같다. 같은 줄을 다시 치면 남은 티켓부터 돈다.
- `not_merged`(integration 검증 실패, merged 티켓 없음), `merge_pending`(병합 큐·승인 대기), `checks_failed`·`checks_timeout`(CI), `revert_pending`·`report_pending`(gs PR의 승인 대기), `setup_failed`·`base_unverified`(준비 실패), `closed`, `reverted`(main 검증 실패로 revert).
- [`중단(네트워크)`](#네트워크가-끊겼을-때): `■ csv-export: 중단(네트워크) → 여기서 멈춤(남은: csv-import)`, 종료 코드 3. 같은 줄을 다시 치면 끊긴 곳부터 잇는다.
- `gs go`가 시작 전에 거부(미커밋 spec, 다른 `gs go`가 잠금): 종료 코드가 1이라 state에 지난 실행의 `verified`가 남아 있어도 멈춘다. state.json을 못 읽으면 `■ csv-export: unknown → 여기서 멈춤(남은: csv-import)`.

멈췄으면 앞 feature를 [실패했을 때](#실패했을-때)대로 고친 뒤 같은 줄을 다시 친다. 모두 병합돼 정리된 앞 feature는 `■ 이미 끝남: csv-export (verified)`로 바로 넘어간다. `--only`는 여러 feature와 함께 못 쓴다(`gs: error: 여러 feature와 --only는 함께 쓸 수 없다`).

**gs 재설치 한계** — gs는 `uv tool install`로 복사 설치되어 있고 `gs go a b`는 한 프로세스로 끝까지 돈다. 그래서 앞 feature가 gs 자체(goldstack 레포의 `src/gs/`, worker 차단 hook이 부르는 `gs hook`)를 고쳐 main에 병합해도 **다음 feature는 시작할 때의 옛 gs로 돈다.** 다음 feature가 앞 feature의 gs 변경에 기대면 이어 돌리지 말고 나눈다:
```sh
gs go goldstack-v4
git pull && gs self-update   # 새 gs로 바꾼다(로컬 설치였으면 gs self-update --from <원격 주소>)
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
| `run/wt/` 아래 전부(티켓·재시도·integration worktree, **미커밋 변경 포함**, git 등록이 풀린 잔여 디렉터리도) | `run/state.json`(지운 worktree 경로만 뺀다), `run/<NN>/<시도>/`(brief, `worker.log`, `review/`, `verify.log` …), `run/finish/` |
| 로컬 브랜치 `gs/csv-export/*` | spec·티켓·`report.md`(커밋된 것), main의 병합 커밋 |
| `git.remote`의 원격 브랜치 `gs/csv-export/*` | 열린·닫힌 PR(GitHub에 그대로) |

- 실행 중이면 거부한다(`--force`로도): `gs clean: 이미 다른 gs go가 돌고 있다(pid 48211)`. 검사와 삭제를 `gs go`와 같은 잠금 안에서 한다.
- 마무리가 `verified`·`reverted`가 아니면 거부한다: `gs clean: 마무리가 verified·reverted가 아니다(not_merged). --force가 필요하다`(실행 기록이 없으면 `(없음)`). 버릴 feature면 남긴 worktree의 미커밋 변경을 확인하고 `gs clean csv-export --force`. 그 뒤 다시 `gs go`하면 main에 들어가지 않은 integration이 사라졌으므로 티켓이 처음부터 다시 돈다.
- 하나를 지우다 실패하면 `경고: 정리 실패: …`를 쓰고 나머지를 계속한 뒤 종료 1.
- 정리한 뒤 같은 feature로 `gs go`를 쳐도 다시 만들지 않는다: 모든 티켓이 병합된 끝난 실행이면 `■ 이미 끝남: csv-export (verified)`(미커밋 변경 때문에 worktree를 남겼던 실행도, 그 worktree를 지웠으면 같다). 실패 티켓이 남았거나 새 티켓을 더했으면 평소처럼 이어 가고, 병합된 티켓은 건너뛴다.

**자동 정리** — 마무리가 `verified`로 끝나면 `gs go`가 main에 최종 보고서 push를 시도한 뒤 그 feature의 integration worktree(`run/wt/integration`)와 로컬·원격 `gs/csv-export/integration`을 스스로 지운다. 출력은 `지움: worktree …/run/wt/integration (미커밋 변경도 지움)` 한 줄이고 실패해도 `경고: 정리 실패: …`만 남는다(결과·종료 코드는 그대로). 원격 삭제만 실패했으면 다음 `gs go csv-export`가 `■ 이미 끝남` 뒤 다시 시도한다. 실패한 티켓의 worktree·브랜치는 자동으로 지우지 않는다(`gs clean`). `verified`가 아닌 마무리(`reverted`, `not_merged`, `merge_pending`, `report_pending` 등)는 원인을 보고 이어 갈 수 있게 integration을 남긴다. 보호된 base에서 쓴 원격 `gs/csv-export/report`·`revert` 브랜치는 자동으로 지우지 않는다(`gs clean`).

## 아이디어 흐름

실행에서 나온 생각은 아이디어 함 `.goldstack/ideas/`에 파일로 쌓였다가 다음 feature의 grill에서 후보가 된다. 보고만으로 남은 high·medium 리뷰 지적은 `/go`가 끝날 때 gs가 스스로 파일로 쓴다([리뷰와 재리뷰](#리뷰와-재리뷰)). `/go csv-export`가 끝나면 `/retro csv-export`가 그 실행 기록(report.md, state.json, worker 로그, 리뷰, 다른 feature 보고서와의 반복)을 읽고 고칠 후보를 제안하고, 사람이 고른 것을 아이디어 파일로 쓴다. 실행 중 대화에서 떠오른 생각은 `/idea <한 줄>`로 바로 넣는다. 다음 feature를 시작하기 전에 `gs backlog`로 열린 아이디어와 범위 밖의 다시 볼 조건을 훑고, `/grill <다음 feature>`를 부르면 라운드 1의 첫 질문으로 그 열린 아이디어 가운데 이번에 넣을 것을 묻는다. 고른 아이디어는 `status: taken`이 되어 다음 `gs backlog`에서 빠진다. 아이디어 파일은 커밋하지 않고 두면 `/grill`·`/go`의 커밋이 함께 담는다.

**`/retro csv-export`** — feature 실행을 돌아볼 때. 인자가 `.goldstack/work/` 아래 feature 이름이면 실행 기록을, 아니면 세션을 읽는다(아래 [`/retro`](#retro--실행을-돌아볼-때사용자-호출)). 후보를 번호 붙여 보이고, 다른 feature 보고서에도 같은 실패가 있으면 `[반복]`을 단다. 파일은 사람이 "1, 3"처럼 고른 뒤에만 쓴다.

**`/idea <한 줄>`** — 생각 하나를 바로 적을 때.
```
/idea gs status가 끝난 티켓의 리뷰 지적 수를 보이면 좋겠다
```
먼저 열린 아이디어에서 비슷한 것(같은 문제, 같은 곳)을 찾는다. 있으면 그 slug와 첫 줄을 보이고 "덧붙일까, 새 파일로 쓸까"를 묻는다. 덧붙이면 그 파일 끝에 `- 2026-11-03 <근거> (출처: …)` 줄이 붙는다. 없으면 slug·severity·source를 문맥에서 정해 새 파일을 쓰고 한 줄로 알린다:
```
.goldstack/ideas/status-review-count.md · 2026-11-03 · low · goldstack-v3 실행 중 대화 · open
```
severity는 `high`(결과·기록이 틀리거나 안전 구멍), `medium`(반복되는 손일·불편), `low`(다듬기). 커밋은 하지 않는다. 파일 형식의 원본은 plugin의 `skills/idea/templates/idea.md`이고, `/idea`가 그 파일을 직접 읽는다(대상 레포의 README를 가리키지 않는다).

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
열린 아이디어를 severity(high→low) → 날짜(오래된 것 먼저) → slug 순으로 보이고, 아래에 `.goldstack/out-of-scope/*.md`마다 `**다시 볼 조건**:` 문장을 보인다. 조건이 맞았으면 그 개념을 다음 grill에서 다시 꺼낸다. `--all`은 taken·dropped도 보이고 status 열을 더한다. 형식이 틀린 아이디어 파일은 `경고: <파일>: <이유>`로 알리고 목록에서 뺀다(`gs check`는 아이디어를 보지 않는다). 파일 형식은 `skills/idea/templates/idea.md`와 [internals.md](internals.md#아이디어-함).

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

## 버전 맞추기(`gs self-update`, `requires`)

처음 설치는 README대로 태그(`@v0.1.0`)에서 하고, 그 뒤 업데이트는 main 채널이다. 태그는 기록용이다.
- `gs go`·`gs doctor`는 시작할 때 설치본의 commit을 원격 main과 비교해 뒤처졌으면 `gs self-update`를 권하는 경고만 낸다. 조회가 안 되거나(오프라인) 출처를 모르면 건너뛴다. `uv tool install --reinstall .`로 설치한 로컬 설치는 설치 기록에 commit·주소가 없어 비교할 수 없으므로 `경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다`를 한 줄 낸다. 실행은 막지 않는다. 플러그인 버전이 gs와 다르면 그것도 경고한다.
- `gs self-update`: CLI를 main으로 재설치하고 이어서 플러그인(marketplace)을 갱신한다. `--version v0.1.0`처럼 태그로 고정할 수 있다. 이 머신에서 `gs go`가 돌고 있거나 프로세스 목록을 못 읽으면 아무것도 바꾸지 않고 거부한다. 확인 직후 시작하는 `gs go`까지는 막지 못한다(머신 공통 잠금은 없다). 머신이 여럿이면 머신마다 친다. 로컬 설치는 설치 기록에 git 주소가 없어 거부하므로 `gs self-update --from <원격 주소>`를 한 번 친다(주소는 `git remote get-url origin`). 그렇게 한 번 설치하면 설치 commit이 남아 경고가 사라지고 이후에는 `gs self-update`만 치면 된다.
- 레포가 최소 버전을 요구하려면 `.goldstack/config.toml`에 `[goldstack] requires = ">=0.1"`. 설치본이 더 낮으면 `gs check`·`gs go`가 오류로 멈춘다. 안 적으면 검사하지 않는다.

## 피드백: gs 결함을 goldstack에 알리기

현장에서 쓰다 드러난 gs 자체의 결함을 goldstack 저장소의 GitHub issue(라벨 `field-report`)로 올린다. 판단 모델 없이 규칙으로만 고른다.

**보내는 것** — gs의 내부 예외, 마무리 이상(재개 phase에 갇힘, 예상 밖 revert, 마무리 오류), 이름 붙은 어댑터 실패 패턴(예 codex ref 잠금 실패)과 모르는 어댑터 오류(`unknown`), 그리고 사람이 `gs feedback "한 줄"`·`/feedback`으로 직접 쓴 글. issue에는 gs·CLI 버전, OS, 단계, 동작에 영향을 주는 config 값(merge_method 등), gs 소스의 프레임(파일:함수:줄), 지문, 횟수, 그리고 `detail = "errors"`면 가린 오류 줄 최대 20줄이 들어간다.

**안 보내는 것** — 대상 레포 이름·원격 URL, 파일·디렉터리 이름, 코드·diff, 커밋 메시지, 브랜치·feature 이름, 사람 이름, `local.env` 값, 모델이 쓴 글. 오류 줄은 경로·이름·토큰 모양을 `<repo>/…`, `~`, `<feature>`, `<secret>`, `<name>`으로 가리고 흔한 오류 낱말만 남긴다. 티켓 구현 실패, 시험 실패, 리뷰 지적, 네트워크·인증·사용량 한도 같은 환경 오류는 올리지 않는다. 직접 쓴 글은 가리지 않고 쓴 그대로 나가니 회사 이름 같은 것을 넣지 않는다.

**동작** — 가린 초안을 `.goldstack/feedback/<지문>.md`에 쌓는다(gitignore). `mode = "auto"`면 `gs go`가 시작과 끝에 보낸다. `gh`가 실패하면 쌓아 두었다가 다음 `gs` 실행 때 다시 보낸다. 같은 지문의 열린 issue에는 새 issue 없이 하루 한 번 횟수 댓글만 단다. 하루 새 issue는 `max_per_day`(5)건까지다. 지문에는 gs 버전이 들어 있다. 피드백 코드가 실패해도 `gs go`의 결과는 바뀌지 않는다. `gs go` 끝에 `■ goldstack 피드백: 보냄 N · 대기 M`이 한 줄 나온다.

**프로젝트별로 끄기** — `.goldstack/config.toml`에서:
```toml
[feedback]
mode = "off"      # off | draft | auto
detail = "errors" # errors | minimal
```
- `off`: 아무것도 쓰지도 보내지도 않는다. 회사 레포에 권한다. `[feedback]` 절이 아예 없는 옛 config도 `off`다.
- `draft`: 로컬 초안만 쌓고 `gs feedback send`나 `/feedback send`로 직접 보낸다. `gs init`이 만든 config의 기본값이다.
- `auto` + `errors`: 개인 프로젝트용. 자동으로 오류 줄까지 보낸다. `minimal`이면 오류 줄 없이 항목만 보낸다.
`/adopt`가 새 레포에서 한 번 묻고 이 값을 적는다. 받는 쪽은 `gs backlog`와 `/grill` 1단계가 열린 `field-report` issue를 후보로 보인다. 티켓 키 `closes: [12]`면 그 PR이 병합될 때 issue가 닫힌다.

명령: `gs feedback "문장"` 또는 `gs feedback --body-file <파일>`(확인한 UTF-8 본문으로 초안을 쓰고 보낸다), `gs feedback list`(초안과 전송 상태. `status`도 같다), `gs feedback send`(쌓인 것 전송). skill은 `/feedback <문장 | --body-file 파일 | list | status | send>`.

**한 단어는 보내지 않는다** — `list`·`send`·`status`는 정상 하위 명령이라 예외다. `gs feedback statsu`처럼 그 밖의 한 단어는 하위 명령을 잘못 친 것으로 보고 `gs feedback: subcommand가 아니다. 보내려면 gs feedback "문장"`을 내고 종료 코드 2로 끝난다. 초안도 만들지 않는다. 옛 판은 `status`를 글로 보고 `draft` 모드에서도 공개 issue를 올렸다. `"status "`·`status ""`처럼 공백이나 빈 인자를 더해도 거부한다. 본문 파일도 두 단어 이상이어야 한다.

**`draft` 모드의 재전송** — 보내다 실패하면 초안은 남고 `gs feedback: 전송하지 못한 초안은 남겨 두고 gs feedback send로 보내세요.`가 나온다. `draft`는 사람이 보낼 때를 고르는 모드라 다음 `gs` 실행이 자동으로 다시 보내지 않는다. `auto`는 `다음 실행 때 다시 보냅니다.`로 알린다.

## `/overnight`: 자는 동안 이어 돌리기

자러 가기 전에 한 번 부르면 여러 feature를 병합까지 이어 돌리고 아침에 한 장으로 보고한다. 범위는 병합까지다(force push나 원격 브랜치 수동 삭제는 안 한다).
```
/overnight csv-export csv-import     # 시작
/overnight resume                    # 세션이 죽었거나 멈춘 밤을 잇는다
```
1. **시작 라운드**(사람이 앞에 있다): 순서와 feature끼리의 독립 여부, 사소한 수정 허락 범위, 텔레그램 켤지를 한 번에 묻는다. 답은 `.goldstack/overnight/<날짜>.md`에 적힌다(gitignore).
2. **사전 점검**: 원격 앞섬, `gs check`, 미커밋 grill, 세션 권한 모드(승인 창이 안 뜨는지), 디스크, CLI 로그인을 사람이 있을 때 확인한다. "자도 된다"가 나오면 그때부터 묻지 않는다.
3. **밤사이**: 그 파일에 적힌 허락만으로 feature를 차례로 잇는다. gs를 고친 feature 뒤에는 `git pull`과 `gs self-update`를 하고 다음을 돌린다. 앞 feature가 실패하면 시작 라운드의 독립 답대로 계속하거나 멈춘다. 허락 밖의 일을 만나면 멈추고 `아침에 물을 것`에 적는다.
4. **깨어 있기**: 맥은 `caffeinate`, 리눅스는 `systemd-inhibit`(없으면 건너뜀). 맥북은 전원을 연결하고 덮개를 연다.
5. **아침**: 같은 파일의 `결과` 표(feature, 상태, 다시 띄움 횟수, PR, 이유와 재개 명령)를 읽는다. 텔레그램이 켜져 있으면 요약 한 통이 온다.

시험은 skill 지침이 있는지만 확인한다. 실제 동작은 첫 사용에서 확인한다.

## 리눅스 서버에서 쓰기

herdr 없이도 된다. `gs go`를 herdr 밖에서 돌리면 worker가 화면 없는 프로세스로 돌고, 진행은 `gs status`와 `worker.log`로 본다. SSH가 끊겨도 돌게 하려면 tmux 안에서 띄운다:
```sh
tmux new -s gs
claude    # 여기서 /go 나 /overnight
# 떼어 놓기: Ctrl-b d · 다시 붙기: tmux attach -t gs
```
`gs go`가 죽었으면 다시 치면 같은 자리에서 잇는다. 설치는 README와 같고 `uv`, `git`, `gh`, `claude`가 필요하다. 이 레포의 시험은 GitHub Actions ubuntu에서도 돈다.

## 원격 머신에서 돌리기(`gs remote`)

맥북이 바쁠 때 herdr에 저장된 다른 머신(예: `mac_mini`)에서 `/go`를 끝까지 돌린다. 원격 pane에 claude를 띄워 `/go <feature>`를 보내고 바로 돌아온다. 이후 실행은 원격의 레포에서 일어난다. 필요한 `herdr`는 로컬에 있어야 하고 머신은 `herdr machine status`에 `reachable`로 보여야 한다.

### 준비 순서 (원격 머신에서, 한 번)
1. `gs` 설치: README의 설치를 따른다(`uv`, `git`, `gh`, `claude`, `codex` 필요). 로컬과 같은 버전이어야 한다.
2. 플러그인: `gs self-update`가 goldstack 플러그인도 갱신한다. 로컬 플러그인 버전과 같아야 한다.
3. 로그인: `gh auth login`, `claude auth login`, `codex login`(티켓 모델과 무관하게 `gs remote check`가 gh·claude·codex 인증을 모두 요구한다). 한 번 `claude`를 띄워 폴더 신뢰 확인도 끝내 둔다.
4. 클론: 대상 레포를 원격에 `git clone`한다. 원격 git이 `git.remote`를 읽을 수 있어야 한다.
5. 로컬 `.goldstack/local.env`에 원격 레포의 절대 경로를 적는다. 머신 이름이 키 접미사다:
   ```
   GS_REMOTE_REPO_mac_mini=/Users/me/workspace/csv-app
   ```
6. 원격 레포에 `.goldstack/local.env`를 복사한다. gitignore라 클론에 없다. 로컬의 `.goldstack/local.env.example`을 바탕으로 사람이 직접 만들고, gs는 파일이 있는지만 본다.

### `gs remote check <머신>`
준비를 항목별로 `통과`·`빠짐`으로 보이고 빠진 것은 고칠 방법을 붙인다. 하나라도 빠지면 종료 1이다:
```console
$ gs remote check mac_mini
통과: 연결 → 준비됨
통과: 레포 경로 설정 → 준비됨
통과: gs → 준비됨
빠짐: gh 인증 → 원격에서 gh auth login
```
비밀 값이나 인증 출력은 가져오지 않고 참·거짓만 받는다. `claude`·`codex`·`agy` 버전이 양쪽에서 다르면 `경고:` 줄만 낸다.

### `gs remote go <머신> <feature>`
같은 검사를 하고 grill 커밋(spec과 티켓)이 원격에 닿았는지 본다. 하나라도 빠지면 세션을 띄우지 않는다. feature는 grill 뒤 커밋·push돼 있어야 한다:
```console
$ gs remote go mac_mini csv-export
■ mac_mini에서 /go csv-export 시작
workspace: …
pane: …
상태: gs remote status mac_mini csv-export
화면: herdr --machine mac_mini pane read … --lines 40
```
같은 feature의 `gs go`가 원격에서 이미 돌고 있으면 새 세션을 띄우지 않고 pid와 상태 명령을 보인다. `/go` 전송 응답을 받지 못하면 전달됐을 수 있어 세션을 닫지 않는다. 안내된 `pane read`로 화면에 `/go`가 있는지 보고, 없을 때만 `workspace close`로 닫고 다시 친다.

### `gs remote status <머신> <feature>`
원격에서 `gs status`를 돌려 그 출력을 보인다. 끝나면 원격 레포의 `report.md`와 PR을 본다:
```console
$ gs remote status mac_mini csv-export
```
읽지 못하면 `gs remote check`로 연결부터 확인한다.

### 맥미니 실제 확인 (사람이)
코드 시험은 가짜 herdr로 돈다. 실제 머신은 아래 순서로 사람이 한 번 확인한다. 2026-11-05 점검에서 `mac_mini`는 연결되지만 `gs`, 플러그인, 레포 클론이 없고 gh가 로그인되지 않았다:
1. `herdr machine status`에서 `mac_mini`가 `reachable`인지 본다.
2. 위 준비 순서를 맥미니에서 끝내고 로컬 `.goldstack/local.env`에 `GS_REMOTE_REPO_mac_mini`를 적는다.
3. 작은 feature(티켓 하나) 하나를 grill·커밋·push한다. check도 grill 커밋이 원격에 닿았는지 보므로 이 단계가 먼저다.
4. `gs remote check mac_mini`가 `빠짐` 없이 끝나는지 본다. 그다음 `gs remote go mac_mini <feature>`를 친다.
5. 맥북을 닫거나 다른 일을 하면서 `gs remote status mac_mini <feature>`로 진행을 보고, `herdr --machine mac_mini pane read` 화면에 claude가 `/go`를 받았는지 확인한다.
6. 끝나면 PR이 만들어졌는지, 원격에서 로컬 레포로 `git pull`하면 보고서가 오는지 본다.
7. 실패한 단계와 화면 출력을 보고서나 아이디어 파일에 적는다. `--machine`이 붙은 `pane run`은 가짜 herdr로만 시험했고 실제로 돌려 본 적이 없다.

## 기존 레포 옮기기(`gs migrate`)

goldstack v2 전에는 파일이 레포 루트의 `.work/`, `.out-of-scope/`, `.ideas/`에 있었다. v2의 `gs`는 `.goldstack/` 아래만 읽는다(옛 위치 호환 없음). 새 `gs`를 설치한 뒤(`gs self-update`) 옛 레포에서 한 번:
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

`/grill`, `/go`, `/adopt`, `/idea` 밖의 다섯 skill은 [mattpocock/skills](https://github.com/mattpocock/skills)를 옮긴 것이다. 각 `SKILL.md` 끝에 원본 링크가 있다. `/idea`·`gs backlog`와 `/retro <feature>`는 [아이디어 흐름](#아이디어-흐름).

skill 본문(frontmatter 뺀 `split()`)에는 단어 상한이 있다. 상한은 `tests/test_skills.py`의 `WORD_LIMITS` 한 곳에 모여 있고, `grill`·`go`·`adopt`·`overnight`·`idea`·`retro`·`writing-for-agents`·`diagnosing-bugs` 각각 실제 단어 수의 약 10% 위(10단위 올림)다. skill 글을 고치는 티켓은 이 값과 지금 단어 수를 완료 조건에 적고, 늘렸으면 상한을 같은 티켓에서 올린다.

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
먼저 `gs retro-log csv-export`가 `.goldstack/work/csv-export/run/retro-log.md` 하나를 쓰고 그 경로를 출력한다. 티켓·시도별로 읽기 쉽게 바꾼 로그, 리뷰 답, `state.json`의 단계 시각이 들어 있고, 실패한 시도에는 오류 줄을 더한다. 약 21만 자(약 8만 토큰)를 넘으면 실패한 시도를 먼저 남기고 나머지를 줄이며 줄였다고 파일에 적는다. `run/`이 없으면(다른 머신에서 돌린 feature) 그렇다고 말하고 0이 아닌 코드로 끝난다. agy에는 이 파일 하나만 주고 근거는 그 파일의 줄 번호로 받는다. 티켓·시도별 실패 이유, 재시도 횟수, 반복된 리뷰 지적, 오래 걸린 단계를 요약하게 한다. Claude는 그 요약과 `report.md`·`state.json`으로 후보를 정하고, 근거로 인용할 곳만 원본 로그를 직접 연다. agy가 없거나 실패하면(종료 코드, 빈 답) 다시 부르지 않고 그렇다고 한 줄 말한 뒤 로그마다 끝부분과 오류 줄을 직접 읽는다. 200KB 미만이면 agy를 부르지 않는다. 이 호출은 gs가 아니라 skill이 부르므로 [`[agy] max_calls_per_run`](#agy-max_calls_per_run--gemini-호출-상한)에 세지 않는다.
길 찾기, 자동 검사, 리뷰 기준, `CLAUDE.md`·`AGENTS.md`, 도구 비용, 효과 없는 지시, goldstack 자체(`gs`, skill, spec·티켓 형식), 정보 접근 범주로 고칠 후보를 심각한 순으로 보인다. 후보마다 본 근거와 고칠 곳이 붙고, 다른 feature에도 있던 실패면 `[반복]`이 붙는다. **사람이 고르기 전에는 아무 파일도 바꾸지 않는다.** feature 회고면 고른 후보를 `/idea` 형식으로 `.goldstack/ideas/`에 쓰고(`source: /retro csv-export`), 세션 회고면 고른 것만 고치고 사람이 원하는 후보만 아이디어 함에 적는다.

### `/writing-for-agents` — agent가 읽는 문서를 쓸 때(사용자 호출)
새 skill을 만들거나 레포의 `CLAUDE.md`가 커져서 줄이고 싶다.
```
/writing-for-agents
skills/release/SKILL.md를 새로 쓰려 한다. description부터 같이 다듬자
```
문맥 포인터, 문맥 부담과 인지 부담, 정보 위계, 단계와 완료 기준, 리딩 워드, 쳐내기 기준을 문맥에 싣는다. skill이면 frontmatter와 호출 방식(사용자 호출·모델 호출) 고르기를 [SKILL-MECHANICS.md](../skills/writing-for-agents/SKILL-MECHANICS.md)에서 읽는다. `/retro`도 후보를 쓸 때 이 기준을 읽는다.
