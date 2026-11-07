---
id: "03"
title: "템플릿 §5 등급 설명에 코드+skill 글 티켓을 더한다"
blocked_by: []
touches: ["skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: ".venv/bin/python -m unittest discover -s tests -p test_skill_grill.py"
---
## 목표
코드와 상한 있는 skill 글을 함께 고치는 티켓을 `small`로 잡지 않게 한다.

## 완료 조건
- `skills/grill/templates/spec.md` §5 주석의 `tier` 설명에 코드와 상한 있는 skill 글을 함께 고치는 티켓은 `small`로 잡지 않는다는 문장과 근거(goldstack-v11 09)가 들어간다.
- `tests/test_skill_grill.py`가 이 문장을 확인한다.

## 범위 밖
- `skills/grill/SKILL.md` 본문과 단어 상한 변경

## 참고
- spec §3 2-8
- 아이디어 `grill-tier-skill-tickets`
