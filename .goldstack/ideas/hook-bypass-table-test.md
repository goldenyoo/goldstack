---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v36"
status: "open"
issues: []
feature: ""
---
hook 셸 해석의 우회를 리뷰어와 사람이 손으로 찾는다. 우회 명령 표를 회귀 시험으로 만들어 verify에 넣는다.

- goldstack-v36 01 리뷰에서 high 회귀 5건이 나왔다. 리뷰어가 매번 실제 `/usr/bin/env -S` 실행 결과를 `hook.decide`와 손으로 대조해 재현했다(state.json findings evidence).
- 수정이 다음 회귀를 낳는 연쇄가 2라운드 이어졌다. 이 내용은 agy 요약에서 옮긴 것이다.
- report는 "0.2.20 설치본에서 spec §6 우회 명령이 모두 막히는지"를 사람 확인 항목으로 남겼다.
- [반복] goldstack-v35: 회고의 high도 같은 hook 우회였다(v36 spec.md 12행).
- 고칠 곳: tests/에 우회 명령 표 기반 회귀 시험을 두고 verify에 넣는다. 가능하면 실제 env·sh 실행 결과와 판정을 비교하는 차분 시험으로 만든다.
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
