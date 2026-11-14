---
id: "05"
title: "v40 문서·버전 0.2.24"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
closes: [74]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v40 변경을 문서에 적고 버전을 0.2.24로 올린다. issue #74(좀비 대기)가 이미 해결됐음을 CHANGELOG에 적고 닫는다.

## 완료 조건
- `docs/guide.md`: worker 시험 범위(grep 묶음 상한, `ps` 차단 실패는 다시 돌리지 않음), 2차 재리뷰가 1차 재리뷰의 새 report 지적도 판정함.
- `docs/internals.md`: `review.rereview_targets`의 새 대상.
- `CHANGELOG.md`에 0.2.24 항목. #74는 0.2.19–0.2.20의 유예 정리(`[timeouts] result_grace_seconds`, 배경 작업 정리)로 해결됐다는 한 줄을 둔다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.24이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–04)

## 참고
- spec §3, §6(#74)
