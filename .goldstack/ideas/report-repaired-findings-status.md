---
date: "2026-11-13"
severity: "high"
source: "/retro goldstack-v36"
status: "taken"
issues: []
feature: "goldstack-v38"
---
보고서가 수리 커밋과 재검증으로 해소된 지적을 "재현된 미수리"로 남겨, 남은 high를 실제(1건)보다 많은 8건으로 센다.

- goldstack-v36 report(origin/main)의 재현된 미수리 high 8건 중 7건은 03 티켓의 "기존 시험 9개 충돌" 지적이다. 나머지 1건은 `failure.py` 64KiB 잘림이다.
- 수리 커밋(`run/03/1/rereview-repair-codex/repair.patch`)이 `test_recheck_resolved.py`·`test_review_target.py`의 fixture severity를 낮췄다. `test_async_review.py`는 같은 fixture를 import한다. 수리 재검증(#7)과 integration 검증(#9)이 통과했다.
- 그런데도 report는 "지적 상태는 미수리 그대로"라고 적고 7건을 high로 센다. 사람은 남은 위험을 8건으로 읽는다.
- 고칠 곳: gs가 지적 상태를 정하고 report를 만드는 부분. 수리 커밋 뒤 검증이 통과한 지적을 "수리로 해소" 같은 별도 상태로 바꾼다.
- 근거 출처: retro subagent 보고. 파일을 직접 열어 봤다고 함. 이 세션이 다시 확인하지는 않았다.
- 관련: 열린 아이디어 `goldstack-v36-03-*`(같은 지적이 아이디어로도 들어가 있다)
