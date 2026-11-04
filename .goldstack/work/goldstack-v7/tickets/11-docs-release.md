---
id: "11"
title: "문서, CHANGELOG 미출시 항목"
blocked_by: ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
touches: ["README.md", "docs/guide.md", "docs/internals.md", "CHANGELOG.md"]
model: claude
reviewer: codex
---
## 목표
v7에서 바뀐 동작과 설정을 문서와 미출시 CHANGELOG에 반영한다.

## 완료 조건
- 버전은 `0.1.0` 그대로다(`pyproject.toml`, `.claude-plugin/plugin.json`을 바꾸지 않는다). `tests/test_version.py`가 통과한다.
- `CHANGELOG.md`의 `## 0.1.0 — 미출시`에 v7 내용이 있고, "레포에서 할 일"로 새 config 키(`[tiers.*]`, `[tiers] review`·`rereview`, `models.failure_summary`, `timeouts.network_wait_minutes`)와 안 넣었을 때의 동작을 적는다.
- `README.md`·`docs/guide.md`의 config·spec·티켓 키 표에 새 키(`tier`, 티켓 `verify`)가 있다. `verify_ticket`이 병합 트리에서 돈다는 것, 빠른 전체 시험을 만드는 예(프로세스 나눠 돌리기)가 있다.
- `docs/internals.md`에 네트워크 대기·`중단(네트워크)`(종료 코드 3)·리뷰 재호출 흐름과 측정 필드가 있다. "재시도 1회"처럼 달라진 옛 설명을 고친다.
- 태그와 GitHub Release는 만들지 않는다(v8 뒤 사람이 확인하고 만든다).

## 범위 밖
- `gs` 동작 변경. 동작이 문서와 다르면 고치지 말고 마지막 메시지에 적는다.

## 참고
- 이번 실행 규칙: 개발 중에는 관련 시험만 돌리고, 전체 검증은 커밋 직전에 한 번만 돌린다(수정 worker도). gs가 병합 전에 다시 돌린다.
- spec §3 전체. 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
