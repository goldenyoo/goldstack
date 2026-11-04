---
id: "11"
title: "문서, 버전 0.2.0, CHANGELOG"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md", "pyproject.toml", ".claude-plugin/plugin.json", "uv.lock", "tests/test_version.py"]
model: claude
reviewer: codex
---
## 목표
v7에서 바뀐 동작과 설정을 문서에 반영하고 0.2.0을 준비한다.

## 완료 조건
- `gs --version`, `pyproject.toml`, `.claude-plugin/plugin.json`, `uv.lock`이 `0.2.0`이다. `tests/test_version.py`가 통과한다.
- `CHANGELOG.md`에 0.2.0 항목이 있고, "레포에서 할 일"로 새 config 키(`[tiers.*]`, `[tiers] review`·`rereview`, `models.failure_summary`, `timeouts.network_wait_minutes`)와 안 넣었을 때의 동작을 적는다.
- `README.md`·`docs/guide.md`의 config·spec·티켓 키 표에 새 키(`tier`, 티켓 `verify`)가 있다. `verify_ticket`이 병합 트리에서 돈다는 것, 빠른 전체 시험을 만드는 예(프로세스 나눠 돌리기)가 있다.
- `docs/internals.md`에 네트워크 대기·`중단(네트워크)`(종료 코드 3)·리뷰 재호출 흐름과 측정 필드가 있다. "재시도 1회"처럼 달라진 옛 설명을 고친다.
- 태그와 GitHub Release는 만들지 않는다(사람이 한다).

## 범위 밖
- `gs` 동작 변경. 동작이 문서와 다르면 고치지 말고 마지막 메시지에 적는다.

## 참고
- spec §3 전체. 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
