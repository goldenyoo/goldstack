---
id: "04"
title: "이 레포의 agy 재리뷰를 High로, 상한을 24로"
blocked_by: []
touches: [".goldstack/config.toml"]
tier: small
model: claude
reviewer: codex
verify: "uv run gs config agy.max_calls_per_run | grep -qx 24"
---
## 목표
v19의 두 번째 리뷰어 시험에 필요한 설정을 넣는다.

## 완료 조건
- `.goldstack/config.toml`의 `[tiers.agy]`에서 `small`과 `medium`이 `gemini-4-argon-high`다.
- `[agy] max_calls_per_run = 24`다. `[tiers] rereview`는 그대로다.
- `src/gs/config.py`의 `gs init` 기본값은 바꾸지 않는다.

## 범위 밖
- 기준 문서(`skills/grill/templates/spec.md`, `docs/guide.md`의 두 번째 리뷰어 기준)는 `/retro goldstack-v19` 결과를 본 뒤 고친다.

## 참고
- spec 결정 1-3, 아이디어 `agy-high-limit-rollout`.
