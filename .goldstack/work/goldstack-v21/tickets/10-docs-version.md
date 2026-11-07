---
id: "10"
title: "v21 문서와 버전 0.2.5"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
v21에서 바뀐 동작을 문서에 맞추고 버전을 올린다.

## 완료 조건
- `docs/guide.md`에 끊긴 검증의 처리, 재시도와 지적 파일, worker hook의 `=` 차단, `gs check`의 새 경고가 있다.
- `docs/guide.md`에 대화 세션의 zsh 구분선 대응으로 `~/.zshenv`의 `setopt noequals`와 `=cmd` 확장에 미치는 영향을 적는다. Claude Code Bash 도구에서는 재지 않았다고 밝힌다.
- `docs/internals.md`가 바뀐 흐름과 맞고 `CHANGELOG.md`에 0.2.5가 있다.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json`이 0.2.5이고 버전 시험이 통과한다.

## 범위 밖
- 코드 변경. 틀린 동작을 찾으면 보고만 한다.

## 참고
- 앞 티켓의 diff, spec §3.
