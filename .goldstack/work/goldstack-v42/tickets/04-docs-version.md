---
id: "04"
title: "v42 문서·버전 0.2.26"
blocked_by: ["01", "02", "03"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p test_version.py && claude plugin validate ."
---
## 목표
v42 변경을 문서에 적고 버전을 0.2.26으로 올린다.

## 완료 조건
- `docs/guide.md`: `[review] second_reviewer_rereview` 절에 겹침 건너뛰기(키 없이 늘, 기준 같은 파일 ±5줄, 줄 번호 없는 위치는 겹치지 않음). `[hook.worker_tests]` 표에 `max_outside_files`와 예시. worker brief 관찰 규칙의 바뀐 뜻.
- `docs/internals.md`: 재리뷰 자리 고르기의 겹침 판정, hook 세션 누적 기록(위치와 세션 단위).
- `CHANGELOG.md`에 0.2.26 항목.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.26이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–03)

## 참고
- spec §3
