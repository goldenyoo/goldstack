---
id: "04"
title: "grill 템플릿: 수치 기준의 우선순위와 재측정"
blocked_by: []
touches: ["skills/grill/templates/ticket.md", "skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skill_grill.py && .venv/bin/python -m unittest discover -s tests -p test_skills.py"
---
## 목표
grill이 정한 수치 완료 기준이 다른 조건과 부딪혀 수정을 더 돌거나, worker 혼자 잰 값으로 끝나지 않게 템플릿이 안내한다.

## 완료 조건
- `skills/grill/templates/ticket.md` 완료 조건 주석에 결정 2-3의 두 문장이 들어간다: (1) 수치 상한이 정확성 같은 다른 조건과 부딪힐 수 있으면 어느 쪽이 우선인지 함께 적는다. (2) 측정형 기준은 재는 명령을 함께 적고, 시험으로 단언할 수 있으면 시험으로, 못 하면 "리뷰어가 이 명령으로 다시 잰다"를 완료 조건에 넣는다.
- `skills/grill/templates/spec.md` §3 결정 주석에 수치 결정이면 우선순위와 재는 방법을 함께 적으라는 한 줄.
- `skills/grill/SKILL.md`는 고치지 않는다.
- `tests/test_skill_grill.py`가 두 템플릿에 그 문장의 핵심 낱말(예: "우선", "다시 잰다")이 있음을 단언한다. 문장을 지우면 실패한다. 채운 템플릿이 `gs check`를 통과하는 기존 시험은 그대로 통과한다.

## 범위 밖
- gs가 측정 명령을 돌리는 `measure:` 키(결정 2-3)

## 참고
- spec §3 결정 2-3. goldstack-v39 04(git 2회 조건과 정확성 충돌, 8630회 재측정 없음)
