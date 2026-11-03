---
id: "07"
title: "ETA 이력: 이전 실행 중앙값으로 처음부터 예측"
blocked_by: ["03"]
model: codex
reviewer: agy
---
## 목표
이번 실행에서 티켓이 하나도 끝나지 않았을 때도 남은 시간을 보인다.

## 완료 조건
- 이번 실행에서 끝난 티켓이 없으면, 이 머신의 다른 feature `.goldstack/work/*/run/state.json`에서 merged 티켓의 소요(첫 단계 시작 ~ 끝)를 모아 중앙값 × 남은 티켓 ÷ max_workers로 `약 N분 남음(이전 실행 기준)`을 보인다. 표본이 없으면 지금처럼 `남은 시간 계산 중`(시험).
- 이번 실행에서 티켓이 하나라도 끝나면 지금 방식(이번 실행 평균)으로 바뀐다(시험).
- 읽지 못하는 state.json은 건너뛴다(시험: 깨진 JSON).
- 이전 실행 표본은 실행 시작 때 한 번 읽는다(매 저장마다 다시 읽지 않는다).

## 범위 밖
- 커밋된 report.md에서 읽기(spec 1-6에서 뺌)

## 참고
- spec §3 1-6, §6 ETA. touches: `src/gs/state.py` `src/gs/go.py` `tests/test_eta_history.py`
