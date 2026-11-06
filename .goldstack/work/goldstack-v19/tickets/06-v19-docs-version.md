---
id: "06"
title: "v19 문서와 버전 0.2.3"
blocked_by: ["01", "02", "03", "04", "05"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v19의 동작 변경을 문서에 옮기고 버전을 0.2.3으로 올린다.

## 완료 조건
- `docs/guide.md`와 `docs/internals.md`가 바뀐 재리뷰·재개·피드백·backlog 동작을 적는다. `CHANGELOG.md`의 미출시 항목을 `0.2.3` 절로 옮긴다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 0.2.3이고 `tests/test_version.py`가 통과한다. 태그·릴리스는 만들지 않는다.

## 범위 밖
- 두 번째 리뷰어 기준 문서는 `/retro goldstack-v19` 결과를 본 뒤 고친다.

## 참고
- spec 결정, goldstack-v17 결정 2-6.
