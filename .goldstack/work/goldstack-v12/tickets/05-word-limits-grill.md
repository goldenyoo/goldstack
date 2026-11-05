---
id: "05"
title: "단어 상한 한 곳으로, grill 정리"
blocked_by: []
touches: ["tests/test_skills.py", "tests/test_overnight_skill.py", "tests/test_profile_brief.py", "skills/grill/**"]
tier: medium
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_overnight_skill.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && claude plugin validate ."
---
## 목표
단어 상한을 한 곳에 모으고, `grill` 글의 표 작성 규칙을 템플릿으로 옮겨 뒤 티켓이 쓸 여유를 만든다.

## 완료 조건
- `tests/test_skills.py`의 `WORD_LIMITS` 한 곳에 `grill`, `go`, `adopt`, `overnight`, `idea`, `retro`, `writing-for-agents`, `diagnosing-bugs`가 있다. 지금 숫자를 쓰고, 값이 없던 셋은 지금 단어 수보다 넉넉히 둔다. `test_overnight_skill.py`와 `test_profile_brief.py`, `/idea` 시험의 따로 있는 상한을 없앤다. 낡은 주석(`/go 400`)을 고친다.
- `skills/grill/SKILL.md` 본문이 420단어 이하다. 표 작성 규칙(일렬 경로, tier 이유, `blocked_by` 이유, 묶기, 두 번째 리뷰어, 티켓 `verify`)은 `skills/grill/templates/spec.md` §5 주석 한 곳에 있고 `grill`은 그것을 가리킨다.
- 두 번째 리뷰어 기준이 `docs/guide.md`와 같다: 상태 전이·재개·revert, 파일·브랜치 삭제, 차단 hook, 비밀, 데이터 마이그레이션(spec 2-6).
- `grill`이 인자를 `<f>`로 쓴다. 인자에 공백이 있으면 요청으로 읽고 라운드 1에서 feature 이름을 제안한다(spec 2-7).
- `grill`이나 템플릿에 규칙이 있다: skill 글을 고치는 티켓은 완료 조건에 상한과 지금 단어 수를 적고, 좁은 verify에 그 시험을 넣는다.
- `이렇게 읽었다`, frontmatter 동시 갱신, 라운드 형식처럼 실행을 바꾸는 지시는 그대로 남는다. 문구 시험은 책임에 맞게 옮긴다(`test_step_requires_criteria`, `test_spec_template_table`).

## 범위 밖
- 상한을 낮추는 일: 티켓 12.
- 표에 모델을 더하는 일: goldstack-v14 03.

## 참고
- spec 1-5, 2-4–2-7
- `.goldstack/ideas/skill-word-limit-visibility.md`
- skill 검토 결과: spec §7 라운드 1
