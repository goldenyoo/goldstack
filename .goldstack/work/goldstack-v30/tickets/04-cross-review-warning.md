---
id: "04"
title: "spec 교차 검토 절이 비었으면 gs check가 경고한다"
blocked_by: []
touches: ["src/gs/check.py", "tests/test_check_cross_review.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
grill이 교차 검토를 빠뜨린 채 끝나지 않게, 템플릿의 `### 교차 검토` 절이 비어 있으면 `gs check`가 경고한다.

## 완료 조건
- feature에 티켓이 하나 이상 있고 spec에 `### 교차 검토`로 시작하는 제목이 있는데, 그 절(다음 `##`·`###` 제목 전까지)에 실제 표 행도 `교차 검토 못 함:`으로 시작하는 줄도 없으면 `경고: <spec 경로>: spec §7 교차 검토 기록이 없다(다른 계열 CLI로 읽기 전용 대조를 하거나 "교차 검토 못 함: <이유>"를 적는다)`를 낸다. 경고라서 종료 코드는 0이다.
- 실제 표 행은 머리 행과 `|---|` 구분 행을 뺀 행 중, 검토 모델·지적·확인·반영 칸(2–5번째)이 모두 비어 있지 않고 `<`로 시작하는 템플릿 자리표시(예: `<모델/effort>`)가 아닌 행이다. 주석(`<!-- … -->`) 안의 글자는 세지 않는다.
- 그 제목이 없는 spec(v0–v29)과 티켓이 없는 feature에서는 경고하지 않는다.
- 시험 `tests/test_check_cross_review.py`: 자리표시 행만 → 경고, 실제 행 하나 → 없음, 칸이 빈 행(`| 1 | | | | |`) → 경고, `교차 검토 못 함: codex 한도` → 없음, 제목 없음 → 없음, 티켓 없음 → 없음, 실제 행이 다음 절에만 있음 → 경고. 판정을 지우면 실패한다.

## 범위 밖
- `gs check --review`처럼 교차 검토를 gs가 직접 돌리는 것(`.goldstack/out-of-scope/grill-review-command.md`)
- grill skill 글 변경(이미 5단계에 교차 검토가 있다)
- touches 오류(03)

## 참고
- spec §3 1-6, 2-6, 3-2
- `skills/grill/templates/spec.md` §7
