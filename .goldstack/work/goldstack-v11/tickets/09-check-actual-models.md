---
id: "09"
title: "gs check가 티켓마다 실제 모델을 보이고 grill 표가 그 값을 옮긴다"
blocked_by: []
touches: ["src/gs/check.py", "src/gs/cli.py", "skills/grill/SKILL.md", "skills/grill/templates/spec.md", "tests/test_check.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
사람이 티켓 분해를 확인할 때 등급이 어떤 모델과 effort로 풀리는지 config를 찾지 않고 보게 한다.

## 완료 조건
- 오류가 없으면 `gs check <feature>`가 기존 줄 뒤에 티켓마다 한 줄을 낸다. 예: `01 large claude opus/xhigh · 리뷰 codex gpt-6.1-sol/high`. `second_reviewer`가 있으면 `+ agy gemini-4-argon-high`처럼 잇는다.
- 값은 실제 실행과 같은 함수(`config`의 등급 풀이, 리뷰는 `tiers.review`)로 푼다. 첫 시도 값만 보인다. 재시도와 재리뷰 값은 보이지 않는다.
- 계열의 `tiers` 표가 없거나 등급이 없으면 `CLI 기본값`으로 적는다(리뷰는 `models`의 값이 있으면 그 값). effort가 없으면 모델만 적는다.
- `skills/grill/SKILL.md` 5단계: 표를 보이기 전에 티켓 frontmatter 초안을 쓰고 `gs check`의 값을 표의 구현·리뷰 칸에 옮긴다. 사람이 표를 고치면 초안도 고친다. `templates/spec.md` §5 예시가 같은 모양이다.
- 시험(`tests/test_check.py`): 표 있음, 표 없음, 두 번째 리뷰어, `--only` 범위, 오류가 있을 때 줄이 나오지 않음.

## 범위 밖
- `gs config`로 칸을 읽는 것(`tiers.claude.large`).
- 리뷰 등급 변경(spec 2-5).
- 문서(10).

## 참고
- spec §3의 1-11, `.goldstack/ideas/grill-table-actual-model.md`
