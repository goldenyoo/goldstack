---
id: "04"
title: "단계별 시각과 progress 필드(ETA), 보고서의 단계별 소요"
blocked_by: ["03"]
model: codex
reviewer: claude
---
## 목표
`gs go`가 티켓마다 단계(worker, review, fix, verify, finish)별 시각을 남기고, state.json에 진행 요약 `progress`를 계속 갱신한다. 진행 바(05)는 이 값을 그리기만 한다.

## 완료 조건
- 티켓 상태에 단계별 시작 시각이 남는다(재시도는 시도별로 덮어쓰지 않고 구분된다). 기존 state.json(단계 시각 없음)을 읽어도 오류가 없다(시험).
- state.json의 `progress`가 spec §4 형식대로 상태가 바뀔 때마다 갱신된다: done·total(범위 안 티켓), running(id·phase·model), elapsed_s, eta_s, line. 마무리 중에는 phase `finish`(시험: 가짜 worker로 `gs go`를 돌리며 중간 state.json을 읽어 phase가 바뀌는 것을 본다).
- ETA는 spec §4 규칙: 끝난 티켓 평균 × 남은 수 ÷ max_workers(정수 분 반올림), 끝난 티켓이 없으면 null과 "남은 시간 계산 중". line 형식은 `▓▓▓░░░░░ <feature> 3/8 · 04 리뷰 중(codex) · 24분 · 약 40분 남음`(바 8칸, 시험: 계산 함수 단위 시험).
- report.md 티켓 결과에 `단계별 소요: worker 9분 · 리뷰 4분 · 수정 2분 · 검증 3분`이 나온다(없던 단계는 빠짐, 시험).
- `gs status` 출력 끝에 `progress.line` 한 줄을 보인다.
- 기존 시험이 모두 통과한다.

## 범위 밖
- 지난 실행 기록으로 ETA 예측(`.out-of-scope/progress-eta-history.md`)
- 바를 그리는 mod(05), 텔레그램(06), README(08)

## 참고
- spec §3(1-4, 1-10), §4 "state.json `progress`"
- 상태 저장: `src/gs/state.py`, 루프: `src/gs/go.py`, 보고서: `src/gs/report.py`, 상태 표: `src/gs/status.py`
