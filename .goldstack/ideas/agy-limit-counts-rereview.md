---
date: "2026-11-06"
severity: "high"
source: "/retro goldstack-v12, v13, v14, v15"
status: "open"
issues: []
feature: ""
---
`gs check`의 agy 상한 검사가 재리뷰를 세지 않아, 경고 0으로 시작한 실행에서 두 번째 리뷰가 빠진다.

**근거**: `check.py`는 티켓에 배정된 계열 수만 세어 goldstack-v15의 3회가 `agy.max_calls_per_run=3`과 같다며 경고 0을 냈다. 실제로는 재리뷰 호출까지 쌓여 `agy 사용: 3/3`이 되고, 02의 agy 재리뷰와 05의 두 번째 리뷰가 건너뛰어졌다. 02의 high 지적 하나가 `확인 못 함(한도)`으로 남았다. 계정 한도 때문이 아니다. 공용 주간 한도는 그 밤에 약 1%만 줄었다.

**제안**: `src/gs/check.py`가 두 번째 리뷰어를 재리뷰까지 포함해 세어(예: 티켓당 2회) 넘을 것 같으면 경고한다. 이 레포의 `agy.max_calls_per_run`을 올릴지는 grill에서 정한다(재는 값: `/usage` 공용 주간 잔량). 두 번째 리뷰가 빠진 티켓은 끝 출력에서 눈에 띄게 한다. 관련: [[report-only-high-visibility]]

- 2026-11-06 사람의 답: 이 레포의 `agy.max_calls_per_run`을 6으로 올린다. 다음 grill 후보. (출처: goldstack-v12–v15 아침 보고)
