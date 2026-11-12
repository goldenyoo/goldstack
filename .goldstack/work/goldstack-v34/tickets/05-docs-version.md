---
id: "05"
title: "v34 문서와 버전 0.2.18"
blocked_by: ["01", "02", "03", "04"]
touches: ["docs/guide.md", "docs/internals.md", "docs/research/agy.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v34의 모델 배정 변경을 사용자 문서에 적고 버전을 0.2.18로 올린다.

## 완료 조건
- `docs/guide.md`:
  - 모델 예시와 기본값 표를 새 기본값(Carbon, astra)으로. 티켓 예시의 `model`·`reviewer`가 고정값이 아니라 티켓마다 고르는 것이고 기준이 spec 템플릿 §5에 있다고 적는다(01).
  - `gs doctor`의 `모델`·`모델 기본값` 행과 `--write`가 그 칸을 바꾸는 법, `gs check`의 codex 목록 경고와 옛 기본값 경고(02–04). 옛 기본값과 같은 값을 일부러 고른 경우도 제안에 나온다는 한계. 다른 머신에서 쓰는 레포는 그 머신에서 `gs doctor`를 친다.
- `docs/internals.md` 모듈 표에 `models.py`, doctor 절에 모델 제안·쓰기.
- `docs/research/agy.md`에 Carbon 모델 이름과 이 레포가 Carbon으로 옮겼다는 한 단락(측정 없이 바꿨다는 사실 포함).
- `CHANGELOG.md`에 0.2.18 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.18이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 변경(01–04)

## 참고
- spec §3 전체
