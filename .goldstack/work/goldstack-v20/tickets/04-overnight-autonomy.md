---
id: "04"
title: "밤사이 판단 기본값을 config로"
blocked_by: ["03"]
touches: ["src/gs/config.py", "skills/overnight/SKILL.md", ".goldstack/config.toml", "tests/test_config.py", "tests/test_overnight_skill.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
되돌릴 수 있는 일은 추천대로 진행하고 기록하게 한다. 레포마다 켠다.

## 완료 조건
- `[overnight] autonomy`가 `stop`과 `record`를 받는다. 절이 없거나 `gs init`이 쓴 config는 `stop`이다. 다른 값은 `gs check` 오류다. `gs config overnight.autonomy`가 값을 낸다.
- 이 레포 `.goldstack/config.toml`은 `record`다.
- `skills/overnight/SKILL.md`가 두 값을 설명한다. `record`: 진행하는 일과 멈추는 일은 spec 결정 1-7대로이고, 스스로 정한 일은 `쓴 허락`에 이유와 되돌리는 법을 적는다. grill 결정을 뒤집어야 하면 그 feature만 `미실행`이다. `stop`: 지금 동작 그대로다. 단어 수가 `WORD_LIMITS` 아래다.

## 범위 밖
- 병합을 PR에서 멈추는 일(범위 밖 `overnight-pr-only`).

## 참고
- spec 결정 1-7.
