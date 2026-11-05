---
id: "01"
title: "보고서 검증 표의 뜻 바로잡기"
blocked_by: []
touches: ["src/gs/metrics.py", "src/gs/report.py", "tests/test_metrics.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
보고서 검증 표가 틀린 추론을 부르지 않게 하고, 판단 입력에 실패 원인을 넣는다.

## 완료 조건
- `metrics.validation`에 티켓 시도와 티켓 head가 있고, 표의 열 이름이 뜻과 맞는다. integration head와 티켓 head가 구별된다. 옛 `state.json`도 읽는다.
- `ticket-09/1`처럼 시도로 오해할 표기가 없다.
- 보고서 판단 입력(`report-input.md`)에 실패한 시험 줄이 있다. `verify.log`가 없으면 없다고 적는다.
- 시험: 같은 티켓의 네 시도, integration 끝이 같은 두 검증, 실패 줄 포함.

## 범위 밖
- 보고서의 다른 칸: 티켓 02·08.

## 참고
- `.goldstack/ideas/report-verify-row-meaning.md`
- `metrics.py`, `report.py` docstring도 고친다
