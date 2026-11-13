---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v38"
status: "taken"
issues: []
feature: "goldstack-v39"
---
검증 줄에서 기다린 시간이 "재리뷰" 단계 시간으로 기록되어, 보고서의 단계별 시간이 틀린다.

- goldstack-v38 05: 보고서는 "재리뷰 8분"인데 codex 재리뷰 호출은 38.7초였다. 05 검증은 06 검증이 끝난 21:12:21 이후에 시작했다.
- `go.py`의 병합 줄 서기 분기가 `say`만 하고 `_wait_phase`를 부르지 않는다(retro subagent가 읽음).
- 고칠 곳: `go._merge`의 줄 서기에서 `_wait_phase(r, a.t.id, "merge-wait")` 같은 단계를 남기고, 보고서 단계 이름에 넣는다.
- 관련: `ticket-verify-ten-minutes`(검증 자리가 하나라 줄이 생긴다)
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
