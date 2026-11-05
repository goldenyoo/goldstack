---
id: "12"
title: "상한 낮추기, 문서, CHANGELOG"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11"]
touches: ["tests/test_skills.py", "docs/guide.md", "docs/internals.md", "CHANGELOG.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && uv run python -m unittest discover -s tests -p test_overnight_skill.py && uv run python -m unittest discover -s tests -p test_profile_brief.py && claude plugin validate ."
---
## 목표
정리 결과에 맞춰 상한을 낮추고, 이번 feature의 동작 변경을 문서에 적는다.

## 완료 조건
- `WORD_LIMITS`의 값이 skill마다 실제 단어 수의 약 10% 위(10단위 올림)다. 예: 390단어 → 430.
- `docs/guide.md`에 수리 worker, `gs notify`, `grill` 인자 갈래, 단어 상한, `/idea` 형식 위치가 있고 옛 설명이 없다. `docs/internals.md`에 수리 단계와 상태가 있다.
- `CHANGELOG.md`의 `## 미출시`에 사람이 볼 변경이 있다.

## 범위 밖
- 버전 올리기: goldstack-v15 07.

## 참고
- spec 2-4
- `.goldstack/profile.md`의 주의점: 동작을 바꾸면 docstring과 internals를 고친다
