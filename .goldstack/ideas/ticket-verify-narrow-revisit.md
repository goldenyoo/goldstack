---
date: "2026-11-10"
severity: "medium"
source: "/retro goldstack-v31"
status: "dropped"
issues: []
feature: ""
---
[반복] 티켓마다 도는 전체 검증이 실행의 큰 비중이라 out-of-scope `ticket-verify-narrow`의 다시 볼 조건이 충족됐다.

- goldstack-v31: 05를 뺀 티켓 검증이 각 약 9.3분. 일렬 경로 01→02→03→05에서 티켓 검증 3번과 integration 검증이 91분 중 약 37분(`run/state.json`).
- goldstack-v30: 검증 11번이 각 약 550초.
- v31 05의 좁은 `verify:`는 2초에 문제없이 끝났다.

제안: 다음 grill에서 `ticket-verify-narrow`를 다시 다룬다(티켓은 좁은 검증, 전체 시험은 integration에서만). 회고 subagent 보고를 옮겼다.
