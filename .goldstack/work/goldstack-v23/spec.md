---
feature: goldstack-v23
verify: .venv/bin/python -m unittest discover -s tests -p test_skills.py && .venv/bin/python -m unittest discover -s tests -p test_feedback_format.py && ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v23 — spec

상태: grill 완료(라운드 3개) · 2026-11-07 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

## 1. 목표
worker hook의 `=` 확장 판정에서 놓침과 오차단을 줄인다.

**완료 조건**: 티켓 2장이 병합되고 main 검증을 통과한다. 티켓 01의 입력별 판정이 시험으로 확인된다.

## 2. 이미 정해진 것
| 항목 | 결정 | 근거 |
|---|---|---|
| 묶음 | goldstack-v22 → v23 → v24를 `/overnight`으로 잇는다. 이 feature의 후보: `goldstack-v21-07-1`, `goldstack-v21-07-3`, `goldstack-v21-07-4` | 라운드 1-3 |

## 3. 결정
| # | 항목 | 결정 |
|---|---|---|
| 1-1 | 넣을 후보 | 열린 아이디어 14건과 issue #36 전부 |
| 1-2 | 다루는 범위 | `goldstack-v21-04-2`·`goldstack-v21-11-1`은 닫고, `async-verify-evidence`·`codex-linux-refs-dir`은 범위 밖으로 옮긴다. 나머지 11건은 티켓 |
| 1-3 | feature 구성 | v22 검증·revert·보고서, v23 worker hook, v24 리뷰·grill 셋으로 나눈다 |
| 2-6 | hook 판정 | 최소 수정. 따옴표 있는 숫자 종료자 허용, `eval`·`zsh -c`·`$(...)` 본문 검사(`bash -c`·`sh -c` 제외), `""===` 잡기 |
| 2-8 | 기본 처리 | 마지막에 문서·버전 티켓(0.2.7) |

## 5. 티켓 그래프
| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 수정 | 수리 | 첫 리뷰 | 재리뷰 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | worker hook의 = 판정에서 놓침과 오차단을 줄인다 | – | 1 | large(차단 hook) | 57분 | claude opus/xhigh | claude opus/xhigh | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | codex gpt-6.1-sol/medium + agy gemini-4-argon-high | `src/gs/hook.py`, `tests/test_hook.py` | 전체 |
| 02 | v23 문서와 버전 0.2.7 | 01 앞 결과 필요 | 2 | small(문서와 버전) | 22분 | claude sonnet/medium | claude sonnet/medium | claude sonnet/medium | codex gpt-6.1-sol/high | codex gpt-6.1-sol/medium | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `tests/test_version.py` | 전체 |

계열: hook이라 claude로 짓고 codex가 본다. 차단 hook인 01에 agy를 붙인다.

공통 모델: 판단 claude opus · 실패 요약 claude haiku

일렬 경로 01→02 예상 79분 · 평균 동시 1.0

## 6. 환경 사실 (2026-11-07 확인)
- 앞 feature가 병합된 main 위에서 돈다. 이 사실은 사이 단계에서 다시 확인한다.
- `hook.decide` 실측: `cat <<'123'` 본문 `===` 차단, `eval`·`zsh -c`·`""===` 통과, `foo\ ===` 통과.
- `gs doctor` 경고 없음. 이 레포 base 보호 없음.

## 7. grill 기록
### 라운드 1 — 후보와 구성 (모두 추천대로)
1. 넣을 후보: 15건 중 선택 — 추천 전부(#36은 아이디어가 아니지만 리뷰 신뢰성 문제) → 확정 전부
2. 다루는 범위: A 전부 코드 수정 / B 4건은 코드 없이 닫기 — 추천 B → 확정 B
3. feature 구성: A 하나 / B 셋 — 추천 B(사이의 `gs self-update`로 v22 재검증이 뒤 feature를 지킨다) → 확정 B

### 라운드 2 — 구현 방식 (모두 추천대로)
6. hook 판정: A 최소 수정 / B 파서 재작성 — 추천 A(차단 hook은 틀리면 바로 사고) → 확정 A

### 라운드 3 — 티켓 분해 (모두 추천대로)
사람이 되물음: Gemini를 쓰지 않는 이유 → `large+` 3장에 두 번째 리뷰어로 쓰며 나머지는 기존 기준을 따랐다고 답함. 확대(B) 대신 지금대로(A)로 확정.
1. 티켓 표와 범위 밖 목록: 추천 그대로 → 확정
