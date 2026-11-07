---
id: "04"
title: "v22 문서와 버전 0.2.6"
blocked_by: ["01", "02", "03"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v22에서 바뀐 동작을 문서에 맞추고 버전을 올린다.

## 완료 조건
- `docs/guide.md`에 `xargs`로 `uv run`을 띄우면 신호 줄이 남지 않아 끊김으로 판정되지 않는다는 한계와 `.venv/bin/python` 예시를 적는다.
- `docs/internals.md`에 옛 검증 정리와 main 재검증을 적는다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `CHANGELOG.md`가 0.2.6으로 맞고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경

## 참고
- spec §3
