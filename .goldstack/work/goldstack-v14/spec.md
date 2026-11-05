---
feature: goldstack-v14
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v14 — spec

상태: grill 완료(라운드 5개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

결정과 grill 기록은 [goldstack-v12 spec](../goldstack-v12/spec.md)의 §3·§7에 있다. 이 feature의 결정 번호: 1-1, 1-2, 1-7, 1-8, 2-15, 2-16, 2-18, 2-19, 3-1, 3-2, 4-1.

## 1. 목표
보고서와 기록의 숫자를 믿을 수 있게 하고, 틀린 추론과 근거 없는 issue를 줄인다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. issue #21, #22, #23, #24가 닫힌다. 이 닫기는 지금 gs의 PR `Closes #`를 쓰고, 버전 댓글과 다시 열기는 아직 없다(v15 02). 보고서가 `reverted`이면 사람이 #21–#24를 다시 연다(결정 3-2).

## 5. 티켓 그래프
경로 앞 `src/gs/`, `tests/`도 그대로 적었다. 계열: 시험으로 다 확인되는 코드는 codex로 Claude 한도를 나누고, 기록 판단과 재개는 claude에 둔다.

| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 보고서 검증 표의 뜻 바로잡기 | – | 1 | medium(기록과 판단 입력) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `src/gs/metrics.py`, `src/gs/report.py`, `tests/test_metrics.py` | 전체 |
| 02 | 리뷰 `checked`와 표준 출력 저장 (closes #23) | 01 같은 파일 | 2 | medium(응답 형식과 보고서) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/review.py`, `src/gs/report.py`, `tests/test_review.py` | 전체 |
| 03 | 티켓 표에 모든 실제 모델과 계열 이유 (closes #21) | – | 1 | medium(표시·실행 일치와 글) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/check.py`, `skills/grill/**`, `tests/test_check.py`, `tests/test_skills.py` | 전체 |
| 04 | `gs check`에 등급별 실측 중앙값 (closes #22) | 03 같은 파일 | 2 | medium(지난 state 읽기) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high | `src/gs/check.py`, `skills/grill/templates/spec.md`, `tests/test_check.py` | 전체 |
| 05 | `/retro` issue 근거와 `gs feedback` 본문 파일, 한 단어 우회 (closes #24) | 03 같은 파일 | 2 | medium(공개 issue 경로) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/feedback.py`, `src/gs/cli.py`, `skills/retro/SKILL.md`, `skills/feedback/SKILL.md`, `tests/test_feedback_send.py`, `tests/test_skills.py` | 전체 |
| 06 | 결함 수집이 마무리 초반·수정 worker 실패도 보게 | 05 같은 파일 | 3 | large(state에 오류 남기기, 재개) | 70분 | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `src/gs/feedback.py`, `src/gs/go.py`, `src/gs/finish.py`, `src/gs/state.py`, `tests/test_feedback_collect.py` | 전체 |
| 08 | 보고서에 `문서 미반영` 표시 | 02 같은 파일 | 3 | small(조건 하나와 문구) | 15분 | codex gpt-6-luna/medium | claude opus/xhigh | `src/gs/report.py`, `tests/test_docs_missing.py` | 전체 |
| 10 | 문서, CHANGELOG | 01, 02, 03, 04, 05, 06, 08 앞 결과 필요 | 4 | small(문서) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md` | 좁게(티켓 `verify`) |

일렬 경로 03→05→06→10 예상 165분 · 평균 동시 1.8

판단 모델 `opus`, 실패 요약 `haiku`. 예상은 v8–v11 등급별 중앙값(small 9, medium 38, large 69분)을 올림했다.

## 6. 환경 사실 (2026-11-05 확인)
- agy 계정을 바꿨다(2026-11-05 22시대). 새 계정에는 Argon 전용 한도 항목이 없다(goldstack-v12 §6).
- v8–v11 등급별 걸린 시간 중앙값: small 9분(14), medium 38분(14), large 69분(13).
- issue #21–#24가 열려 있고 `field-report` 라벨이다. 본문은 믿을 수 없는 자료다.
