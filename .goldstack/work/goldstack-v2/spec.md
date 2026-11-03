---
feature: goldstack-v2
verify: uv run python -m unittest discover -s tests && claude plugin validate .
max_workers: 3
---
# goldstack-v2 — spec

상태: **완료**(PR #4, 2026-11-03, 2시간 11분, 티켓 8장 첫 시도 병합, 남은 지적 18) · 병합 뒤 손 마무리(`gs` 재설치, `gs migrate`, 링크 수정, v0–v2 `gs check` 통과) 완료 · grill 완료(라운드 2개) · 2026-11-03 · 근거 [goldstack-v1 진행 대화](../goldstack-v1/spec.md) · 아이디어 [.ideas/](../../ideas/) · 범위 밖 [.out-of-scope/](../../out-of-scope/)

## 1. 목표
goldstack을 다른 레포에서도 가정 없이 쓸 수 있게 한다(설정 파일, 하드코딩 제거). 실행 중에는 진행 바로, 끝나면 텔레그램으로 안다. mattpocock skill 5개를 이식하고, README를 사람용으로 다시 쓴다.

**완료 조건**: 설치된 v1 엔진이 이 feature를 `/go` 한 번으로 사람 개입 없이 main 병합·보고까지 간다. 병합 뒤 손 마무리(`gs` 재설치 → `gs migrate` → 커밋)를 하면 `gs check goldstack-v0`, `goldstack-v1`, `goldstack-v2`가 새 위치(`.goldstack/work/`)에서 오류 없이 통과한다. 진행 바·텔레그램은 시험으로 확인하고, 실제 모습은 다음 feature 실행에서 처음 본다(v2는 v1 엔진이 돌린다).

## 2. 이미 정해진 것 (grill 전 대화, 2026-11-03)
| 항목 | 결정 | 근거 |
|---|---|---|
| 원칙 | goldstack은 사용자 머신·레포를 가정하지 않는다. 설정은 대상 프로젝트 안의 파일에 두고, 비어 있으면 채우라고 안내한다. 비밀(토큰)은 커밋하지 않는 파일에 둔다 | 사용자 |
| 범위 ① 이식성 | `gs init`, `.goldstack/config.toml`(커밋) + `.goldstack/local.env`(gitignore) + `local.env.example`. 하드코딩 제거 후보: 기본 브랜치·원격(`main`/`origin`), 모델 이름(`opus`, agy slug), 리뷰·판단 시간 제한, run 디렉터리 ignore(다른 레포에서 worktree가 커밋에 섞일 위험), 티켓 모델 CLI 사전 확인, `gs` CLI 설치 확인. worker hook에 `.goldstack/local.env` 읽기 차단 추가 | 라운드 3-1 A |
| 범위 ② 텔레그램 | 끝·실패 알림. 설정 파일을 처음 쓰는 기능. 레퍼런스: mac_mini `~/workspace/asset_tracker/notify/telegram.py`(stdlib urllib, 시험 러너에서 전송 안 함, 예외 안 냄, 3회 재시도, 3900자 자름, 토큰 가림). 토큰 위치는 가정하지 않는다(위 원칙) | 라운드 3-1 A |
| 범위 ③ 진행 바 | Claude Code mod로 `/go` 세션 프롬프트 위에 진행 바. 참고: JohnnyVizz/claude-kit `savvy-progress`(mod hooks API early-access, Claude Code 2.1.286에서 시험됨). 재료는 `run/state.json` | 라운드 3-1 사용자 추가 |
| 파일 위치 | 대상 레포의 goldstack 파일을 `.goldstack/` 아래로 모은다: `config.toml`, `local.env`, `work/<feature>/`, `out-of-scope/`, `ideas/` | 라운드 3-2 A |
| 범위 ④ skill 이식 | mattpocock/skills(MIT, 커밋 4ae2317)에서 5개: `wait-what`, `handoff`, `diagnosing-bugs`, `retro`, `writing-for-agents`. 저작권 표기 유지, GLOSSARY 등 matt 전제는 걷어 낸다. model-invoked는 `diagnosing-bugs`만(문맥 비용) | 라운드 3-3 B |
| 범위 ⑤ 문서 | README = 사람의 첫 화면(설치, 5분 따라 하기, skill 목록·언제 쓰나), `docs/guide.md` = 예시가 있는 사용 가이드, `docs/internals.md` = 지금 README의 엔진 명세. **이식한 skill마다 설명과 사용처(언제, 예시)가 드러나게** | 라운드 3-4 A + 사용자 요청 |
| 다음(v3) | 아이디어 흐름: `/idea`, `/retro <feature>`(+ `/insights` 보고서는 찾을 수 있으면 선택 입력, 경로는 그때 확인), `gs backlog`, 다음 `/grill`이 후보를 첫 라운드에 묻기. v2의 `retro` 이식은 matt 원본(세션 retro) 수준, v3가 goldstack 실행 기록으로 넓힌다 | 라운드 3-5 A |
| 하지 않음 | codex 비용 집계(사용자 판단 불필요), mattpocock 플러그인 설치(이식으로 대신) | 사용자 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | `.goldstack/` 이동 | v2는 새 위치만 읽는 코드와 `gs migrate`를 만든다. 실행 중에는 이 레포의 파일을 옮기지 않는다. 병합 뒤 손으로 `gs` 재설치 → `gs migrate` → 커밋. 옛 위치 호환 코드는 두지 않는다 |
| 1-2 | config 없음 | `gs check`·`gs go` 오류 + "`gs init`을 먼저" 안내. `gs init`이 base 브랜치를 `origin/HEAD`에서 찾아 적는다. 레포마다 값은 config.toml, feature마다 값은 spec frontmatter |
| 1-3 | 텔레그램 시점 | 실행 끝에 한 통(성공·실패·revert). 토큰 없음·전송 실패는 경고만, 결과 불변. 보내는 쪽은 gs |
| 1-4 | 남은 시간 | 경과 + 현재 단계 + 이번 실행 기준 ETA. state에 단계별 시각, 보고서에 단계별 소요 |
| 1-5 | skill 이식 | 한국어로 옮기고 goldstack에 맞춤(matt 전제 제거), 원본 링크·MIT 표기 |
| 1-6 | 하드코딩 제거 | 8개 전부: 원격·base, run ignore, 모델 이름, 리뷰·판단 시간 제한, GitHub 아닌 원격 경고, 티켓 모델 CLI 사전 확인, `gs` 없을 때 hook 조용히, hook이 `.goldstack/local.env` 차단 |
| 1-7 | grill 답 되짚기 | v2에 넣는다(`skills/grill/SKILL.md` 4단계 한 줄) |
| 1-8 | mod 위치 | goldstack 플러그인 안(`hooks/hooks.json`에 `modules`). validate로 같이 못 넣는다고 확인되면 별도 플러그인 디렉터리 |
| 1-9 | 바가 보여 줄 실행 | 이 레포에서 끝나지 않았고 최근 갱신된 state.json 자동 선택, 없으면 숨김 |
| 1-10 | 진행 계산 | gs가 state.json `progress` 필드에 계산(Python 시험), mod는 그리기만. verify에 `&& claude plugin validate .` |

## 3-1. grill 전 열린 문제(라운드 1에서 닫힘)
- 범위가 크다(이식성·텔레그램·진행 바·skill 5개·문서). 티켓 수와 순서, 진행 바 조사 티켓을 앞에 둘지.
- **자기 이동 문제**: 이 feature는 설치된 v1 엔진이 `.work/goldstack-v2/`에서 돈다. 파일 위치를 `.goldstack/`로 옮기는 티켓이 실행 중인 feature의 경로(보고서 `.work/<f>/report.md`, `_require_committed`)와 어긋나지 않게 순서·호환(옛 경로 읽기)을 정해야 한다.
- 설정 파일 형식(toml 키 이름, 기본값, 없을 때 동작)과 `gs init`이 무엇을 쓰는지.
- 진행 바 ETA에 필요한 단계별 시각을 state에 남길지.
- `.ideas/`의 "grill 답 되짚기"(skill 한 줄)를 v2에 넣을지.

## 4. 형식
**`.goldstack/` 배치**(대상 레포 루트):
```
.goldstack/config.toml          커밋. 레포마다 값
.goldstack/local.env            gitignore. 비밀(TG_TOKEN, TG_CHAT_ID)
.goldstack/local.env.example    커밋. 빈 값 + 채우는 법 안내
.goldstack/work/<feature>/      spec.md, tickets/, report.md (run/은 gitignore)
.goldstack/out-of-scope/        뺀 개념
.goldstack/ideas/               아이디어 함(형식은 v3)
```
`.gitignore`에 `gs init`이 넣는 줄: `.goldstack/local.env`, `.goldstack/work/*/run/`

**config.toml**(`gs init`이 전부 쓴다. 빠진 키는 오류, 모르는 키는 경고):
```toml
[git]
remote = "origin"
base = "main"                 # gs init이 refs/remotes/<remote>/HEAD에서 찾는다
[models]
judge = "opus"                # 실패 요약·리뷰 분류·보고서용 claude -p --model
claude_review = "opus"        # claude reviewer --model
agy = "gemini-4-argon-high"   # agy worker·reviewer --model
codex = ""                    # 비우면 codex 기본 모델
[timeouts]
review_minutes = 30
judge_minutes = 10
summary_seconds = 60
[notify]
telegram = false
```
- feature마다 값은 지금처럼 spec frontmatter(`verify`, `max_workers`, `idle_minutes`, `verify_minutes`).
- `local.env`는 `KEY=value` 줄. `os.environ`은 보지 않는다(원천 하나). gs는 토큰을 출력·로그에 쓰지 않는다.
- 명령: `gs init`(없는 파일만 만든다, 있으면 그대로 두고 알림), `gs config <섹션.키>`(값 한 줄 출력, skill이 base 브랜치를 읽을 때 쓴다), `gs migrate`(아래).

**`gs migrate`**: `.work/<f>/`(tracked) → `.goldstack/work/<f>/`, `.out-of-scope/` → `.goldstack/out-of-scope/`, `.ideas/` → `.goldstack/ideas/`를 `git mv`로 옮긴다. untracked `run/`도 같이 옮긴다. `.work/` 아래에 등록된 git worktree가 남아 있으면 옮기지 않고 목록과 지우는 명령을 보여 주며 실패한다. config가 없으면 `gs init`을 한다. `.gitignore`의 `.work/*/run/` 줄을 새 줄로 바꾼다. 커밋은 하지 않고 다음 할 일을 출력한다. 옮길 것이 없으면 아무것도 하지 않는다(두 번 돌려도 같다). 문서 안 상대 링크는 고치지 않는다.

**state.json `progress`**(gs가 상태를 바꿀 때마다 갱신, 04):
```json
{"done": 3, "total": 8, "running": [{"id": "04", "phase": "review", "model": "codex"}],
 "elapsed_s": 1440, "eta_s": 2400, "line": "▓▓▓░░░░░ goldstack-v2 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음"}
```
- phase: `worker`, `review`, `fix`, `verify`, `finish`. 티켓 상태에 단계별 시작 시각을 남긴다.
- ETA: 이번 실행에서 끝난 티켓의 평균 소요 × 남은 티켓 수 ÷ 동시 worker 수. 끝난 티켓이 없으면 `eta_s: null`, line에 "남은 시간 계산 중".
- report.md 티켓 결과에 `단계별 소요: worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`.

**진행 바 mod**(05): 1초마다 이 레포의 `.goldstack/work/*/run/state.json` 중 `finished_at`이 비었고 최근 10분 안에 바뀐 것 하나(가장 최근)를 골라 `progress.line`을 프롬프트 위(`AbovePrompt`)에 그린다. 없으면 아무것도 그리지 않는다. 계산은 하지 않는다.

**텔레그램**(06): `gs go`가 끝날 때 `notify.telegram = true`면 한 통. 형식:
```
✅ goldstack-v2 · main 병합
티켓 8/8 병합 · 52분 · 남은 지적 2
PR https://github.com/…/pull/4
```
실패면 `❌ <feature> · <마무리 결과> · 티켓 n/m (<id> 실패: <이유>) · 보고서 <경로>`. 표준 라이브러리 urllib, 3회 재시도, 3900자 자름, 예외를 밖으로 내지 않음, 토큰은 오류 문자열에서도 가림. 시험 seam: `GS_TELEGRAM_API`(기본 `https://api.telegram.org`). 켜져 있는데 토큰이 없으면 `gs check` 경고, 실행 끝에는 경고 한 줄.

**문서 규칙**: README·`docs/`는 08만 바꾼다(다른 티켓은 README를 건드리지 않는다).

## 5. 티켓 그래프
| id | 제목 | blocked_by | wave | 구현 | 리뷰 계열 |
|---|---|---|---|---|---|
| 01 | 설정 파일: config, `gs init`, `gs config`, `gs check` 검사 | – | 1 | codex | claude |
| 02 | `.goldstack/work/` 위치·base·원격을 config에서 + `gs migrate` | 01 | 2 | claude | codex |
| 03 | 모델·시간 제한 config화, CLI 사전 확인, GitHub 경고, hook 정리 | 02 | 3 | codex | claude |
| 04 | 단계별 시각과 `progress`(ETA), 보고서 단계별 소요 | 03 | 4 | codex | claude |
| 05 | 진행 바 mod | 04 | 5 | claude | codex |
| 06 | 텔레그램 알림 | 04 | 5 | claude | codex |
| 07 | mattpocock skill 5개 이식 + grill 답 되짚기 | 02 | 3 | claude | codex |
| 08 | 문서: README(사람용), guide, internals | 05, 06, 07 | 6 | claude | codex |

01→02→03→04: go.py·finish.py·report.py·check.py·시험 fixture를 함께 건드린다. 05(hooks/, plugin.json)와 06(notify.py, 마무리 호출)은 겹치지 않아 병렬. 07은 skills/만, 02가 /grill·/go skill의 경로를 바꾸므로 02 뒤. README·docs는 08만.
06은 localhost 가짜 서버 시험이라 claude(codex sandbox는 localhost 불가), 05는 내장 `plugin-authoring` skill이 필요해 claude.

## 6. 환경 사실 (2026-11-03 확인)
- 설치된 `gs`는 v1(verify 시간 제한, worktree 정리 포함). `~/.local/share/uv/tools/goldstack`(python 3.13)
- 이 노트북에는 `~/.config/telegram/notify.env`가 없다(mac_mini에만 있음). 원칙상 그 위치를 쓰지 않는다
- `/insights` 보고서: 2026-11-03에 처음 생성됨 `~/.claude/usage-data/report-2026-11-03-141836.html`, facets는 `~/.claude/usage-data/facets/`(v3 retro 입력 후보)
- 경로·브랜치 가정이 있는 곳(grep `.work`, `out-of-scope`, `main`, `origin`): go.py 17, finish.py 16, worker.py 10, hook.py 8, adapters.py 6, skills/go·grill 각 4, feature.py·cli.py·report.py 각 3, status.py 2, state.py 1. 시험도 `.work`에 묶임(test_go 17, test_check 6, test_adapters 4)
- feature 위치는 `feature.load`가 `repo / ".work" / name`으로 정한다. worker brief는 `.work/<f>/spec.md`, `.work/<f>/tickets/…`를 "이 worktree 안에 있다"며 가리킨다 → 실행 중 티켓이 디렉터리를 옮기면 그 뒤 worker는 spec·티켓을 못 찾는다(자기 이동 문제의 실체)
- 시험 레포는 `.gitignore`에 `.work/*/run/`를 직접 쓴다(test_go). 실제 대상 레포에서는 아무도 안 쓴다
- 코드 4119줄, 시험 193개 약 3분(v1 verify 로그 169–187초)
- Python 3.12+ 표준 라이브러리 `tomllib`은 읽기 전용(쓰기 없음) → `gs init`은 템플릿 문자열로 쓴다
- mattpocock 원본 clone: 커밋 4ae2317(2026-10-31). 이식 대상 크기: wait-what 60단어, handoff 144, retro 679, diagnosing-bugs 1427, writing-for-agents 1777(+ SKILL-MECHANICS.md)
- 진행 바 mod(조사, 2026-11-03): savvy-progress는 `hooks/hooks.json`에 `{"modules": ["./register.tsx"]}`, `register.tsx`가 `export const register`, `ui.render {component:'AbovePrompt'}`에서 `Text`로 바를 그린다. 값은 모델의 MCP 도구 호출로 받고 파일 감시는 없다. 엔진 API에 `$.fs.read/stat/exists/list`(텍스트 4MiB), `$.clock.every(ms)`가 있어 state.json polling이 가능하다(watch API는 없음). 빌드 불필요(엔진이 .ts/.tsx를 직접 로드, no DOM/no Node). 참고 문서: Claude Code 2.1.317 번들 skill `plugin-authoring`(reference.md, types/claude-code.d.ts, examples/band.tsx)
- mod 위험: hooks API early-access(릴리스마다 바뀔 수 있음, savvy-progress는 2.1.286에서 시험). marketplace 설치본에서 mod가 안 뜰 수 있다(README 경고, `--plugin-dir`·`CLAUDE_CODE_PLUGIN_DIRS`로 우회). 기존 command hook(`"hooks"`)과 `"modules"`를 같은 hooks.json에 둘 수 있는지는 미확인
- `claude plugin validate .`: 이 레포에서 0.7초, 통과(경고 있음), 모델 호출 없음. `claude plugin test [dir]`는 mod 시험 실행기
- node v25.8.1 있음(mod에는 불필요), bun·deno 없음

## 7. grill 기록
### 라운드 1 — 위치 이동, 설정, 알림, 시간, skill, 진행 바 (모두 추천대로)
사용자 답 "yes" → 1–10 추천 전부로 읽고 한 줄씩 되짚어 보임(1-7을 이 라운드부터 적용). 8–10은 mod 조사 결과가 온 뒤 같은 라운드에 추가했다.
1. 이동: A 코드만+`gs migrate` 병합 뒤 / B 옛 위치 호환 / C 마지막 티켓이 이동 — 추천 A(실행 중 feature의 경로를 바꾸지 않음, 호환 코드 없음) → 확정 A
2. config 없음: A 오류+`gs init` 안내 / B 내장 기본값 — 추천 A(숨은 가정 없음) → 확정 A
3. 텔레그램: A 끝에 한 통 / B 티켓 실패마다도 — 추천 A(중간 재시도는 gs 몫, 소음) → 확정 A
4. 남은 시간: A 경과+단계+이번 실행 ETA / B 경과·단계만 / C 지난 실행 기록 — 추천 A(원래 원한 것, 단계 시각은 보고서에도 씀) → 확정 A
5. skill 언어: A 한국어+goldstack 맞춤 / B 영어 원문 — 추천 A(goldstack skill이 모두 한국어) → 확정 A
6. 하드코딩: A 8개 전부 / B 위험한 3개 — 추천 A(같은 설정 파일을 읽는 작은 일들) → 확정 A
7. 답 되짚기: A v2에 / B v3로 — 추천 A(한 줄) → 확정 A
8. mod 위치: A goldstack 플러그인 안 / B 별도 플러그인 — 추천 A(설치 하나, 안 되면 B) → 확정 A
9. 보여 줄 실행: A 자동 선택 / B `/go` 세션만 — 추천 A(단순, 다른 세션에서도 보임) → 확정 A
10. 진행 계산: A gs가 계산 / B mod가 계산 — 추천 A(로직을 시험 가능한 Python에) → 확정 A, verify 변경
### 라운드 2 — 티켓 분해 (모두 추천대로)
사용자 질문: "왜 codex는 sandbox에서 돌아? 일반적으로 못 돌리는 이유가 있나?" → 무인 `codex exec`는 확인 질문을 못 하니 sandbox냐 전부 허용(`--dangerously-bypass-approvals-and-sandbox`)이냐 둘뿐이고, v0 3-1에서 codex 차단 장치는 sandbox였다. codex-cli 0.166에는 hook이 있지만 fail-open, Bash만 잡을 수 있음, 신뢰 절차가 걸려 확인이 필요하다 → v2는 sandbox 유지, "codex를 hook으로" 조사는 `.ideas/` 후보(확정 yes).
1. 티켓 8장(§5) / 2. 순서 01→02→03→04→{05,06}, 02→07, {05,06,07}→08 / 3. 모델: 01·03·04 codex, 02·05·06·07·08 claude, 리뷰는 반대 계열 / 4. 범위 밖 4개(legacy-work-path, notify-per-ticket, progress-eta-history, gitlab-support) → 확정

