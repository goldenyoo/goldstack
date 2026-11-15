---
id: "05"
title: "v43 문서·버전 0.2.26"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v43 변경(과 v42에서 문서에 빠진 02)을 문서에 적고 버전을 0.2.26으로 올린다.

## 완료 조건
- `docs/guide.md`: 티켓 키 `after`(순서만, 상류 실패에도 하류가 돈다)와 `blocked_by`의 차이. 판별 통과 파일만 다시 실패하면 수리 없이 같은 트리를 다시 검증한다는 것. config `[sandbox] writes`(규칙, 오류 조건, 적용 계열). goldstack-v42 02: 두 번째 리뷰어의 fix 지적이 모두 첫 리뷰어 지적과 겹치면(같은 파일 ±5줄) 재리뷰에 두 번째 리뷰어를 부르지 않는다.
- `docs/internals.md`: `after`의 그래프·건너뜀 처리, flaky 다시 검증 분기(`verify_again` 재사용), `[sandbox] writes`가 hook·codex 쓰기 목록으로 가는 길.
- `CHANGELOG.md`에 0.2.26 항목(v42 02 포함).
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.26이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–04).

## 참고
- spec §3(결정 3-3). goldstack-v42 보고서 "빠진 범위", `src/gs/go.py`의 `_second_skipped` docstring.
