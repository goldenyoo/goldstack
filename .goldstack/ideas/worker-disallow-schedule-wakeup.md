---
date: "2026-11-13"
severity: "high"
source: "/retro goldstack-v38"
status: "taken"
issues: []
feature: "goldstack-v39"
---
claude worker가 건 `ScheduleWakeup`이 일이 끝났거나 턴이 죽은 뒤에도 세션을 붙잡아, 일렬 경로 티켓이 15분 넘게 논다.

- goldstack-v38 01(일렬 경로 맨 앞): 09:42:50 UTC에 1200초 wakeup을 걸었고, 깨어난 턴이 `API Error: 403 Attention Required! | Cloudflare`로 죽었다. 커밋 전인 채 10:03:03 wakeup까지 924초를 놀았다(`run/01/1/worker.log`, `ScheduleWakeup` 4회. 이 세션이 403 문구와 횟수를 확인했다).
- [반복] goldstack-v36 `run/03/1/fix/worker.log`: 최종 보고 뒤에도 wakeup이 남아 1067초를 놀았다.
- 고칠 곳: `src/gs/adapters.py`의 claude worker `--disallowedTools`(지금 `"Bash(git push *)" "Bash(gh *)" Monitor`)에 `ScheduleWakeup`(필요하면 `CronCreate`)을 더한다. `Monitor`를 막은 것과 같은 방식이다.
- `cloudflare-403-transient`와 함께 고친다. 이것만 고치면 놀던 시간이 403 영구 오류로 끝난 티켓 실패로 바뀔 수 있다.
- 관련: `worker-mutation-test-cost`(v37 wakeup 합계 언급), taken `worker-disallow-monitor`
- 근거 출처: retro subagent 보고. 403 문구와 wakeup 횟수, `--disallowedTools` 값은 이 세션이 확인했다.
