---
id: "10"
title: "측정 필드: 처리 대기, 검증별 시간, 리뷰어별 시간·채택 수, 마무리 단계, 버전, 실제 모델"
blocked_by: ["09"]
touches: ["src/gs/state.py", "src/gs/go.py", "src/gs/finish.py", "src/gs/report.py", "src/gs/review.py", "tests/test_metrics.py"]
model: codex
reviewer: claude
---
## 목표
다음 시간 줄이기와 등급 조정을 측정으로 판단하게 한다. 시간 목표(130–160분)는 다음 feature 보고서의 이 값으로 확인한다.

## 완료 조건
- state.json에 다음이 남고, 시험이 값을 확인한다.
  - a 티켓 시도마다 worker 실제 종료 시각(`exit` 파일 시각)과 gs가 처리를 시작한 시각.
  - b gs가 돌린 검증마다 라벨, 명령, SHA, 걸린 시간, 결과(티켓 검증과 마무리 검증 모두).
  - c 리뷰어마다 걸린 시간, 지적 수, 채택(fix) 수.
  - d 마무리 단계별 걸린 시간.
  - e 실행한 gs 버전.
  - f 시도마다 실제 모델·effort(worker, 리뷰어).
- 보고서에 위 값의 요약이 있다: 티켓마다 실제 모델·effort와 시간, 리뷰어별 시간·채택 수, 마무리 시간, gs 버전, 일시 오류 횟수와 기다린 시간(06이 남긴 값).
- 이 필드가 없는 옛 state.json을 읽는 실행과 `gs status`가 깨지지 않는다. 시험이 있다.
- 측정 코드의 오류는 실행을 멈추지 않는다(측정은 잃어도 병합 판단은 그대로다). 시험이 있다.

## 범위 밖
- worker 안에서 돌린 시험 측정(gs가 볼 수 없다), 측정으로 스케줄 바꾸기(`async-coordinator`), `/retro` 변경.

## 참고
- spec §3 1-6, 2-8. 아이디어 `.goldstack/ideas/e2e-time-reduction.md` "측정 필드".
