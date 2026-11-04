---
id: "11"
title: "문서, CHANGELOG 미출시 항목"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md", ".claude-plugin/**"]
model: claude
reviewer: codex
tier: small
verify: "uv run python -m unittest discover -s tests -p test_version.py && claude plugin validate . && uv build -q -o \"$(mktemp -d)\""
---
## 목표
v8에서 바뀐 동작과 설정을 문서와 미출시 CHANGELOG에 반영한다. 다음 일은 첫 릴리스(`v0.1.0`)다.

## 완료 조건
- 버전은 `0.1.0` 그대로다. `.claude-plugin/`의 플러그인·marketplace 설명에 새 skill(`/overnight`, `/feedback`)이 있고 버전 값은 바꾸지 않는다. `tests/test_version.py`가 통과한다.
- `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v8 내용이 있고, "레포에서 할 일"로 새 config 키(`[goldstack] requires`, `[feedback]`)와 안 넣었을 때의 동작을 적는다.
- `README.md`: 처음 설치는 태그 `v0.1.0`(v8 뒤 사람이 만든다), 이후 업데이트는 `gs self-update`와 main 채널 기준이다. 리눅스 서버에서 쓰는 법(herdr 없이 도는 것, tmux)이 있다. skill 표에 `/overnight`, `/feedback`이 있다.
- `docs/guide.md`: 피드백이 무엇을 보내고 무엇을 안 보내는지, 프로젝트별 끄는 법, `/overnight` 쓰는 법이 있다.
- `docs/internals.md`: 모듈 표에 `version.py`, `selfupdate.py`, `feedback.py`가 있고, 피드백 흐름과 Actions 시험이 있다.
- 태그와 GitHub Release는 만들지 않는다(v8이 verified가 된 뒤 사람이 확인하고 만든다).

## 범위 밖
- `gs` 동작 변경. 동작이 문서와 다르면 고치지 말고 마지막 메시지에 적는다.

## 참고
- spec §3 전체, §4 형식. 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
