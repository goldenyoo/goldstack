---
id: "05"
title: "v18 문서와 버전 0.2.2"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v18의 동작 변경을 문서에 옮기고 버전을 0.2.2로 올린다.

## 완료 조건
- `docs/guide.md`와 `docs/internals.md`가 첫 worker의 계열별 시험 지시와 "새 시험의 실패 보기"를 적는다.
- `CHANGELOG.md`의 미출시 항목을 `0.2.2` 절로 옮긴다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 0.2.2이고 `tests/test_version.py`가 통과한다. 태그·릴리스는 만들지 않는다.

## 범위 밖
- 두 번째 리뷰어 기준 문서는 고치지 않는다(결정 1-4).

## 참고
- spec 결정 1-1, 1-2, goldstack-v17 결정 2-6.
