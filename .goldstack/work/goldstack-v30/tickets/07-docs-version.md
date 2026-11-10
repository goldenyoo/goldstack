---
id: "07"
title: "v30 문서와 버전 0.2.14"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v30의 변경을 사용자 문서에 반영하고 버전을 0.2.14로 올린다.

## 완료 조건
- `docs/guide.md`: `gs replay` 절(용도, 인자, 시작 commit 자동 찾기와 `--base`, 수정·재리뷰가 빠지는 한계, `.goldstack/trials/replay.md`와 로그 자리, 결과는 사람이 커밋). 티켓 형식 설명에 `gs check`가 touches 없는 티켓을 오류로 막는다는 것. `gs check`의 교차 검토 경고. 수리 worker의 브랜치 밖 원인 표식이 네트워크 끊김보다 먼저라는 것(수리 절이 있으면).
- `docs/internals.md` 모듈 표에 `replay.py`를 더하고, 바뀐 동작의 설명이 있으면 맞춘다.
- `CHANGELOG.md`에 0.2.14 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.14이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–06)

## 참고
- spec §3 전체
