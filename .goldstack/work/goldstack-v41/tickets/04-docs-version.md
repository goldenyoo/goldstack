---
id: "04"
title: "v41 문서·버전 0.2.25"
blocked_by: ["01", "02", "03"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v41 변경을 문서에 적고 버전을 0.2.25로 올린다.

## 완료 조건
- `docs/guide.md`: 마무리 integration 검증을 건너뛰는 조건과 보고서 마무리 줄의 표시, worker brief의 백그라운드 출력 규칙.
- `docs/internals.md`: `finish`의 integration 검증 건너뛰기 판정(근거가 `metrics.validations`이고 `verified_head`를 남긴다는 것).
- `CHANGELOG.md`에 0.2.25 항목.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.25이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–03)

## 참고
- spec §3
