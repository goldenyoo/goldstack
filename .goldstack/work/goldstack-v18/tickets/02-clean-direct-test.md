---
id: "02"
title: "push 설정 변경 시험을 직접 시험으로 보강"
blocked_by: []
touches: ["tests/test_clean.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
`test_push_settings_change_during_remote_delete_is_not_warned`의 남은 약점을 메운다.

## 완료 조건
- `clean.integration`을 직접 불러 `git.PushSettingsChanged`가 올라오는 것을 `assertRaises`로 보는 시험이 있다.
- 기존 시험이 stderr에 `경고`가 없음을 단언한다.
- `src/gs/clean.py`의 안쪽 re-raise를 잠깐 지우면 새 시험이 실패하는 것을 worker가 직접 보고 마지막 메시지에 적는다. 소스는 바꾸지 않는다.

## 범위 밖
- `src/gs/clean.py` 수정.

## 참고
- 아이디어 `goldstack-v15-06-6`.
