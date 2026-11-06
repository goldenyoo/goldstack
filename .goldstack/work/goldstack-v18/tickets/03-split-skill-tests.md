---
id: "03"
title: "tests/test_skills.py를 skill별 파일로 나눈다"
blocked_by: []
touches: ["tests/test_skills.py", "tests/test_skill_*.py", "tests/skill_support.py", "skills/grill/templates/spec.md", ".goldstack/profile.md"]
tier: small
model: claude
reviewer: codex
---
## 목표
글만 고치는 티켓이 `tests/test_skills.py` 때문에 줄을 서지 않게 한다. 동작은 바꾸지 않는다.

## 완료 조건
- 특정 skill을 보는 시험이 `tests/test_skill_<이름>.py`로 옮겨 간다. `WORD_LIMITS`와 모든 skill 공통 시험은 `tests/test_skills.py`에 남는다. spec들의 `verify`가 이 이름을 부르므로 파일을 없애지 않는다.
- 옮기기 전과 뒤의 시험 이름 집합이 같다. 바뀐 단언이 없다.
- `tests/test_profile_brief.py`와 `tests/test_overnight_skill.py`가 `test_skills`에서 가져오는 이름(`SKILLS`, `skill_frontmatter`, `steps`)을 그대로 가져올 수 있다.
- `skills/grill/templates/spec.md` §5 주석의 skill 글 규칙이 새 파일을 말한다. 상한을 바꿀 때만 `tests/test_skills.py`를 `touches`에 넣는다고 적는다. `.goldstack/profile.md` 시험 절에 나눈 파일을 적는다.

## 범위 밖
- 소스 파일 나누기. 새 시험 추가.

## 참고
- spec 결정 1-5, §6. skill 글 상한 `grill` 450을 넘지 않게 본문은 고치지 않는다.
