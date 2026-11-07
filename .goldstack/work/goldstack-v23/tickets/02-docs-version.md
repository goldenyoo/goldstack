---
id: "02"
title: "v23 문서와 버전 0.2.7"
blocked_by: ["01"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v23에서 바뀐 hook 판정을 문서에 맞추고 버전을 올린다.

## 완료 조건
- `docs/internals.md`의 hook 설명이 새 판정과 맞는다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`, `CHANGELOG.md`가 0.2.7로 맞고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경

## 참고
- spec §3
