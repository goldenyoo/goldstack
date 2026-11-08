---
id: "03"
title: "v26 문서와 버전 0.2.10"
blocked_by: ["01", "02"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v26의 동작 변경을 사용자 문서와 구조 문서에 반영하고 버전을 0.2.10으로 올린다.

## 완료 조건
- `docs/guide.md`에 `[hook.worker_tests]` 설정(키 넷의 뜻, 기본 꺼짐, 예시 값)과 main 검증 건너뛰기 조건이 사용자 관점으로 있다.
- `docs/internals.md`에 01·02의 구조 변경(worker 환경 변수로 규칙 전달, hook 판정 위치, main 건너뛰기 판단 위치)이 있다.
- `CHANGELOG.md`에 0.2.10 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.10이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 동작 변경(01·02)

## 참고
- spec §3 전체
