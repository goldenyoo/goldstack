---
id: "10"
title: "문서, CHANGELOG"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
이번 feature의 동작 변경을 문서에 적는다.

## 완료 조건
- `docs/guide.md`에 `gs check`의 모델·실측 줄, `gs feedback --body-file`, `checked`, `문서 미반영`이 있고 옛 설명이 없다. `docs/internals.md`와 `CHANGELOG.md` 미출시가 맞는다.

## 범위 밖
- 코드 변경은 하지 않는다.

## 참고
- `.goldstack/profile.md` 주의점
