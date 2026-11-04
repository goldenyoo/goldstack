---
id: "11"
title: "문서, 버전 0.3.0, CHANGELOG"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", ".claude-plugin/plugin.json", "uv.lock", "tests/test_version.py"]
model: claude
reviewer: codex
tier: small
verify: "uv run python -m unittest discover -s tests -p test_version.py && claude plugin validate . && uv build -q -o \"$(mktemp -d)\""
---
## 목표
v8에서 바뀐 동작과 설정을 문서에 반영하고 0.3.0을 준비한다.

## 완료 조건
- `gs --version`, `pyproject.toml`, `.claude-plugin/plugin.json`, `uv.lock`이 `0.3.0`이다. `tests/test_version.py`가 통과한다.
- `CHANGELOG.md`에 0.3.0 항목이 있고, "레포에서 할 일"로 새 config 키(`[goldstack] requires`, `[feedback]`)와 안 넣었을 때의 동작을 적는다.
- `README.md`: 설치·업데이트가 `gs self-update`와 main 채널 기준이다. 리눅스 서버에서 쓰는 법(herdr 없이 도는 것, tmux)이 있다. skill 표에 `/overnight`, `/feedback`이 있다.
- `docs/guide.md`: 피드백이 무엇을 보내고 무엇을 안 보내는지, 프로젝트별 끄는 법, `/overnight` 쓰는 법이 있다.
- `docs/internals.md`: 모듈 표에 `version.py`, `selfupdate.py`, `feedback.py`가 있고, 피드백 흐름과 Actions 시험이 있다.
- 태그와 GitHub Release는 만들지 않는다(사람이 한다).

## 범위 밖
- `gs` 동작 변경. 동작이 문서와 다르면 고치지 말고 마지막 메시지에 적는다.

## 참고
- spec §3 전체, §4 형식. 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
