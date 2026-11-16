---
id: "06"
title: "v45 문서·버전 0.2.28"
blocked_by: ["01", "02", "03", "04", "05"]
touches: ["docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", "uv.lock", ".claude-plugin/plugin.json", "tests/test_version.py"]
tier: small
model: claude
reviewer: codex
verify: "uv sync --locked -q && printf 'test_%s.py\\n' version skill_retro review_touches_outside docs_missing fix_brief sandbox skill_grill | xargs -n 1 .venv/bin/python -m unittest discover -s tests -p && claude plugin validate ."
---
## 목표
v45가 바꾼 동작을 문서에 적고, 남아 있던 문서 흔적을 걷고, 버전을 0.2.28로 올린다.

## 완료 조건
- `docs/guide.md`·`docs/internals.md`에 적는다: brief의 관찰 규칙(touches 안은 고친다), 범위 밖 관찰의 하류 brief 전달(경로 ↔ touches), 보고서 관찰 표가 모든 worker 로그를 읽는 것, 마무리 줄 덧붙임(spec §4).
- `docs/internals.md`에서 없는 `go._verifying_again`과 `_mark_resume(verify_again=True)`를 가리키는 문장을 지금 코드에 맞게 고친다. 확인 명령(리뷰어가 다시 돌린다): `grep -nE '_verifying_again|verify_again=True' docs/internals.md`가 아무 줄도 내지 않는다.
- `CHANGELOG.md`에 0.2.28 항목: 01–05의 변경.
- `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` 버전이 0.2.28이고 `tests/test_version.py`가 통과한다.
- verify는 문서 이름을 단언하는 시험(spec §6 목록)을 포함한다. 그 시험이 고치지 않고 통과한다.

## 범위 밖
- 코드와 skill 글 변경(01–05).

## 참고
- spec §3, §4, §6.
