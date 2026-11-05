---
feature: goldstack-v15
verify: uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p && claude plugin validate . && uv build -q -o "$(mktemp -d)"
max_workers: 3
---
# goldstack-v15 — spec

상태: grill 완료(라운드 3개) · 2026-11-05 · 티켓 [tickets/](tickets/) · 범위 밖 [out-of-scope/](../../out-of-scope/)

결정과 grill 기록은 [goldstack-v12 spec](../goldstack-v12/spec.md)의 §3·§7에 있다. 이 feature의 결정 번호: 1-1, 1-2, 1-3, 1-7, 1-8, 2-20–2-23.

## 1. 목표
issue가 실제 반영과 맞게 열리고 닫히게 하고, 리뷰한 코드만 병합되게 한 뒤 `0.2.0`으로 올린다.

**완료 조건**: §5의 티켓이 병합되고 main 보고서 마무리 줄이 `verified`다. 세 버전 파일이 `0.2.0`이고 태그가 없다.

## 5. 티켓 그래프
경로 앞 `src/gs/`, `tests/`도 그대로 적었다. 계열: 병합·revert·재개는 claude opus와 두 번째 리뷰어, 작은 코드는 codex다.

| id | 제목 | blocked_by(이유) | wave | tier(이유) | 예상 | 구현 | 리뷰 계열 | touches | verify |
|---|---|---|---|---|---|---|---|---|---|
| 01 | issue와 아이디어 연결, 미분류 후보 | – | 1 | medium(새 키와 후보 표시) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/backlog.py`, `skills/grill/SKILL.md`, `skills/idea/**`, `tests/test_backlog.py`, `tests/test_skills.py` | 전체 |
| 02 | issue 닫기 구멍, 고친 버전, revert 뒤 다시 열기 | – | 1 | large(병합·revert) | 70분 | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `src/gs/finish.py`, `tests/test_issue_close.py` | 전체 |
| 03 | 닫힌 issue 재발 확인 | 02 앞 결과 필요 | 2 | medium(외부 쓰기 조건) | 40분 | codex gpt-6.1-sol/medium | claude opus/xhigh | `src/gs/feedback.py`, `tests/test_feedback_send.py` | 전체 |
| 04 | 리뷰한 SHA로 병합 | – | 1 | large(병합 경로) | 70분 | claude opus/xhigh | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `src/gs/go.py`, `src/gs/review.py`, `tests/test_review_target.py` | 전체 |
| 05 | 빈 자리 순서와 끊김 중 리뷰 준비 | 04 같은 파일 | 2 | medium(재개 흐름, 작은 수정) | 40분 | claude sonnet/high | codex gpt-6.1-sol/high + agy gemini-4-argon-high | `src/gs/go.py`, `src/gs/review.py`, `tests/test_async_review.py` | 전체 |
| 06 | push 설정 변경을 정리 경고로 넘기지 않기 | – | 1 | small(예외 분기 하나) | 15분 | codex gpt-6-luna/medium | claude opus/xhigh | `src/gs/clean.py`, `tests/test_clean.py` | 전체 |
| 07 | 문서, CHANGELOG, `0.2.0` | 01–06 앞 결과 필요 | 3 | small(문서와 버전) | 15분 | claude sonnet/medium | codex gpt-6.1-sol/high | `docs/guide.md`, `docs/internals.md`, `CHANGELOG.md`, `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` | 전체 |

일렬 경로 02→03→07 예상 125분 · 평균 동시 2.3

판단 모델 `opus`, 실패 요약 `haiku`. 예상은 v8–v11 등급별 중앙값(small 9, medium 38, large 69분)을 올림했다.

## 6. 환경 사실 (2026-11-05 확인)
- `finish._closing_numbers`, `_close_without_pr`가 닫기를 맡는다. `src/gs`에 issue를 다시 여는 코드는 없다.
- `feedback`의 재발 확인은 `gh issue list --state open`만 본다.
- 버전은 `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`에 `0.1.0`이다. `test_version_sync.py`가 있다.
- `go._merge_stage`는 브랜치 이름으로 `git merge --no-ff --no-commit`을 한다.
