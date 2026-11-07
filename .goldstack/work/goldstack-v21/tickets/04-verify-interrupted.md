---
id: "04"
title: "신호로 끊긴 검증은 수리 없이 한 번 다시 돌린다"
blocked_by: ["02"]
touches: ["src/gs/verify.py", "src/gs/go.py", "tests/test_verify.py", "tests/test_verify_repair.py", "tests/test_verify_failure_report.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
다른 프로세스가 죽인 검증을 코드 결함으로 착각해 수리 worker를 띄우고 원인을 잃는 일을 없앤다.

## 완료 조건
- 검증 로그 끝에 종료 코드 줄이 남는다. 통과와 시간 초과도 같다.
- 종료 코드가 음수거나 128보다 크거나, 이번 실행 분량의 로그에 줄 처음부터 `xargs: … terminated with signal N`이나 `killed by signal N` 형태가 있으면 끊김이다. 앞선 재시도의 출력은 판단에 쓰지 않는다.
- 티켓 검증이 끊기면 수리 worker를 띄우지 않고 같은 트리로 한 번 다시 검증한다. 보고서와 `gs go` 출력에 끊김이라고 나온다.
- 다시 검증이 통과하면 병합한다. 끊김이 아닌 실패면 일반 실패처럼 수리로 간다. 또 끊기면 티켓 실패이고 이유에 끊김이 보인다.
- 다시 검증 중 gs가 죽어도 다음 `gs go`가 이어 간다. 옛 `state.json`을 읽을 수 있다.
- 시간 초과, 병합 충돌, 검증 중 integration이 바뀐 경우의 처리는 그대로다.
- 시험은 실제 프로세스에 신호를 보내 위 경우를 확인하고 실제 시간에 기대지 않는다. `xargs` 문구는 이 맥의 실측 값으로 고정한다.
- `go.py` docstring과 `verify.py`가 이 동작과 맞는다. 새 예외를 만들면 `_KIND_WORDS` 낱말로 짓는다.

## 범위 밖
- 마무리(`finish`) 검증의 처리: 티켓 검증만 고친다. 시도별 로그 누락 표시: 범위 밖 `verify-log-per-attempt`.

## 참고
- spec 결정 2-5, §6의 신호 측정. 아이디어 `verify-killed-by-signal`.
