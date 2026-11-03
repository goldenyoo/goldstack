---
id: "03"
title: "CI 검사 기다리기"
blocked_by: ["02"]
model: codex
reviewer: claude
touches: ["src/gs/finish.py", "tests/test_wait_checks.py"]
---
## 목표
`git.wait_checks = true`면 PR의 CI 검사가 통과한 뒤에만 병합한다.

## 완료 조건
- 병합 직전, 보고서 커밋까지 든 PR 최종 head(`merge_head`)의 검사를 기다린다: 필수 검사가 있으면 그것만, 없으면 그 PR의 모든 검사(spec 2-5). 진행은 `■ PR #N: CI 검사 대기 중(<이름> ✓, <이름> …)`처럼 바뀔 때 출력, 진행 바 단계 `CI 대기`.
- 모두 통과하면 병합으로 간다. 하나라도 실패하면 병합하지 않고 phase `checks_failed`, outcome `CI 실패: <이름들>`, PR은 열어 둔다. `timeouts.checks_minutes`를 넘기면 `checks_timeout`, `CI 대기 시간 초과`(시험: 통과, 실패, 시간 초과, 검사 없음 → 바로 병합).
- `checks_failed`·`checks_timeout`에서 다음 `gs go`가 PR head가 그대로면 검사를 다시 읽어 이어 가고, head가 바뀌었으면(사람이 고침) 그 head를 다시 integration 검증한 뒤 이어 간다(시험).
- 텔레그램 알림 문구에 CI 실패·시간 초과가 드러난다.
- `wait_checks = false`면 지금과 같다(기존 시험).

## 범위 밖
- CI 실패를 고치는 티켓 자동 생성(out-of-scope `ci-fix-tickets`)

## 참고
- spec §3 1-3, 2-5
