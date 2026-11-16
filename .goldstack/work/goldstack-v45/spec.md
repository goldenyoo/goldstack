---
feature: goldstack-v45
verify: uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
verify_retries: 1
---
# goldstack-v45 — spec

상태: grill 완료(라운드 3개) · 2026-11-16 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
worker가 남긴 관찰이 수정 루프로 새거나 사라지지 않고, 덜 끝난 실행이 마무리 줄에서 보이게 한다. 관찰 = worker가 마지막 메시지 `## 남긴 관찰`에 적는 줄.

**완료 조건**: 티켓이 모두 병합되고 전체 검증이 통과한다. (1) brief가 touches 안 결함·완료 조건 위반을 관찰로 남기지 말고 고치라고 말한다. (2) 앞 티켓에서 "범위 밖"으로 판정된 관찰 중 경로가 아직 시작하지 않은 티켓의 touches에 걸리는 것이 그 티켓 brief에 실린다. (3) 보고서 관찰 표가 그 티켓의 모든 worker 로그를 읽는다. (4) 덜 끝난 실행(일부 병합, 미해결·재현된 미수리 지적)의 마무리 줄에 그 사실이 붙는다. 각 항목은 티켓의 시험으로 확인한다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| feature 이름 | `goldstack-v45` | 라운드 1-1 |
| 범위 판단 | 넣을 후보를 Fable 5.2 high 세션에 맡겨 그 답을 grill 세션이 코드로 확인한 뒤 정했다 | 사람 요청(라운드 1-2) |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | feature 이름 | `goldstack-v45` |
| 1-2 | 넣을 후보 | `worker-fix-in-scope-observations`, `observation-handoff-to-ticket`(앞·뒤 절반 모두), `grill-criteria-vs-profile`, `verified-partial-label`, `wt-integration-vanish-parallel`(시험 git 환경의 `maintenance.auto=false` 한 줄 수리만, 원인 확정 아님). `ci-tests-job-red-unread`는 뺀다(PR #82 뒤 5연속 성공, 남은 것은 config 결정). 처음 추천(1·2·3·10)과 다르다 |
| 1-3 | spec 기본값 | goldstack-v44와 같다(전체 verify, `max_workers: 3`, `verify_retries: 1`, 병렬 6) |
| 2-1 | 관찰을 하류 티켓에 보내는 기준 | 관찰 글 속 경로를 아직 시작하지 않은 티켓의 touches(glob)와 맞춘다. 리뷰어 이유의 티켓 id는 보지 않는다. 맞는 티켓이 없거나 이미 시작했으면 보고서에만 남는다 |
| 2-2 | 보고서 관찰 표가 읽는 로그 | 그 티켓의 모든 worker 로그(첫 worker·수정·수리). 같은 글은 한 번 |
| 2-3 | 마무리 줄 형식 | phase 값은 그대로 두고, 덜 끝났을 때만 뒤에 붙인다. 예: `마무리: verified · 티켓 3/4 병합 · 미해결 2 · PR … 병합`. `gs go` 끝 출력 `■ 마무리:`도 같다 |
| 2-4 | 문서 티켓 verify 기준 | grill 티켓(04)에 묶는다. 템플릿 §5에 "문서 티켓의 좁은 verify에 그 문서 파일 이름을 시험 폴더에서 grep해 나온 시험을 넣는다"를 더한다 |
| 3-1 | 티켓 표 | §5대로 확정. 교차 검토 5건 반영 뒤(결정 2-3은 phase `verified`일 때만으로 좁혔다) |
| 3-2 | 기록 | taken: `worker-fix-in-scope-observations`·`observation-handoff-to-ticket`·`grill-criteria-vs-profile`·`verified-partial-label`. 열어 두고 덧붙임: `wt-integration-vanish-parallel`(05는 위생 수리, 원인 미확인)·`ci-tests-job-red-unread`(PR #82 뒤 5연속 성공, config `checks`는 그대로). 새 범위 밖 파일 없음 |

## 4. 형식
- 하류 brief에 실리는 관찰: 믿을 수 없는 자료로 표시한 절 하나. 줄마다 `<출처 티켓 id>: <관찰 글>`. 실을 관찰이 없으면 절이 없다.
- 마무리 줄 덧붙임: `티켓 <병합>/<전체> 병합`(병합 < 전체일 때), `미해결 <n>`·`재현된 미수리 <n>`(0보다 클 때). 다 끝난 실행의 줄은 지금과 같다.

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | brief: touches 안 결함·완료 조건 위반은 고친다 | – | 1 | small(규칙 문장 하나와 시험) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `tests/test_brief_rules.py`, `tests/test_fix_brief.py`, `tests/test_review_observations.py` | 전체 |
| 02 | 보고서: 관찰 표 모든 로그, 덜 끝난 verified 표시 | – | 1 | medium(보고서 두 곳과 `gs go` 끝 출력, 단언 시험 여럿) | 35분 | codex gpt-6-astra/high | codex gpt-6-astra/high | codex gpt-6-astra/high | claude opus/xhigh | claude sonnet/high | `src/gs/report.py`, `src/gs/go.py`, 시험 12개(티켓 파일) | 전체 |
| 03 | 범위 밖 관찰을 하류 티켓 brief에 | after 01·02 같은 파일(`worker.py`·`go.py`·`report.py`) | 2 | medium(리뷰 기록 읽기와 brief 구성, 새 시험 파일) | 35분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `src/gs/worker.py`, `src/gs/go.py`, `src/gs/report.py`, `tests/test_brief_rules.py`, `tests/test_observation_handoff.py` | 전체 |
| 04 | grill: profile 충돌 대조, 문서 티켓 verify 기준 | – | 1 | small(skill 글 한 문장, 템플릿 한 문장) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `skills/grill/SKILL.md`, `skills/grill/templates/spec.md`, `tests/test_skill_grill.py` | `test_skill_grill`·`test_skills` + plugin 검사 |
| 05 | 시험 공용 git 환경 `maintenance.auto=false` | – | 1 | small(시험 fixture 한 곳) | 13분 | codex gpt-6-luna/medium | codex gpt-6-luna/medium | codex gpt-6-luna/medium | claude opus/xhigh | claude sonnet/high | `tests/support.py`, `tests/test_jail.py`, `tests/test_support_git.py`, `tests/test_environment.py`, `tests/test_sandbox_launch.py` | 전체 |
| 06 | 문서·버전 0.2.28 | 01–05 앞 결과 필요 | 3 | small(문서와 버전) | 13분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6-astra/xhigh | codex gpt-6-astra/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | `test_version`과 문서 이름 단언 시험 6개 + plugin 검사 |

계열: 01·04·06은 한국어 글(brief 규칙, skill, 문서)이 결과물이라 claude 구현·codex 리뷰. 02·05는 touches가 좁고 시험으로 닫히는 코드·fixture라 codex 구현·claude 리뷰. 03은 코디네이터가 리뷰 기록을 읽어 brief를 구성하는 흐름이라 claude 구현·codex 리뷰. 상태 전이·삭제·hook·비밀을 바꾸는 티켓이 없어 두 번째 리뷰어는 없다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 02→03→06 예상 83분 · 평균 동시 1.5

## 6. 환경 사실 (2026-11-16 확인)
- gs 0.2.27, 레포 버전 0.2.27(`pyproject.toml`).
- `worker.OBSERVATIONS_RULE`(`src/gs/worker.py:54`)은 goldstack-v42 01 이전 그대로다. 병합되지 않은 v42 01 커밋 `38b83f7`(`worker.py` +4/−2, `tests/test_brief_rules.py` +8)이 브랜치 `gs/goldstack-v42/01`에 남아 있다.
- 보고서 관찰 표 `report.observation_table`(`src/gs/report.py:571`)은 티켓마다 `latest_worker_log`(`:540`) 하나만 읽는다. 수정 worker가 있으면 그 로그다. goldstack-v43 02의 "05 범위" 관찰이 보고서에서 빠진 까닭이다(Fable 세션 보고, 코드는 이 세션이 확인).
- `docs/internals.md:148`·`:654`가 지금도 없는 `go._verifying_again`과 `_mark_resume(verify_again=True)`를 적는다.
- 관찰 판정은 리뷰 기록의 `observation_verdicts`([{n, verdict(지적|수용|범위 밖), reason}], `review.py:681`·`:750`)에 있다.
- 첫 worker brief는 `go.py:1897` `worker.write_brief(..., merged=_base_tickets(r, base))`가 쓴다. 재개는 `go.py:1823`.
- 마무리 줄: 보고서 `report.status_line`(`report.py:826`), `gs go` 끝 `go._summary`의 `■ 마무리: {_outcome(r)}`(`go.py:3593`). 텔레그램 `_message`는 이미 `티켓 n/m`을 쓴다(`go.py:3636`). `마무리: verified`를 단언하는 시험 파일 10개.
- grill SKILL 본문 495단어, 상한 550(`tests/test_skills.py` `WORD_LIMITS`).
- `maintenance.auto=false`는 `tests/test_jail.py:26`에만 있고 `tests/support.py`(GoTest 환경 `GIT_CONFIG_GLOBAL=/dev/null`, `isolate_git_env`)에는 없다. git 2.54의 `git push`가 로컬 bare 양쪽에서 `git maintenance run --auto --detach`를 띄운다(Fable 세션이 `GIT_TRACE=1`로 확인, 이 세션은 다시 돌리지 않음).
- CI `tests` job: PR #82 병합 전 27회 중 11회 실패, 병합 뒤 5회 연속 성공(`gh run list --workflow tests.yml`).
- 문서 이름을 단언하는 시험(`grep -rlE 'guide\.md|internals\.md' tests`): `test_skill_retro`, `test_review_touches_outside`, `test_docs_missing`, `test_fix_brief`, `test_sandbox`, `test_skill_grill`.

## 7. grill 기록
### 라운드 1 — 범위 (2번은 추천과 다름)
사람이 2번을 Fable 5.2 high 세션에 물어 그 답으로 정해 달라고 했다. Fable 답(1·3·9·10 + 선택 7, 2 제외)의 근거를 이 세션이 코드·`gh`로 확인했다(§6). Fable이 남긴 질문 셋은 이 세션이 정했다: 3의 뒤 절반 포함(빼면 v43 문서 결함이 다시 main에 남는다), 7은 원인 확정 없이 한 줄 수리로 포함하고 아이디어는 열어 둔다, 2의 config `checks` 변경은 하지 않는다. Fable 세션의 `git cherry-pick -n` 시도는 권한 단계에서 거부됐고 `git status`는 그대로였다.
1. feature 이름: A `goldstack-v45` — 추천 A → 확정 A
2. 넣을 후보(열린 아이디어 12): 추천 1·2·3·10 → 확정 1·3·7·9·10(Fable 답 기반)
3. spec 기본값: A v44와 같게 / B 바꾼다 — 추천 A(v44 실측 뒤 바뀐 조건 없음) → 확정 A

### 라운드 2 — 세부 (모두 추천대로)
4. 관찰을 보낼 하류 티켓: A 관찰 글 속 경로 ↔ 아직 시작 안 한 티켓 touches / B 리뷰어 이유의 티켓 id — 추천 A(결정적, 리뷰어 글에 기대지 않음) → 확정 A
5. 보고서 관찰 표의 로그: A 모든 worker 로그(중복 제거) / B 첫 + 최근 — 추천 A(수정이 둘 이상이면 B는 중간 관찰을 놓친다) → 확정 A
6. 마무리 줄: A 덜 끝났을 때만 덧붙임 / B phase `verified_partial` — 추천 A(B는 `clean.py`·`cli.py`·`go.py` 판정과 시험 17곳이 흔들린다) → 확정 A
7. 문서 티켓 verify 기준: A 9번 티켓에 묶음 / B 따로 — 추천 A(같은 grill 글, 템플릿이라 단어 상한 밖) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
교차 검토(아래 표)를 반영한 뒤 물었다.
8. 티켓 표: A 맞다 / B 고친다 — 추천 A → 확정 A
9. 기록(taken 4, 덧붙임 2, 새 범위 밖 0): A 맞다 / B 고친다 — 추천 A → 확정 A

### 교차 검토 (2026-11-16)
| # | 검토 모델 | 지적 | 확인(코드·실측) | 반영 |
|---|---|---|---|---|
| 1 | codex(CLI 기본 모델) read-only | 03이 재개 brief에도 싣라면서 이미 시작한 티켓은 제외해 어긋난다 | 재개는 기존 worktree에서 `resumed=True`로 brief를 다시 쓴다(`go.py:1823`, 확인) | 반영함: 새로 시작하는 worker brief만. 재개·수정·수리 brief는 범위 밖 |
| 2 | 같음 | 03이 가장 최근 회차만 보면 첫 리뷰의 `범위 밖` 판정이 재리뷰 뒤 사라진다 | 재리뷰 회차는 그 회차에 실은 관찰만 남긴다(`review._keep_round`, 확인) | 반영함: 모든 회차·두 리뷰어, 같은 글 한 번. 시험에 그 경우를 넣었다 |
| 3 | 같음 | 03 완료 조건이 02 결과(보고서 표)를 요구하는데 `after`라 02 실패에도 돈다 | `after` 의미(템플릿 §5, 확인) | 반영함: 그 문장을 완료 조건에서 빼고 범위 밖에 "보고서 관찰 표(02)" |
| 4 | 같음 | 05가 `GIT_CONFIG_COUNT` 방식이면 `test_environment.py`·`test_sandbox_launch.py`가 깨지는데 touches에 없다 | `tests/test_environment.py:22–33`, `tests/test_sandbox_launch.py:313`(확인) | 반영함: touches에 둘, 단언이 지키는 뜻은 유지 |
| 5 | 같음 | 02의 "기존 시험 수정 없이 통과"가 `마무리: not_merged · merged 티켓 없음` 단언과 부딪힌다 | `tests/test_final_report_on_base.py:46–47`(확인) | 반영함: 덧붙임은 phase `verified`일 때만(결정 2-3의 취지대로 좁힘). 덜 끝난 verified 단언 시험은 고친다 |

