---
date: "2026-11-13"
severity: "low"
source: "goldstack-v37 grill 라운드 2-1"
status: "open"
issues: []
feature: ""
---
첫 티켓 검증 도중 gs가 멈추면(Ctrl-C, 예외) 다음 `gs go`가 그 티켓을 worker부터 새로 시작한다. 같은 SHA를 다시 검증하면 worker·리뷰 시간(30–60분)을 아낀다.

- 지금: 첫 검증으로 넘어갈 때 일반 티켓의 재개 표시를 지운다(`go._review_tick`의 `_set(network_resume={})`). 재개는 표시가 없으면 "새로 시작한다"(`go._begin`). 같은 SHA 다시 검증은 검증 명령이 신호로 죽은 결과를 받았을 때(`_verify_interrupted`, `verify_again`)와 그 다시 검증 도중 멈췄을 때뿐이다(goldstack-v37 spec §6, 교차 검토 2).
- 제안: 검증 호출 전에 대상 SHA·트리와 함께 재개 표시를 남긴다. "다시 검증이 또 끊기면 실패" 규칙과 섞이지 않게 `verify_again`과 따로 둔다.
- goldstack-v37은 비동기 검증과 재개 변경을 섞지 않으려 뺐다(결정 2-1).
