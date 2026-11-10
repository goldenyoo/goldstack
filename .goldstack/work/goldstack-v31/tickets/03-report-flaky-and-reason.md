---
id: "03"
title: "보고서 Summary가 flaky 통과를 보이고, integration 검증 실패를 티켓 이유와 어긋나지 않게 쓴다"
blocked_by: ["02"]
touches: ["src/gs/report.py", "src/gs/finish.py", "tests/test_report_flaky.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
다시 돌려 통과한 검증이 보고서에서 숨지 않게 하고, not_merged인데 티켓 표가 "병합·검증됨"으로 읽히는 어긋남을 없앤다.

## 완료 조건
- 보고서 `## Summary`의 gs가 쓰는 상태 줄 아래(모델 요약이 아님, `_render`의 `summary_status` 쪽)에 이번 실행 검증 로그의 flaky 줄을 한 줄씩 넣는다.
  - 02의 줄: 지점·시험 파일과 함께. 예: `- flaky: 05 티켓 검증 test_resume_report (따로 돌려 통과, 전체 다시 통과)`
  - 기존 `flaky: <label> 재시도 N번 만에 통과` 줄: 파일을 모르므로 `- flaky: <지점> (전체 재시도 N번 만에 통과, 시험 파일 모름)`
  - flaky 줄이 없으면 지금과 같다.
- 마무리가 integration 계열 검증 실패로 `not_merged`이면(integration, integration-final, integration-recheck) 병합된 티켓의 기본 이유를 `integration에 병합(티켓 검증 통과) · <지점> 검증 실패`로 쓴다. `integration-recheck` 실패도 `failed_verify`를 남기게 `finish.py`를 고친다. 그 밖의 경우와 티켓에 따로 적힌 이유(`ts.reason`)는 그대로다.
- 시험 `tests/test_report_flaky.py`: 티켓·integration·main 로그의 새 flaky 줄 → Summary 줄, 옛 형식 → "시험 파일 모름" 줄, flaky 없음 → 변화 없음, not_merged(integration·final·recheck 각각) → 새 이유, verified → 지금 이유. 각 판정을 지우면 실패한다.

## 범위 밖
- 판별·재실행 동작(02), 사용자 문서(05)

## 참고
- spec §3 2-4, 2-7, §7 교차 검토
- 아이디어 `report-ticket-reason-not-merged`
