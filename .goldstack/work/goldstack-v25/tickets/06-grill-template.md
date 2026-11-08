---
id: "06"
title: "grill 템플릿에 문서·버전 티켓의 좁은 검증과 완료 조건 점검을 더한다"
blocked_by: []
touches: ["skills/grill/templates/spec.md", "skills/grill/templates/ticket.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
verify: ".venv/bin/python -m unittest discover -s tests -p test_skill_grill.py"
---
## 목표
문서·버전 티켓이 바로 뒤 전체 검증과 겹치지 않게 하고, 완료 조건이 티켓 목표보다 약해지지 않게 한다.

## 완료 조건
- `templates/spec.md` §5 주석의 verify 규칙에 "문서·버전 티켓은 레포에서 확인한 환경 동기화·버전 시험·plugin 검사로 좁힌다"가 들어간다. 구체 명령(`uv` 등)은 쓰지 않는다. `.goldstack/config.toml`을 고치는 티켓의 전체 검증 예외는 그대로다.
- `templates/ticket.md` 완료 조건 주석에 "목표의 동사마다 완료 조건이 하나씩 있는지, 표시용 값과 원본 데이터를 구분했는지"가 들어간다.
- `tests/test_skill_grill.py`가 두 문장을 확인한다. SKILL.md는 고치지 않는다(`WORD_LIMITS["grill"]` 450, 지금 419).

## 범위 밖
- `gs check`의 경고 규칙 변경

## 참고
- spec §3 1-7
- 아이디어 `docs-ticket-narrow-verify`, `ticket-done-matches-goal`
