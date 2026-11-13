---
id: "06"
title: "ETA를 tier별 중앙값으로, 예상을 넘긴 티켓은 넘김 표시"
blocked_by: ["04"]
touches: ["src/gs/state.py", "src/gs/check.py", "src/gs/go.py", "tests/test_progress.py", "tests/test_eta_history.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
도는 티켓이 평균을 넘겨도 남은 시간이 한 값에 멈추지 않게 한다(spec 결정 2-5, 아이디어 eta-overrun-fixed-value).

## 완료 조건
- 진행 계산(`state.calculate_progress`)이 티켓마다 예상을 이 순서로 고른다: (a) 이번 실행에서 끝난 같은 tier 티켓들의 평균, (b) 그 tier의 지난 실행 중앙값(`gs check`의 `실측(지난 실행)`과 같은 표본, `check.tier_samples`), (c) 지금 계산(이번 실행 전체 평균, 없으면 지난 실행 전체 중앙값). tier가 없는 티켓은 (c)다. 표본 함수는 순환 import 없이 한 곳에 둔다. `gs check`의 `실측(지난 실행)` 줄 출력은 그대로다(`tests/test_check.py`).
- 예상을 넘긴 도는 티켓은 진행 줄에 `<id> 예상 <N>분 넘김(+<M>분)`이 보이고, 전체 남은 시간 줄에도 넘긴 티켓이 있다는 표시가 붙는다.
- `tests/test_progress.py`: (1) large 표본 48분·전체 25분일 때 large 티켓 30분 경과면 남은 시간이 약 18분 기준이다, (2) 60분 경과면 `예상 48분 넘김(+12분)`이 보인다, (3) tier 없는 티켓은 전체 중앙값. 시각은 고정값을 넘기고 실제 시간에 기대지 않는다. (1)은 tier 선택 코드를 되돌리면 실패한다.
- 옛 state·tier 없는 feature도 오류 없이 지금처럼 계산한다.

## 범위 밖
- 범위 표시(범위 밖 `eta-range-display`)

## 참고
- spec §3 결정 2-5
