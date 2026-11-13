---
id: "06"
title: "v36 문서·grill 템플릿 규칙·버전 0.2.20"
blocked_by: ["01", "02", "03", "04", "05"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py", "skills/grill/templates/spec.md"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && .venv/bin/python -m unittest discover -s tests -p test_skill_grill.py && claude plugin validate ."
---
## 목표
v36 변경을 문서에 적고, 차단 hook 티켓의 grill 규칙을 템플릿에 넣고, 버전을 0.2.20으로 올린다.

## 완료 조건
- `docs/guide.md`: `gs child`는 명령 맨 앞에 한 번(앞붙이는 `--` 뒤), 셸 중첩이 깊으면 막힘(01); 배경 작업이 있으면 유예 정리를 하지 않고 활동하면 유예 시계가 다시 시작(02, `result_grace_seconds` 설명 포함); 마지막 재리뷰의 high는 병합하지 않고 티켓 실패(03).
- `docs/internals.md`: hook 막는 것 목록, `_wait_any`의 유예 조건, 2차·수리 재리뷰 high의 처리.
- `skills/grill/templates/spec.md` §5 주석에 두 규칙: "차단 hook의 명령 분해를 바꾸는 티켓은 large", "새 래퍼 명령을 만들면 hook이 그것을 어떻게 판정할지 grill에서 정한다. 재귀 분해보다 맨 앞·허용 목록 같은 평평한 규칙을 먼저 고른다". `tests/test_skill_grill.py`가 통과한다.
- `CHANGELOG.md`에 0.2.20 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.20이고 `tests/test_version.py`가 통과한다.
- `.goldstack/config.toml`의 `result_grace_seconds = 0`은 건드리지 않는다(v37 마지막 티켓이 지운다, spec 2-2).

## 범위 밖
- 코드 변경(01–05)

## 참고
- spec §3, `.goldstack/ideas/hook-parse-ticket-grill-rule.md`
