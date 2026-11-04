---
id: "02"
title: "티켓 검증: 병합 트리에서 돌리고 깨끗함 확인, 티켓 verify 키, worker 지시문"
blocked_by: ["01"]
touches: ["src/gs/go.py", "src/gs/feature.py", "src/gs/worker.py", "src/gs/report.py", "tests/test_ticket_verify.py", "tests/test_verify_modes.py"]
model: claude
reviewer: codex
---
## 목표
빠른 티켓 검증을 안전하게 쓸 수 있게 구멍을 막고, 문서·설정 티켓이 전체 시험을 돌리지 않을 길을 만든다.

## 완료 조건
- spec `verify_ticket`이나 티켓 `verify`가 있어도 티켓 검증은 미완 병합 트리(integration worktree)에서 돈다. 시험: 티켓 worktree에만 있는 커밋 안 된 파일이 있어야 통과하는 검증 명령은 실패한다.
- 검증이 트리를 바꾸면(HEAD, 브랜치, `setup.is_clean` 기준) 실패이고 로그에 `검증 중 worktree가 바뀌었다`가 남는다. 시험이 있다.
- 티켓 frontmatter에 선택 키 `verify`가 있다. 우선순위는 티켓 `verify` → spec `verify_ticket` → spec `verify`. 시험이 세 경우를 모두 본다.
- `verify`가 비었거나 여러 줄이면 `gs check` 오류다(spec의 `verify`와 같은 규칙).
- 마무리(`integration`, `integration-final`, `main-recheck`)는 티켓 `verify`와 상관없이 spec `verify`를 돌린다. 시험이 있다.
- worker brief(수정 worker 포함)가 그 티켓의 실제 검증 명령을 보이고, "개발 중에는 관련 시험만 돌리고, 커밋 전에 이 명령을 한 번 돌린다"고 적는다. 시험이 있다.
- 보고서의 티켓 검증 명령 표시가 티켓별 `verify`를 반영한다.

## 범위 밖
- 일시 오류 대기(06), 마무리 검증 실패 보고(05), 전체 시험 병렬(01), grill 지침(04).

## 참고
- spec §3 2-2, 2-3, 2-4. §6 `verify_ticket` 구멍, 검증 지점.
- `finish._verify`가 트리 변경을 보는 방식과 맞춘다.
- `verify_ticket`은 v5 spec 1-7에서 도입됐다. 키는 유지하고 도는 위치만 바꾼다.
