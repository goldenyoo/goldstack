---
id: "05"
title: "v31 문서, v30 사실 바로잡기, 버전 0.2.15"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py", "tests/test_check.py", ".goldstack/work/goldstack-v30/spec.md"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && .venv/bin/python -m unittest discover -s tests -p test_check.py && claude plugin validate ."
---
## 목표
v31 변경을 사용자 문서에 반영하고, v30 grill의 틀린 사실을 기록에서 바로잡고, 버전을 0.2.15로 올린다.

## 완료 조건
- `docs/guide.md`: config `[verify]`(`failed_file`·`rerun`·`max_files`, 비면 꺼짐, 이 레포 예시, `verify_retries`와의 관계, flaky가 보고서 남은 위험에 나옴). `gs replay` 절에 base 이력을 먼저 찾는다는 것. touches 오류 설명에 "끝난 옛 feature(v0–v4 같은)는 `gs check`에서 오류로 나오고 다시 돌릴 일이 없으면 그대로 둔다".
- `docs/internals.md`에 verify 재실행과 보고서 flaky가 있으면 맞춘다.
- `tests/test_check.py` `copy_feature_with_touches` docstring: 옛 기록 v0–v4에 touches 없는 티켓이 있고(v0 11, v1 2, v2 8, v3 8, v4 10), 이 helper는 touches 밖의 옛 형식 호환을 보려고 사본에만 넣는다고 적는다. 동작은 바꾸지 않는다.
- `.goldstack/work/goldstack-v30/spec.md` §6의 "touches가 없는 것은 `goldstack-v0`의 10장뿐" 줄 아래에 바로잡는 줄을 더한다(원문은 지우지 않는다): 실제 수와 원인(`| head`로 잘림), 아이디어 `goldstack-v30-03-1`.
- `CHANGELOG.md`에 0.2.15 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.15이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–04)

## 참고
- spec §3 전체
