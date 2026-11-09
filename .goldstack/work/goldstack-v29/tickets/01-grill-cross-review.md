---
id: "01"
title: "grill 교차 검토와 실측 반례"
blocked_by: []
touches: ["skills/grill/SKILL.md", "skills/grill/templates/spec.md", "tests/test_skill_grill.py", "tests/test_skills.py"]
tier: medium
model: claude
reviewer: codex
verify: ".venv/bin/python -m unittest discover -s tests -p test_skill_grill.py && .venv/bin/python -m unittest discover -s tests -p test_skills.py"
---
## 목표
grill이 티켓 표를 확인받기 전에 다른 계열 모델의 읽기 전용 검토를 받고, 실측으로 선택지를 가를 때 그 안이 놓치거나 깨뜨릴 경우도 재게 한다.

## 완료 조건
- `skills/grill/SKILL.md` 1단계에 "실측이 선택지를 가르면 그 안이 놓치거나 깨뜨릴 경우도 함께 잰다"는 뜻의 문장이 있다.
- 5단계에서 표·범위 밖 목록을 확인받기 전에: grill 세션과 다른 계열 CLI(claude가 아닌 것, 예: `codex exec -s read-only`)가 spec·티켓 초안·관련 코드를 읽기 전용으로 대조한다. 지적은 grill 세션이 코드·실측으로 확인한 뒤 사람에게 보이고 반영한다. 결정을 바꾸는 지적은 그 결정을 다시 묻는다. 돌리지 못하면(CLI 없음, 한도 등) spec §7에 "교차 검토 못 함: <이유>"를 적고 진행한다. 특정 CLI를 필수로 가정하지 않는다(예시로만 든다).
- `skills/grill/templates/spec.md` §7 주석 또는 형식에 교차 검토 기록 자리(검토 모델, 지적, 확인 여부, 반영)가 있다.
- `tests/test_skill_grill.py`가 1단계 반례 문장, 5단계 교차 검토·"교차 검토 못 함" 문장을 단언한다. 문장을 지우면 시험이 실패한다.
- grill 상한은 지금 450, 지금 419단어다. 고친 뒤 단어 수의 약 10% 위(10단위 올림)로 `tests/test_skills.py` `WORD_LIMITS["grill"]`을 올리고 두 시험이 통과한다.

## 범위 밖
- 교차 검토를 돌리는 `gs` 명령(spec 1-3)
- 문서·버전(03)

## 참고
- spec §3 1-3·1-4·1-5, 아이디어 `grill-cross-family-review`·`grill-measure-counterexample`, v28 spec §7 "codex 검토 반영"
