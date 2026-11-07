---
id: "09"
title: "/retro의 agy 호출에서 권한 플래그를 뺀다"
blocked_by: []
touches: ["skills/retro/SKILL.md", "docs/guide.md", "tests/test_skill_retro.py"]
closes: [33]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skill_retro.py && uv run python -m unittest discover -s tests -p test_skills.py"
---
## 목표
auto mode에서 `/retro`의 agy 요약이 거부되는 일을 없애고, 신뢰할 수 없는 로그를 읽는 모델의 권한을 줄인다.

## 완료 조건
- `skills/retro/SKILL.md`와 `docs/guide.md`의 agy 명령이 `agy -p "<프롬프트>" --sandbox --disable-slash-commands --model "$model"`이고 `--dangerously-skip-permissions`가 없다.
- "`--sandbox`가 workspace를 읽기 전용으로 만든다"는 설명을 실제 동작에 맞춘다. 쓰기와 셸은 headless `-p`의 자동 거부로 막힌다.
- 실패 판정에 답이 `no output produced`를 담는 경우가 더해져, 다시 부르지 않고 직접 읽는 방식으로 간다.
- `tests/test_skill_retro.py`가 플래그 없음과 새 실패 판정을 단언한다.
- `retro` 상한 930, 지금 850이다. 상한을 바꾸지 않는다.

## 범위 밖
- `src/gs/review.py`의 agy 리뷰어 플래그: 이번 범위가 아니다.

## 참고
- spec 결정 2-9, §6의 agy 측정. `docs/research/agy.md`.
