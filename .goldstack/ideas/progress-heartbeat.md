---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 보고서"
status: "taken"
feature: "goldstack-v3"
---
[medium] 진행 바가 worker가 10분 넘게 돌면 사라진다: `progress`는 상태가 바뀔 때만 갱신되고 mod는 최근 10분 안에 바뀐 state만 그린다. gs가 주기적으로 progress를 갱신(heartbeat)하거나 mod 기준을 바꾸기. 레포 하위 디렉터리에서 연 세션에서도 안 보임

출처: goldstack-v2 보고서
