---
id: "07"
title: "진행 바의 남은 시간을 의존 일정과 마무리로 계산한다"
blocked_by: ["06"]
touches: ["src/gs/state.py", "src/gs/go.py", "tests/test_progress.py", "tests/test_eta_history.py", "tests/test_progress_finish_cleanup.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
진행 바의 남은 시간이 실제보다 크게 짧게 나오지 않게 한다. 의존 사슬, 도는 티켓의 쓴 시간, 마무리를 계산에 넣는다.

## 완료 조건
- `calculate_progress`가 티켓 의존(`blocked_by`)과 `max_workers`로 남은 일정을 흉내 낸다. 직렬 세 티켓은 `max_workers = 3`이어도 나누어지지 않는다. 예: 첫 티켓이 10분 걸렸고 둘이 남으면 약 20분이다.
- 도는 티켓은 끝난 티켓 평균에서 쓴 시간을 뺀 값으로 센다. 평균을 넘겼으면 1분으로 센다.
- 티켓 소요 예상은 끝난 티켓의 평균이다. 등급별로 나누지 않는다(spec §6). 끝난 티켓이 없으면 지금처럼 이전 실행 중앙값을 쓰고 `(이전 실행 기준)`을 붙인다.
- 같은 레포 다른 feature의 `run/state.json`에서 마무리 시간(마지막 티켓 종료부터 실행 종료까지)의 중앙값을 읽어 남은 시간에 더한다. 재개가 섞인 실행(이번 시작 전 단계를 가진 티켓이 있는 state)은 표본에서 뺀다. 깨진 기록은 건너뛴다.
- 표기: 마무리 값이 있으면 `약 N분 남음`, 없으면 `약 N분 남음 + 마무리`. 마무리 중에 값이 있고 아직 남았으면 `약 N분 남음`, 값이 없거나 넘겼으면 `마무리 중`이다. 어느 경우에도 마무리 중에 `약 0분 남음`이 나오지 않는다. 진행 바의 나머지 칸은 그대로다.
- `eta_s`는 표기와 같은 값이다. `마무리 중`이면 `None`이다.
- `go.py`의 `Run.save`가 새 입력을 넘긴다. 마무리 표본은 실행 시작에 한 번만 읽는다.
- 시험: 직렬, 병렬, 도는 티켓의 쓴 시간, 평균 초과, 마무리 값 있음·없음, 마무리 중, CI 대기 중, 재개가 섞인 표본 제외, 이전 실행 기준.

## 범위 밖
- 범위 표기(범위 밖 `eta-range-display`).
- 재시도·수정 단계의 예측, 등급별 평균.
- mod(`hooks/register.tsx`) 변경. mod는 `progress.line`을 그리기만 한다.
- 문서(10).

## 참고
- spec §3의 2-1–2-3, §6의 ETA 재생 측정, `.goldstack/ideas/eta-accuracy.md`
