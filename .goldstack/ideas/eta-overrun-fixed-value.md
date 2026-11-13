---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v37"
status: "taken"
issues: []
feature: "goldstack-v38"
---
도는 티켓이 평균 시간을 넘기면 남은 시간이 고정값에 멈춘다. goldstack-v37에서 "약 39분 남음"이 1시간 넘게 그대로였다.

- 이 세션이 `gs status`에서 직접 봤다. 01이 25분 40초 지났을 때도 1시간 34분 지났을 때도 "약 39분 남음(이전 실행 기준)"이었다.
- 39.2분 = `load_eta_history` 1516.0초 + `load_finish_history` 775.5초 + `MIN_RUNNING_S` 60초. `src/gs/state.py:396`은 평균을 넘긴 도는 티켓을 늘 60초 남은 것으로 센다(retro subagent 계산).
- 중앙값이 tier를 가리지 않는다. 01은 tier large였고 116분 걸렸다(state.json 14:46:59→16:43:02).
- 고칠 곳: `state.calculate_progress`. tier별 중앙값을 쓰거나, 예상을 넘긴 티켓은 "예상 N분 넘김"처럼 보인다. 시험도 함께 넣는다.
- 관련: 범위 밖 `eta-range-display`(다시 볼 조건: 새 계산을 쓴 실행에서도 오차가 커서 사람이 남은 시간을 믿지 못하게 되면)
