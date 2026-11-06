---
date: "2026-11-06"
severity: "high"
source: "/retro goldstack-v17"
status: "taken"
issues: []
feature: "goldstack-v20"
---
worker가 이름으로 프로세스를 찾아 끄거나 기다려서 다른 티켓의 검증을 죽이거나 늦춘다.

- v17 티켓 04 worker가 12:16:50에 `pkill -f "unittest discover"`를 쳤다(`run/04/1/worker.log`). 티켓 01의 gs 검증은 11:56:52 시작, 1198초 소요로 같은 시각에 끝났고 로그는 `........`에서 끊겼다. 실패 줄도 `시간 초과` 줄도 없다. 수리 대기 10분, 수리 11분, 재검증 7분을 썼다.
- v18 티켓 01·02 worker는 `until ! pgrep -f "unittest discover"`로 기다렸고, 티켓 03 검증이 끝난 14:03:22에 함께 끝났다.
- 확인 못 한 것: v17 03의 exit 144와 05의 SIGTERM은 시각을 대조하지 않았다.

고칠 곳: `src/gs/hook.py`가 `pkill`·`killall`을 막고, worker brief가 자기 PID로 다루라고 적는다.
