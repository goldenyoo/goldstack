---
id: "04"
title: "v24 문서와 버전 0.2.8"
blocked_by: ["01", "02", "03"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v24에서 바뀐 동작을 문서에 맞추고 버전을 올린다.

## 완료 조건
- `docs/internals.md`의 리뷰·재시도 설명에 실행 기록과 성공 명령 전달을 적는다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `CHANGELOG.md`가 0.2.8로 맞고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경

## 참고
- spec §3
