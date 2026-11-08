---
id: "07"
title: "v25 문서와 버전 0.2.9"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v25의 동작 변경을 사용자 문서와 구조 문서에 반영하고 버전을 0.2.9로 올린다.

## 완료 조건
- `docs/guide.md`에 `setup_when` 설정, 커밋 없는 수리와 `브랜치 밖 원인:` 처리, 형식 오류 리뷰 표시, "버려진 시도의 지적" 절이 사용자 관점으로 있다.
- `docs/internals.md`에 01~05의 구조 변경(이스케이프 고치기, `format-error`, setup 재실행 시점, 수리 종료 분기, 원본 명령, `prior_findings`)이 있다.
- `CHANGELOG.md`에 0.2.9 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.9이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 동작 변경(01~06)

## 참고
- spec §3 전체
