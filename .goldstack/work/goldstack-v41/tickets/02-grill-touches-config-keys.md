---
id: "02"
title: "grill 템플릿: touches grep에 바뀌는 설정 키를 더한다"
blocked_by: []
touches: ["skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_skill_grill.py && .venv/bin/python -m unittest discover -s tests -p test_skills.py"
---
## 목표
설정 키나 설정 항목 수를 바꾸는 티켓도 그 키를 단언하는 기존 시험을 touches에 넣도록 grill 템플릿이 안내한다. 그러면 리뷰 판단이 `defer`를 내고 티켓 검증이 반드시 실패하는 일(goldstack-v40 01)을 grill 단계에서 막는다.

## 완료 조건
- `skills/grill/templates/spec.md` §5 주석의 `touches:` 줄에 한 문장을 더한다. 설정 파일(예: `.goldstack/config.toml`)의 키를 바꾸거나 목록 항목 수를 바꾸는 티켓은 그 키 이름도 시험 폴더에서 grep하고, 나온 시험 파일을 touches에 넣는다. 예로 `[hook.worker_tests] deny`에 줄을 더하면 `deny`를 grep한다(`tests/test_config.py`가 개수를 단언한다)를 든다.
- `skills/grill/SKILL.md`와 `templates/ticket.md`는 고치지 않는다.
- `tests/test_skill_grill.py`가 spec 템플릿에 그 문장의 핵심 낱말(예: "설정 키")이 있다고 단언한다. 그 문장을 지우면 이 시험이 실패한다. 채운 템플릿이 `gs check`를 통과한다는 기존 시험은 그대로 통과한다.

## 범위 밖
- 판단이 `defer`를 내면 gs가 검증 전에 바로 수리로 보내는 것(`.goldstack/out-of-scope/defer-repair-before-verify.md`)

## 참고
- spec §3 결정 1-4, §6(v40 01의 `defer`)
