---
date: "2026-11-06"
severity: "medium"
source: "/retro goldstack-v17"
status: "taken"
issues: []
feature: "goldstack-v21"
---
신호로 죽은 검증을 일반 실패로 처리해 수리 worker를 띄운다. 로그에는 종료 코드도 남지 않는다.

- v17 티켓 01의 검증이 다른 worker의 `pkill`로 죽었는데([[worker-machine-wide-kill]]) gs는 `검증 실패`로 보고 수리를 띄웠다. 로그에 실패 줄이 없어 수리 worker는 원인을 못 찾고 커밋 없이 끝났고, 보고서와 아침 보고도 원인을 몰랐다.
- 시간 초과는 수리 없이 바로 티켓 실패로 가지만, 신호로 끊긴 것은 가르지 않는다. 실제 종료 코드는 기록되지 않아 값을 모른다.

고칠 곳: `src/gs/verify.py`가 로그 끝에 종료 코드를 남기고, `go._verify_failed`가 끊김이면 수리 없이 한 번 다시 검증한다. 범위 밖 `verify-log-per-attempt`와 같이 본다.
