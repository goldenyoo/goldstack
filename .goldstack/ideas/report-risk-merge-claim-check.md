---
date: "2026-11-10"
severity: "high"
source: "/retro goldstack-v31"
status: "taken"
issues: []
feature: "goldstack-v33"
---
보고서 "남은 위험"이 worker의 병합 상태 주장을 확인 없이 옮겨 없는 위험을 적었다.

- goldstack-v31 report "남은 위험 3": "05가 04 병합 전에 CHANGELOG를 썼다"(worker 보고). 실제로는 05의 base 2da0b8b에 Merge 04(9fb522d)와 수정 6b77f38이 이미 있고 CHANGELOG 10행이 최종 동작과 맞는다.
- 원인: brief가 blocked_by 티켓 중 이미 병합된 것을 알려 주지 않고, 요약 단계가 worker 주장을 그대로 옮겼다. v28에도 worker 주장이 위험 칸으로 넘어갔다.

고칠 곳: brief에 "base에 이미 병합된 티켓·commit"을 적는다. 요약 단계는 병합 상태 주장을 git으로 대조한 뒤에만 위험으로 적는다.
