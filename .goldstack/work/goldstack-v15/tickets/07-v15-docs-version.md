---
id: "07"
title: "문서, CHANGELOG, `0.2.0`"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json"]
tier: small
model: claude
reviewer: codex
---
## 목표
문서를 맞추고 버전을 `0.2.0`으로 올린다. 태그와 릴리스는 만들지 않는다.

## 완료 조건
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 `0.2.0`이다. `test_version_sync.py`가 통과한다.
- `CHANGELOG.md`의 미출시가 `## 0.2.0 — <날짜>`가 되고 새 빈 미출시 절이 있다.
- `docs/guide.md`, `docs/internals.md`에 issue 상태, `issues` 키, 리뷰한 SHA 병합이 있다.
- git 태그가 없다.

## 범위 밖
- 릴리스·태그 발행.

## 참고
- spec 1-3
