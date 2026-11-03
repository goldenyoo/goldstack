---
id: "05"
title: "squash 되살림 표시와 본문, CI 검사 등록 기다리기"
blocked_by: ["04"]
touches: ["src/gs/finish.py", "src/gs/config.py", "tests/test_squash_reintroduce.py", "tests/test_checks_grace.py"]
model: codex
reviewer: claude
---
## 목표
squash 저장소에서 되돌림·되살림 기록이 사라지지 않게 하고, CI 검사가 등록되기 전에 "검사 없음"으로 병합하지 않게 한다.

## 완료 조건
- squash 병합 메시지 본문에 되살린 티켓도 목록·`gs-ticket:` 줄에 들어가고, 되살림이면 되돌렸던 커밋을 가리키는 줄(`This reverts commit <sha>`와 같은 식별을 `_undone_reverts`·`_revert_of`가 찾을 수 있는 형식)을 넣는다. 새 clone에서도 다음 실행이 이미 되살린 revert를 다시 적용하려 하지 않는다(시험: `test_feature_restored_after_someone_reverted_squash` 변형, 새 clone).
- CI 대기: `timeouts.checks_grace_seconds`(정수 ≥0, 기본 60) config 키. 검사가 하나도 보고되지 않으면 그 시간 동안 기다렸다가 그래도 없으면 "검사 없음 → 병합". base 보호 규칙에서 필수 검사 이름을 알면 그 이름들이 모두 나타나 끝날 때까지 기다린다(상한 `checks_minutes`). 필수가 아닌 검사의 실패는 필수 검사 이름을 알 때 병합을 막지 않는다(시험: 늦게 등록되는 검사, 끝까지 없음, 필수 이름 대기, 비필수 실패).
- 기존 `test_wait_checks.test_no_checks_merges_immediately`는 grace 뒤 병합으로 갱신(시험 시간은 짧게 주입).

## 범위 밖
- CI 실패 자동 수정(out-of-scope `ci-fix-tickets`)

## 참고
- spec §3 1-7 a·b, §6 아직 남음 (a)(b)
