---
id: "01"
title: "브랜치 밖 원인 표식을 남긴 수리 worker는 네트워크로 끊겨도 다시 띄우지 않는다"
blocked_by: []
touches: ["src/gs/go.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
수리 worker가 `브랜치 밖 원인: <이유>`를 남긴 뒤 네트워크 오류로 끝나도, 일시 오류 처리보다 표식 판정을 먼저 해 재시도하지 않고 사람에게 넘긴다.

## 완료 조건
- `_check_worker`에서 이번 실행에서 띄운(`a.launched`) 수리 worker가 커밋 없이 끝났고 마지막 메시지에 `브랜치 밖 원인:` 줄이 있으면, `_transient_end`가 일시 오류 이유를 돌려주더라도 `_net_hold`로 가지 않고 `_end_repair`로 가서 `retry=False`로 실패한다. 실패 이유와 보고 문구는 표식이 있는 지금의 `_end_repair` 경로와 같다.
- 표식이 없으면 네트워크 끊김은 지금처럼 `_net_hold`로 간다. 커밋을 남긴 수리 worker, 이번 실행에서 띄우지 않은 자리(앞 실행 메시지), 수리가 아닌 worker(구현·수정)의 일시 오류 처리는 바뀌지 않는다.
- 마지막 메시지를 읽지 못하면(로그 없음, 읽기 오류) 지금처럼 일시 오류 처리로 간다.
- 시험 `tests/test_verify_repair.py`: (1) 표식 + `turn.failed`의 `stream disconnected before completion` + 종료 1 + 커밋 0 → `_net_hold` 호출 0, `retry=False` 실패. (2) 같은 끊김에 표식 없음 → 지금처럼 네트워크 대기. (3) 표식 + 끊김이지만 이번 실행에서 띄우지 않은 자리 → 네트워크 대기 또는 지금 동작 유지. 순서를 되돌리면 (1)이 실패한다.
- `go.py` 머리말과 `_check_worker`·`_end_repair` docstring에 순서를 적는다.

## 범위 밖
- verify 명령의 `exec` 표지 문제(`goldstack-v22-01-1`, 이번 feature에 넣지 않음)
- 사용자 문서(07)

## 참고
- spec §3 1-2
- 아이디어 `goldstack-v27-03-1`(재현 명령과 이벤트 내용)
- `.goldstack/work/goldstack-v27/tickets/03-repair-end-message.md`
