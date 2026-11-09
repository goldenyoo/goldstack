---
id: "03"
title: "v29 문서와 버전 0.2.13"
blocked_by: ["01", "02"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v29의 skill 변경을 사용자 문서에 반영하고 버전을 0.2.13으로 올린다.

## 완료 조건
- `docs/guide.md`의 `/grill` 절에 티켓 표 확인 전 교차 검토(다른 계열 CLI, 읽기 전용, 못 하면 §7에 기록)가 있다. `/overnight` 아침 보고 설명이 있으면 끝의 `gs self-update`를 적는다.
- `docs/internals.md`에 grill·overnight 단계 설명이 있으면 맞춘다(없으면 고치지 않는다).
- `CHANGELOG.md`에 0.2.13 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.13이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- skill 글 변경(01·02)

## 참고
- spec §3 전체
