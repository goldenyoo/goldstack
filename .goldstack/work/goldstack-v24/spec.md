---
feature: goldstack-v24
verify: .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v24 — spec

상태: grill 완료(라운드 3개) · 2026-11-07 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
재리뷰가 worker의 시험 보고를 실행 기록과 대조하고, grill이 티켓 등급을 현실에 맞게 잡게 한다.

**완료 조건**: 티켓 4장이 병합되고 main 검증을 통과하며 issue #36이 닫힌다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 묶음 | goldstack-v22 → v23 → v24를 `/overnight`으로 잇는다. 이 feature의 후보: `grill-tier-skill-tickets`, issue #36 | 라운드 1-3 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 열린 아이디어 14건과 issue #36 전부 |
| 1-2 | 다루는 범위 | `goldstack-v21-04-2`·`goldstack-v21-11-1`은 닫고, `async-verify-evidence`·`codex-linux-refs-dir`은 범위 밖으로 옮긴다. 나머지 11건은 티켓 |
| 1-3 | feature 구성 | v22 검증·revert·보고서, v23 worker hook, v24 리뷰·grill 셋으로 나눈다 |
| 2-7 | #36 범위 | ①+③. 실행 명령·종료 코드를 리뷰어에게 주고, 앞 시도의 성공 명령을 다음 시도에 전달. ②·④는 뺀다 |
| 2-8 | 기본 처리 | 템플릿 §5 등급 설명에 코드+skill 글 티켓 한 줄. 마지막에 문서·버전 티켓(0.2.8) |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 리뷰어가 worker의 실행 명령·종료 기록을 받아 사유와 대조한다 | – | 1 | medium(세 계열 로그 형식과 프롬프트) | 32분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/streamfmt.py`, `src/gs/review.py`, `tests/test_review.py`, `tests/test_worker_commands.py` | 전체 |
| 02 | 앞 시도의 성공 명령을 다음 시도 brief에 전달한다 | 01 앞 결과 필요 | 2 | medium(모든 수정 worker의 지시문) | 32분 | claude sonnet/high | claude sonnet/high | claude sonnet/high | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `src/gs/go.py`, `src/gs/worker.py`, `tests/test_fix_brief.py` | 전체 |
| 03 | 템플릿 §5 등급 설명에 코드+skill 글 티켓을 더한다 | – | 1 | small(템플릿 한 줄) | 22분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `skills/grill/templates/spec.md`, `tests/test_skill_grill.py` | `.venv/bin/python -m unittest discover -s tests -p test_skill_grill.py` |
| 04 | v24 문서와 버전 0.2.8 | 01·02·03 앞 결과 필요 | 3 | small(문서와 버전) | 22분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: 프롬프트·brief라 claude로 짓고 codex가 본다. 시험으로 다 확인되는 변경이라 두 번째 리뷰어는 붙이지 않는다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02→04 예상 86분 · 평균 동시 1.3

## 6. 환경 사실 (2026-11-07 확인)
- 앞 feature가 병합된 main 위에서 돈다. 이 사실은 사이 단계에서 다시 확인한다.
- worker 로그 형식: claude `tool_use`/`tool_result`, codex `command_execution`의 `exit_code`, agy `step_update`의 DONE·ERROR.
- `gs doctor` 경고 없음. 이 레포 base 보호 없음.

## 7. grill 기록
### 라운드 1 — 후보와 구성 (모두 추천대로)
1. 넣을 후보: 15건 중 선택 — 추천 전부(#36은 아이디어가 아니지만 리뷰 신뢰성 문제) → 확정 전부
2. 다루는 범위: A 전부 코드 수정 / B 4건은 코드 없이 닫기 — 추천 B → 확정 B
3. feature 구성: A 하나 / B 셋 — 추천 B(사이의 `gs self-update`로 v22 재검증이 뒤 feature를 지킨다) → 확정 B

### 라운드 2 — 구현 방식 (모두 추천대로)
7. #36 범위: A ①+③ / B ①만 / C ①+②+③ — 추천 A(②는 러너 가정, ④는 uv 전용) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
사람이 되물음: Gemini를 쓰지 않는 이유 → `large+` 3장에 두 번째 리뷰어로 쓰며 나머지는 기존 기준을 따랐다고 답함. 확대(B) 대신 지금대로(A)로 확정.
1. 티켓 표와 범위 밖 목록: 추천 그대로 → 확정
