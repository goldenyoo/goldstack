---
feature: goldstack-v0
verify: uv run python -m unittest discover -s tests
max_workers: 3
---
# goldstack v0 — spec

상태: grill 완료(라운드 4개) · 2026-11-03 · 근거 [docs/ORIGINS.md](../../docs/ORIGINS.md) · 티켓 [tickets/](tickets/) · 범위 밖 [.out-of-scope/](../../.out-of-scope/)

## 1. 목표
Claude Code로 프로젝트를 진행하는 개인 운영 kit. grill로 깊게 정렬 → `go` 한 번 → 자율 실행 → main 병합 → 최종 보고.
첫 대상은 goldstack 자신이다.

**완료 조건**: goldstack이 다음 feature 하나(예: `goldstack-v1`)를 `/grill` → `/go` → main 병합 → 보고까지 사람 개입 없이 한 번 완주한다. `/go` 이후 사람이 손대면 아직 끝나지 않은 것이다.

## 2. ORIGINS에서 이미 정한 것
| 항목 | 결정 |
|---|---|
| 흐름 | grill(라운드 질문, 추천 답) → `go` 한 번 → 자율 실행 → main 병합까지 자동 → 최종 보고 |
| 실행 | 코디네이터 1 + 티켓마다 새 worker(worktree, herdr pane). 세션 간 메시지 없음 |
| 병합 | worker 브랜치 → integration(코디네이터가 합침) → 검증 통과 시 main 자동. main이 깨지면 자동 revert |
| 모델 | grill에서 티켓마다 지정, 리뷰는 다른 계열 |
| 상태 | 레포 안 markdown 파일(`.work/<feature>/spec.md`, `tickets/NN-slug.md`), 실행 중 상태는 `.work/*/run/`(gitignore) |
| 멈춤 | 되돌릴 수 없는 일만: 배포, 외부 게시, 비밀, force push |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 코디네이터 | 결정적 스크립트 루프 `gs go`가 frontier·spawn·병합·검증·revert. 판단이 필요한 곳만 모델 호출. 규칙(횟수 상한 등)은 코드 |
| 1-2 | worker 실행 | herdr pane에서 headless(`claude -p`, `codex exec`, `agy -p`). 끝 = 프로세스 종료 + 종료 코드 + 브랜치 커밋 + 결과 파일. 프롬프트 주입 없음 |
| 1-3 | 언어·배포 | Python 3.12(uv), 표준 라이브러리만. CLI `gs` + Claude Code plugin(skill + hook) 같은 레포. 설치는 고정 복사 `uv tool install --reinstall .`(editable `-e`는 작업 트리를 따라 바뀌므로 1-6과 어긋난다. 01 구현 중 발견) |
| 1-4 | cc-ops-kit 재사용 | herdrkit에서 필요한 함수만 복사해 줄임. codexrun·usage는 v0 밖 |
| 1-5 | 사용자 명령 | `/grill <feature>`, `/go <feature>` + 읽기 전용 `gs status` |
| 1-6 | 부트스트랩 | 01·02를 손으로 만들고 나머지는 goldstack `go`로(§6). 실행은 작업 worktree가 아니라 설치된 고정 버전 |
| 1-7 | v0 완료 조건 | §1 |
| 2-1 | 검증 | feature마다 spec frontmatter `verify`에 명령 하나. `gs`가 직접 돌린 결과만 인정 |
| 2-2 | main 병합 | feature당 PR 하나(integration → main), 검증 통과 시 `gs`가 `gh pr merge`. PR 본문 = 보고서. 병합 직후 main에서 재검증, 실패 시 `git revert` |
| 2-3 | 리뷰 시점 | 티켓마다 integration에 합치기 전, 다른 계열이 그 티켓 diff만 |
| 2-4 | 리뷰 종료 | 수정 1회. 남은 지적은 보고서에, 검증 통과면 병합 |
| 2-5 | 실패·멈춤 | 출력·커밋 없이 일정 시간(기본 20분) → 종료, 실패 로그 붙여 새 worker로 1회 재시도, 또 실패면 그 티켓과 그 티켓에 막힌 티켓만 실패, 나머지 계속 |
| 3-1 | worker 권한 | 권한 확인 없이 실행, 되돌릴 수 없는 일만 장치로 차단(claude: plugin hook, codex: `workspace-write` sandbox, agy: 11 조사). push·PR·병합은 `gs`만 |
| 3-2 | 티켓·상태 | 티켓은 `go` 뒤 불변. 진행 상태는 `.work/<f>/run/state.json` |
| 3-3 | 동시 worker | spec frontmatter `max_workers`, 기본 3 |
| 3-4 | 병렬 충돌 | grill에서 같은 파일을 건드릴 티켓은 blocked_by로 직렬화. 그래도 충돌하면 최신 integration 위에서 새 worker로 다시(재시도 1회로 셈) |
| 3-5 | 판단 모델 | 리뷰 지적 분류·실패 요약·보고서는 매번 새 `claude -p`(Opus), 파일 경로만 넘김 |
| 3-6 | 최종 보고 | `.work/<f>/report.md`(PR 포함) = PR 본문: 요약, 티켓별 결과, 남은 지적, 검증 출력, 되돌리는 법. `/go` 세션은 세 줄 요약 + PR 링크 |
| 4-1 | 티켓 분해 | 11장(§5). 모듈을 나눠(loop, worker, review, merge, report) 병렬 충돌을 줄인다 |
| 4-2 | 부트스트랩 순서 | §6 |
| 4-3 | 시험 seam | 하나: 임시 git 레포(원격은 로컬 bare 레포) + 가짜 worker 명령으로 `gs go` 전체를 돌린다. herdr·gh·모델 호출도 가짜로 바꿔 끼울 수 있게. 파싱·그래프 같은 순수 함수만 단위 시험 |
| 4-4 | 재시도 모델 | 같은 모델 + 실패 로그 |
| 4-5 | 범위 밖 | `.out-of-scope/`(사용량 어댑터, retro·학습 루프, 원격 머신, 알림, wayfinder, GLOSSARY·ADR, prototype 단계, 대화형 worker) |

## 4. 형식
**spec frontmatter**: `feature`, `verify`(셸 명령 한 줄), `max_workers`(정수, 기본 3), `idle_minutes`(정수, 기본 20, 07부터). 그 밖의 키는 무시하지 않고 `gs check`가 경고.

**티켓** `.work/<f>/tickets/NN-slug.md`:
```
---
id: "03"
title: 한 줄 제목
blocked_by: ["02"]
model: claude        # claude | codex | agy
reviewer: codex      # model과 다른 계열
---
## 목표
## 완료 조건   (검증 가능한 문장으로)
## 범위 밖
## 참고        (선택: 문서 포인터. 파일 줄 번호는 적지 않는다)
```

**브랜치**: integration `gs/<feature>/integration`, 티켓 `gs/<feature>/NN`. `gs/<feature>` 자체는 만들지 않는다(ORIGINS 실패 12: `ws/W0`와 `ws/W0/x` 공존 불가).

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | 뼈대: `gs` CLI, 파싱, 그래프·frontier·순환 검출, `gs check` | – | 손 | claude | codex |
| 02 | 최소 `gs go`: 순차, claude headless worker, integration, 검증, PR 생성 | 01 | 손 | claude | codex |
| 03 | 실행 상태, `gs status`, 재실행 시 이어가기 | 02 | 1 | claude | codex |
| 04 | 병렬 실행 | 03 | 1 | claude | codex |
| 05 | 모델 어댑터: codex, agy | 02, 11 | 1 | claude | codex |
| 06 | 다른 계열 리뷰와 수정 1회 | 04, 05 | 2 | claude | codex |
| 07 | 실패·멈춤 처리와 재시도 | 04 | 2 | codex | claude |
| 08 | 마무리: 보고서, 자동 병합, main 재검증, revert | 06, 07 | 2 | codex | claude |
| 09 | plugin 뼈대와 worker 차단 hook | 02 | 1 | claude | codex |
| 10 | skill `/grill`, `/go` | 09 | 2 | claude | codex |
| 11 | 조사: agy 권한과 차단 장치 | – | 1 | claude | codex |

같은 파일을 건드릴 것 같은 쌍은 이미 줄 세웠다: 03→04(상태·루프), 04→06·07(루프), 06·07→08, 09→10(plugin 매니페스트).

## 6. 부트스트랩 진행
`gs go`는 도는 동안 자기 자신이 바뀌지 않는다(설치된 고정 버전). 그래서 v0는 단계로 나눠 돌린다.

```
① 손:     01, 02          이 세션이 구현
② wave 1: 03 04 05 09 11  gs go goldstack-v0 --only 03,04,05,09,11   (02 엔진: 순차, claude만)
③ wave 2: 06 07 08 10     gs go goldstack-v0 --only 06,07,08,10      (wave 1 엔진: 병렬, codex·agy)
④ v1:     완전한 엔진으로 첫 무인 완주 = 완료 조건
```

- **v0 리뷰는 11장 모두 손**이다. 자동 리뷰(06)는 v1부터 돈다. 01·02는 이 세션이 브랜치에서, wave 1·2는 `gs`가 연 PR에서 이 세션이 '리뷰 계열' 모델을 새 문맥으로 불러 티켓 커밋별로 리뷰 → 지적 분류 → 수정 1회 → 병합한다. claude 리뷰도 이 세션이 아니라 새로 띄운 claude가 한다.
- 08 전까지 `gs go`는 PR을 열기만 하고 병합하지 않는다.
- wave 사이에 main을 받고 `gs`를 다시 설치한다.

## 7. 환경 사실 (2026-11-03 확인)
- origin: `github.com/goldenyoo/goldstack` (private), `gh` 로그인됨(goldenyoo)
- herdr 0.9.5, codex-cli 0.166.0, agy 1.4.12(Gemini; `gemini` CLI는 없음), Claude Code 2.1.316
- 시스템 python3 = 3.9.6, `uv` 있음. cc-ops-kit `lib/herdrkit.py`(360줄)는 3.10+ 가정
- herdr: `pane run`, `pane wait-output`, `pane read`, `pane close`, `worktree create/remove`. 구독 CLI는 없고 socket API
- headless: `claude -p --output-format stream-json`, `codex exec --json -s workspace-write`, `agy -p --output-format stream-json --mode auto`

## 8. grill 기록
### 라운드 1 — 형태와 실행 구조 (모두 추천대로)
사용자가 옵션 차이를 예시로 다시 설명해 달라고 했고, "pstack·mattpocock은 A·B 중 어느 쪽?"을 물었다 → 둘 다 A(글로 지휘하는 Claude), mattpocock은 써 본 뒤 결정적 루프가 낫다고 적음. 그 뒤 1번 B 확정.
1. 코디네이터: 결정적 스크립트 루프 / 2. worker: headless / 3. Python 3.12 + plugin / 4. herdrkit 복사해 줄이기 / 5. 명령 2개 + `gs status` / 6. 작은 엔진부터 dogfood / 7. 무인 완주 1회

### 라운드 2 — 검증, 병합, 리뷰, 실패 (모두 추천대로)
1. `gs`가 돌린 검증 명령만 인정 / 2. feature당 PR 하나, 자동 병합, 재검증·revert / 3. 티켓마다 리뷰 / 4. 수정 1회 / 5. 시간 초과 → 재시도 1회 → 막힌 티켓만 실패

### 라운드 3 — worker 권한, 티켓, 병렬, 보고 (모두 추천대로)
1. 권한 확인 없이 + 되돌릴 수 없는 일만 차단 / 2. 티켓 불변, 상태는 run/ / 3. 동시 3 / 4. blocked_by 직렬화 + 충돌 시 재실행 / 5. 판단은 매번 새 `claude -p` / 6. report.md = PR 본문

### 라운드 4 — 티켓 분해와 부트스트랩 (모두 추천대로)
사용자 질문: "리뷰에서 손이라는 게 어떤 의미?" → 이 세션이 직접 리뷰를 돌린다는 뜻. 설명하다 wave 2 리뷰도 자동이 아니라는 표 오류를 발견해 고침(v0 리뷰는 전부 손).
1. 티켓 11장 / 2. 손 → wave 1 → wave 2 → v1 / 3. 시험 seam 하나 / 4. 재시도는 같은 모델 / 5. 범위 밖 8개
