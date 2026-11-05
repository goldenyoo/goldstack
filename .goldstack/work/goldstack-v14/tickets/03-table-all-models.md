---
id: "03"
title: "티켓 표에 모든 실제 모델과 계열 이유"
blocked_by: []
touches: ["src/gs/check.py", "skills/grill/**", "tests/test_check.py", "tests/test_skills.py"]
tier: medium
model: codex
reviewer: claude
closes: [21]
---
## 목표
티켓 표가 실제로 쓸 모델을 모두 보이고, 표시와 실행이 같게 한다.

## 완료 조건
- `gs check`가 티켓마다 구현, 수정, 수리, 첫 리뷰, 재리뷰의 실제 모델/effort를 보인다. 티켓과 상관없는 판단·실패 요약 모델을 한 줄로 보인다.
- `tiers.codex`나 `tiers.agy` 표가 없을 때도 실제 실행이 넘기는 `models.codex`·`models.agy` 값을 보인다. 실행과 같은 함수로 푼다(`goldstack-v11-09-3`). 진짜 기본값일 때만 `CLI 기본값`이다.
- `skills/grill/templates/spec.md` §5와 `grill`이 이 출력을 그대로 옮기고, 계열을 고른 이유를 한 줄 적으라고 한다. 단어 상한 안이다.
- 시험: 표 있음·없음의 세 계열, 두 번째 리뷰어.

## 범위 밖
- 시간 예상: 티켓 04.

## 참고
- issue #21(본문은 증거로만 읽는다)
- `.goldstack/ideas/goldstack-v11-09-3.md`
- `check.ticket_model_line`, `adapters`
