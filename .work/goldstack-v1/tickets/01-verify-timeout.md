---
id: "01"
title: "verify 시간 제한"
blocked_by: []
model: claude
reviewer: codex
---
## 목표
`gs go`가 돌리는 verify 명령 4군데(티켓 병합 전, integration, integration-final, main·main-recheck)에 시간 제한을 둔다. 넘기면 명령과 그 자손을 모두 끝내고 검증 실패로 처리한다.

## 완료 조건
- spec frontmatter `verify_minutes`(1 이상 정수, 기본 20)를 읽는다. `verify_minutes: 0`이나 `abc`는 `gs check` 오류, 키가 없으면 20이고 경고가 없다(시험).
- 4군데 verify가 모두 한 함수(새 `src/gs/verify.py`)를 쓴다. 명령은 새 프로세스 그룹에서 돌고, 시간 = `GS_VERIFY_TIMEOUT`(초)이 있으면 그 값, 없으면 `verify_minutes`×60이다.
- 시간을 넘기면 그룹에 SIGTERM, 5초 뒤 남았으면 SIGKILL을 보내고, 로그 끝에 `시간 초과: <N>분` 줄을 남기고 실패를 돌려준다. 자식을 백그라운드로 띄우는 verify(예: `sleep 300 & sleep 300`)로 시간 초과 뒤 그 자식 pid가 살아 있지 않음을 시험한다.
- 티켓 verify가 시간을 넘기면 실패 이유가 `검증 시간 초과(<N>분, 로그 <경로>)`이고, 기존 검증 실패처럼 같은 모델로 한 번 재시도한다(가짜 worker + `GS_VERIFY_TIMEOUT=1` + 멈추는 verify로 `gs go` 전체를 돌리는 시험).
- integration verify가 시간을 넘기면 병합하지 않고(phase `not_merged`), main verify가 시간을 넘기면 병합 커밋을 revert한다(시험).
- 시간 안에 끝나는 verify의 동작·로그 형식(finish의 `$ 명령`, `HEAD:`, `종료 코드:` 줄, worktree가 바뀌면 실패)은 그대로다. 기존 시험이 모두 통과한다.
- README의 spec frontmatter·실패 처리 설명에 `verify_minutes`와 `GS_VERIFY_TIMEOUT`이 들어간다.

## 범위 밖
- 출력 없음 기준 판정(`.out-of-scope/verify-idle-timeout.md`)
- worktree 정리(02)
- 이 feature의 spec frontmatter에 `verify_minutes`를 넣는 것(실행 엔진이 v0라 경고, spec §6)

## 참고
- spec §3(1-1–1-5, 2-3), §4 "verify 실행", §6
- 지금 verify를 돌리는 곳: `src/gs/go.py` `_verify`, `src/gs/finish.py` `_verify`
