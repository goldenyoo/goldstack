---
id: "05"
title: "재시도가 병합되면 옛 시도의 지적 파일을 닫는다"
blocked_by: []
touches: ["src/gs/findings.py", "tests/test_findings_ideas.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
재시도로 버려진 코드에 대한 지적이 새 지적과 함께 열린 아이디어로 남는 일을 없앤다.

## 완료 조건
- 보고서 커밋을 만들 때, 이번 실행에서 병합된 티켓의 지적 파일 중 지금 state의 `idea_number`에 없고 `status: open`인 파일은 `status: dropped`가 되고 본문 끝에 재시도로 대체됐다는 한 줄이 붙는다.
- `taken`, `dropped`인 파일과 지금 state에 번호가 있는 파일, 병합되지 않은 티켓의 파일, 다른 티켓의 파일은 바이트까지 그대로다. 이름이 비슷한 티켓(`A_1`, `A-1`)도 섞이지 않는다.
- 파일을 못 고쳐도 경고만 남기고 실행 결과는 그대로다. 재개로 두 번 돌아도 결과가 같다.
- `findings.copy_to_base`와 함께 돌 때 base 쪽 결과도 같은 상태가 되는지 시험한다.
- `findings.py` 머리 설명이 이 동작과 맞는다.

## 범위 밖
- 판단 모델 비교와 문장 유사도: spec 결정 2-6. 같은 시도 안의 비슷한 지적은 합치지 않는다.

## 참고
- spec 결정 2-6, §6. 아이디어 `findings-dup-after-edit`.
