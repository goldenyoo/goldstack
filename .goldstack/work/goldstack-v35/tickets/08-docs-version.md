---
id: "08"
title: "v35 문서와 버전 0.2.19"
blocked_by: ["01", "02", "03", "04", "05", "06", "07"]
touches: ["docs/guide.md", "docs/internals.md", "README.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v35 변경을 사용자 문서에 적고, 실행 예시를 `/goldstack:<이름>`으로 맞추고, 버전을 0.2.19로 올린다.

## 완료 조건
- `docs/guide.md`: `gs child`(03)와 worker가 `GS_ROLE`을 바꾸지 못함(02), worker 마지막 메시지의 `## 남긴 관찰`과 리뷰 판정·보고서 표(04·05), `[timeouts] result_grace_seconds`(06), 수동 피드백 제목(01), brief의 touches(04).
- `docs/internals.md`: 모듈 표에 `child.py`, hook 막는 것 목록, 리뷰 출력의 `observations`, `_wait_any`의 유예 정리.
- README와 `docs/guide.md`의 실행 예시(`/go`, `/overnight`, `/wait-what` 등 짧은 이름)를 `/goldstack:<이름>`으로(아이디어 `docs-slash-examples`). 설명 규칙과 예시가 맞는다.
- `CHANGELOG.md`에 0.2.19 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.19이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–07)

## 참고
- spec §3 전체
- `.goldstack/ideas/docs-slash-examples.md`
