---
id: "06"
title: "v39 문서·버전 0.2.23"
blocked_by: ["01", "02", "03", "04", "05"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v39 변경을 문서에 적고 버전을 0.2.23으로 올린다.

## 완료 조건
- `docs/guide.md`: worker가 막는 도구에 `ScheduleWakeup`·`CronCreate`, Cloudflare 403을 일시 오류로 기다림, 보고서 단계 `병합 대기`.
- `docs/internals.md`: `transient`의 Cloudflare 403 분류, 병합 줄의 `merge_wait` 단계, `setup.marker`가 `.git`을 직접 읽음.
- `CHANGELOG.md`에 0.2.23 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.23이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–05)

## 참고
- spec §3
