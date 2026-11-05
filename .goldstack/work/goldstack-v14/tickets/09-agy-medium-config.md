---
id: "09"
title: "`/retro` 요약과 `small`을 Argon Medium으로"
blocked_by: []
touches: [".goldstack/config.toml"]
tier: small
model: claude
reviewer: codex
verify: "test \"$(uv run gs config models.agy)\" = \"gemini-4-argon-medium\" && test \"$(uv run gs config tiers.agy.large)\" = \"gemini-4-argon-high\""
---
## 목표
agy 공용 한도를 아끼도록 `/retro` 요약과 쓰이지 않는 `small`을 Argon Medium으로 옮긴다. 첫 리뷰는 High다.

## 완료 조건
- `.goldstack/config.toml`에서 `[models] agy`와 `[tiers.agy] small`이 `gemini-4-argon-medium`이다. `[tiers.agy] large`는 `gemini-4-argon-high`, `medium`은 그대로, `[tiers] review`는 그대로다.
- `gs check goldstack-v14`가 오류·경고 없다.

## 범위 밖
- `gs init` 기본값(`src/gs/config.py`).
- 첫 리뷰를 Medium으로 옮기는 일.

## 참고
- `.goldstack/ideas/agy-high-to-medium.md`
