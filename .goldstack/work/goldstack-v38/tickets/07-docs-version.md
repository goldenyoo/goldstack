---
id: "07"
title: "v38 문서·버전 0.2.22·이 레포 재리뷰 설정"
blocked_by: ["01", "02", "03", "04", "05", "06"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py", ".goldstack/config.toml"]
tier: small
model: claude
reviewer: codex
---
## 목표
v38 변경을 문서에 적고, 버전을 0.2.22로 올리고, 이 레포 config에서 두 번째 리뷰어를 1차 재리뷰까지만 부른다(결정 2-4).

## 완료 조건
- `docs/guide.md`: `[review] second_reviewer_rereview`(값 셋과 기본 `"all"`, 빠진 회차의 판정을 첫 리뷰어가 맡음), 보고서의 `수정됨(수리 재리뷰 확인)`·`touches 밖:` 줄, ETA의 넘김 표시, 병합 전 대조의 대체 규칙을 적는다.
- `docs/internals.md`: `final_highs`의 대체 규칙, `failure.record`의 `final-high.md` 앞부분 싣기.
- `.goldstack/config.toml`에 `[review]` 절과 `second_reviewer_rereview = "first"` 한 줄(위에 이유 주석 한 줄). 다른 줄은 그대로.
- `CHANGELOG.md`에 0.2.22 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.22이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–06)

## 참고
- spec §3
