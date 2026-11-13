---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v37"
status: "open"
issues: []
feature: ""
---
worker가 brief의 변이 지시("되돌려 실패를 본다")를 넓은 시험 묶음으로 돌려 시간을 쓰고, `.pyc` 재사용으로 거짓 통과까지 봤다.

- goldstack-v37 01 worker는 3605초가 걸렸다. `run/01/1/worker.log`의 ScheduleWakeup 예약 합이 300+600+1200+900+600 = 3600초다.
- 같은 로그: "M2 … 900초 시간 제한까지 걸리므로", "`.pyc` 재사용 때문에 처음에 통과로 나왔고"
- 지시 출처: `run/01/1/brief.md:11-12`("되돌려 실패를 본다" / "지우면 실패하도록")
- 고칠 곳: worker brief 템플릿의 그 두 줄. 변이를 돌릴 때 `PYTHONDONTWRITEBYTECODE=1`을 쓰고, 변이마다 짧은 timeout을 두고, 대상 시험 파일만 돌리라고 적는다. 또는 gs에 변이 실행 도우미를 둔다.
- 근거 출처: retro subagent 보고(로그를 직접 열어 봤다고 함). 이 세션이 다시 확인하지는 않았다.
