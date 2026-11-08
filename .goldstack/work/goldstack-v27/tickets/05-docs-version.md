---
id: "05"
title: "v27 문서와 버전 0.2.11"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v27의 동작 변경을 사용자 문서와 구조 문서에 반영하고 버전을 0.2.11로 올린다.

## 완료 조건
- `docs/guide.md`에 재현된 결함의 새 판단 기준, `defer`와 보고서 "재현된 미수리 결함" 절, codex 리뷰어의 임시 폴더 쓰기가 사용자 관점으로 있다.
- `docs/internals.md`에 01~04의 구조 변경(고치지 못하는 파일 목록, `defer` 판정 흐름, codex 리뷰 sandbox, 수리 종료 분기, 출력 끝 형식)이 있다. 02가 실측 결과로 코드를 바꾸지 않았으면 그 사실과 연구 문서 링크를 적는다.
- `CHANGELOG.md`에 0.2.11 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.11이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 동작 변경(01~04)

## 참고
- spec §3 전체
