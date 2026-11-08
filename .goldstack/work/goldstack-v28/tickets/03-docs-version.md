---
id: "03"
title: "v28 문서와 버전 0.2.12"
blocked_by: ["01", "02"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && .venv/bin/python -m unittest discover -s tests -p 'test_version*.py' && .venv/bin/python -m unittest discover -s tests -p test_docs_missing.py && claude plugin validate ."
---
## 목표
v28의 동작 변경을 사용자 문서와 구조 문서에 반영하고 버전을 0.2.12로 올린다.

## 완료 조건
- `docs/guide.md`의 "worker hook이 막는 `=` 단어와 zsh 구분선" 절을 새 방식으로 다시 쓴다: worker는 gs가 `ZDOTDIR` 전달 폴더로 `noequals`를 켜서 띄운다, 02가 판정을 지웠는지 남겼는지(실측 표 링크), 대화 세션의 `~/.zshenv` 안내는 유지.
- `docs/internals.md`에 전달 폴더 위치·`GS_NOEQUALS`·hook 판정 변경이 있다.
- `CHANGELOG.md`에 0.2.12 항목. `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.12이고 `tests/test_version.py`가 통과한다.

## 범위 밖
- 코드 동작 변경(01·02)

## 참고
- spec §3 전체, `docs/research/worker-noequals.md`
