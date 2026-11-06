---
feature: goldstack-v20
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v20 — spec

상태: grill 완료(라운드 4개) · 2026-11-06 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
`gs go`가 도는 동안 다음 feature를 grill해 대기열에 붙이면 승인 창에 막히지 않고 이어 돈다. 사람이 없는 세션이 어디까지 해도 되는지 정해 둔다. worker가 다른 티켓의 검증을 죽이지 못하게 하고, 첫 worker가 전체 시험에 쓰는 시간을 없앤다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. 병합과 `gs self-update` 뒤 사람이 플러그인 경로에서 한 번 확인한다: `gs overnight arm`을 친 세션은 허용 규칙에 없는 명령이 사람 입력 없이 거부되고, 다른 세션은 창이 그대로 뜬다. 결과를 §6에 적는다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 실행 시점 | v17–v19 결과를 본 뒤 낮에 `/go goldstack-v20`으로 돌린다 | goldstack-v17 결정 1-2 |
| 버전 | 끝자리를 올린다. v20은 0.2.4 | goldstack-v17 결정 2-6 |
| 코디네이터 세션 | `gs go`가 스스로 다음 feature로 넘어가지 않는다. §6 재확인은 모델이 맡는다 | 범위 밖 `overnight-detached` |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | `mac-mini-feature-parallel` | 원격 운영의 남은 구멍만 다룬다(세션 재량, 재부팅 뒤 로그인 안내). 같은 머신 병렬과 로그 옮기기는 범위 밖이다 |
| 1-2 | 무인 세션의 재량 | 멈춘 실행은 읽어서 원인 후보를 적고 멈춘다. 회고·수정·재실행은 하지 않는다 |
| 1-3 | 대기열 | `/overnight add <f>`와 `gs overnight add`가 밤샘 파일 `결과` 표에 줄을 더한다. 코디네이터가 없으면 친 세션이 pid에 묶여 코디네이터가 된다 |
| 1-4 | 실행 중 grill 커밋 | 로컬에 두고 사이 단계에서 push 안 된 grill 커밋만 `git pull --rebase`로 올린다. 충돌하면 그 feature는 `미실행`이다 |
| 1-5 | 승인 창 | 플러그인 `PermissionRequest` hook. `gs overnight arm`을 친 그 세션에서만 거부한다. 거부는 기록해 `쓴 허락`에 옮긴다 |
| 1-6 | 사이 단계 묶기 | `gs overnight next <다음>`이 pull·재설치·`gs check`를 묶는다. 재설치 뒤 `gs check`는 새 프로세스로 부른다. §6 재확인과 spec 수정은 모델이 맡는다 |
| 1-7 | 밤사이 판단 | `[overnight] autonomy`. `gs init` 기본은 지금 동작(`stop`), 이 레포만 `record`. 되돌릴 수 있으면 진행하고 이유와 되돌리는 법을 적는다. force push, 태그·릴리스, 비밀, 다른 레포·외부 쓰기는 멈춘다. grill 결정을 뒤집어야 하면 그 feature만 `미실행`이다 |
| 4-1 | worker의 프로세스 다루기 | hook이 `pkill`·`killall`을 막는다. brief는 자기가 띄운 프로세스를 PID로 다루라고 적는다. `pgrep`은 읽기라 막지 않는다 |
| 4-2 | 첫 worker 전체 시험 | 계열과 상관없이 모든 첫 worker에서 뺀다. 뒤 실행에서 첫 검증 실패가 늘어 수리 시간이 줄어든 시간을 넘으면 되돌린다 |
| 4-3 | 두 번째 리뷰어 범위 | 코드 티켓 전부로 넓히지 않는다. 기준은 `skills/grill/templates/spec.md` 그대로다. goldstack-v18 결정 1-4의 시험을 닫는다 |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 무인 세션의 승인 창을 거부하는 hook | – | 1 | large(차단 hook) | 74분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `hooks/hooks.json`, `src/gs/hook.py`, `src/gs/overnight.py`, `src/gs/cli.py`, `tests/test_overnight_cmd.py`, `tests/test_hook.py` | 전체 |
| 02 | `/overnight add`와 코디네이터 묶기 | 01 같은 파일 | 2 | large(코디네이터 흐름과 skill 글) | 74분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/overnight.py`, `src/gs/cli.py`, `skills/overnight/SKILL.md`, `skills/go/SKILL.md`, `tests/test_overnight_cmd.py`, `tests/test_overnight_skill.py` | 전체 |
| 03 | `gs overnight next`로 사이 단계 묶기 | 02 같은 파일 | 3 | large(base를 옮기는 rebase) | 74분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/overnight.py`, `src/gs/cli.py`, `skills/overnight/SKILL.md`, `tests/test_overnight_cmd.py`, `tests/test_overnight_skill.py` | 전체 |
| 04 | 밤사이 판단 기본값을 config로 | 03 같은 파일 | 4 | medium(설정과 skill 글) | 59분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/config.py`, `skills/overnight/SKILL.md`, `.goldstack/config.toml`, `tests/test_config.py`, `tests/test_overnight_skill.py` | 전체 |
| 05 | 사람 없는 세션의 재량과 재부팅 안내 | – | 1 | medium(원격 프롬프트, 가짜 herdr 시험) | 59분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/remote.py`, `tests/test_remote.py` | 전체 |
| 06 | v20 문서와 버전 0.2.4 | 01–05, 07, 08 앞 결과 필요 | 5 | small(문서와 버전) | 25분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |
| 07 | worker hook이 `pkill`·`killall`을 막는다 | 01 같은 파일 | 2 | medium(차단 hook의 형태들) | 59분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/hook.py`, `tests/test_hook.py` | 전체 |
| 08 | 모든 첫 worker가 좁은 시험까지만 돌리고 자기 프로세스만 다룬다 | – | 1 | medium(모든 worker의 지시문) | 59분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/worker.py`, `src/gs/go.py`, `tests/test_fix_brief.py`, `tests/test_ticket_verify.py`, `tests/test_sandbox_brief.py` | 전체 |

계열: 코디네이터·hook·rebase라 claude로 짓고 codex가 본다. 틀리면 바로 사고인 01·07(차단 hook)·03(base 이동)에 agy를 붙인다. 최악 3장 × 3회 = 9회로 상한 24 안이다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→03→04→06 예상 306분(`large` 74분은 1장 표본, 08이 첫 worker 시간을 줄이는 효과는 넣지 않았다) · 평균 동시 1.6

## 6. 환경 사실 (2026-11-06 확인)
- 측정(이 grill, Claude Code 2.1.318, haiku, `manual` 모드, `--settings`로 건 hook, 1회): 허용 규칙에 없는 Bash에서 승인 창이 잠깐 떴고, 사람 입력 없이 `PermissionRequest` hook의 `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"deny","message":"…"}}}`가 닫았다. 명령은 돌지 않았고 세션은 이어졌다. hook 입력에 `session_id`가 있다. 플러그인 경로는 재지 않았다.
- code.claude.com 문서(2026-11-06, subagent가 옮김): 플러그인 `hooks/hooks.json`의 hook은 사용자·프로젝트 hook과 합쳐진다. `CLAUDE_SESSION_ID` 같은 세션 환경 변수는 문서에 없다. exit 2는 `PermissionRequest`를 거부하지 않는다. auto 모드는 3회 연속·20회 합계 차단 뒤 창으로 돌아간다. Bash 규칙은 Claude가 쓴 명령 글자에 맞춘다.
- `hooks/hooks.json`에는 `PreToolUse`만 있고 `GS_ROLE=worker`일 때만 `gs hook pretooluse`를 부른다.
- `.claude/settings.local.json`에 `Edit(/.goldstack/**)`, `Bash(gs self-update)`, `Bash(gs go *)`가 있다. `defaultMode` 키는 없고 허용 규칙은 33개다.
- `gs remote go`는 `herdr agent prompt <pane> "/go <feature>"`로 시작한다.
- 재부팅·잠자기 뒤 Claude 로그인은 재지 않았다.
- v19 병합 뒤(`398a301`, gs 0.2.3) 코드로 다시 봤다. `hooks/hooks.json`, 허용 규칙, `gs remote go`의 문장은 그대로다.
- skill 단어 수(본문): `overnight` 1604(상한 1710), `go` 495(상한 530). 02·03·04가 `overnight`에 함께 더하므로 여유 106단어 안에서 줄여 가며 쓴다.
- `src/gs/hook.py`의 `decide`는 `GS_ROLE=worker`일 때만 판정하고 `check_segment`가 명령 이름으로 가른다. `strip_prefix`가 `sudo`·`xargs` 같은 앞말을, `bash -c`는 재귀가 맡는다. `pkill`·`killall`은 지금 막지 않는다.
- `worker.write_brief`는 `narrow`이거나 티켓 `model`이 codex면 좁은 시험 규칙을 쓴다. `go.py`의 호출은 네 곳이다.
- `/retro` 결과: v17 04의 `pkill`이 01의 gs 검증을 죽였다(아이디어 `worker-machine-wide-kill`). v19 시험에서 agy만 찾은 fix 지적은 0건, 일렬 경로 약 14분 증가다(범위 밖 `second-reviewer-all-code`).

## 7. grill 기록
### 라운드 1 — 범위. goldstack-v17 라운드 1에서 함께 정했다.
### 라운드 2 — 설계 결정 (모두 추천대로)
1. `mac-mini-feature-parallel`: A 같은 머신 병렬 / B 남은 구멍만 / C 미룸 — 추천 B(파일이 겹쳐 나란히 못 돈다) → 확정 B
2. 무인 세션 재량: A 조사까지 / B 보고만 / C 회고까지 — 추천 A(읽기는 되돌릴 일이 없다) → 확정 A
3. 대기열: A `/overnight add` / B 만들지 않음 — 추천 A(목적 자체다) → 확정 A
4. 실행 중 grill 커밋: A 로컬 + rebase / B 사이 단계에서 커밋 — 추천 A(기록이 먼저 남는다) → 확정 A
5. 승인 창: A `PermissionRequest` hook / B `dontAsk` / C auto — 추천 A(잰 값이 있고 열린 세션에 쓴다) → 확정 A
6. 사이 단계 묶기: A `gs overnight next` / B 허용 규칙만 — 추천 A(규칙이 줄어 거부가 준다) → 확정 A
7. 밤사이 판단: A config로 켬 / B 모든 레포 / C 뒤집지 않음 — 추천 A(사람의 결정을 모델이 바꾸지 않고 환경을 가정하지 않는다) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
1. 티켓 6장(§5), 나누지 않음, 범위 밖 `same-machine-feature-parallel` → 확정

### 라운드 4 — `/retro goldstack-v17`, `v18`, `v19` 반영 (추천대로)
회고 후보 8개 중 사람이 추천대로 골랐다: 1·2·3·4는 아이디어 함, 6은 결정 기록, 1·3은 v20에 합침.
1. 프로세스 다루기: hook으로 막음 + brief 문장 → 확정, 티켓 07·08
2. 첫 worker 전체 시험: 모든 첫 worker에서 뺌(표본 v19 codex 2장) → 확정, 티켓 08. 범위 밖 `first-worker-no-verify`를 지움
3. 두 번째 리뷰어: 넓히지 않음 → 확정, 범위 밖 `second-reviewer-all-code`
4. 2(`verify-killed-by-signal`)와 4(`narrow-verify-config-ticket`)는 v20에 넣지 않고 열린 아이디어로 둔다
