---
id: "07"
title: "worker hook이 기계 전체를 끄는 pkill·killall을 막는다"
blocked_by: ["01"]
touches: ["src/gs/hook.py", "tests/test_hook.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker가 이름으로 프로세스를 끄다가 다른 티켓의 검증을 죽이는 일을 막는다.

## 완료 조건
- `GS_ROLE=worker`에서 `pkill`과 `killall`을 막는다. `bash -c`, `xargs`, `sudo`, 경로를 붙인 형태(`/usr/bin/pkill`)도 막는다. 이유 문장이 PID로 끄라고 안내한다.
- `kill <PID>`와 `pgrep`은 통과한다. `GS_ROLE`이 worker가 아니면 그대로 통과한다.
- 위 각 경우와 실제 사례 `pkill -f "unittest discover"`를 시험한다. `src/gs/hook.py` 모듈 설명의 막는 것 목록에 더한다.

## 범위 밖
- `kill`의 PID가 자기 것인지 판정하는 일. brief 규칙은 티켓 08이, 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 4-1. 아이디어 `worker-machine-wide-kill`. `check_segment`에 이름 비교로 넣으면 `strip_prefix`와 `bash -c` 재귀가 형태를 맡는다.
