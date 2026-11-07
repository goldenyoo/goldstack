---
id: "03"
title: "보고서가 실패 시험 이름·revert 상태·변경 파일·worker 한계를 싣는다"
blocked_by: []
touches: ["src/gs/report.py", "tests/test_verify_failure_report.py", "tests/test_resume_report.py", "tests/test_final_report_on_base.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
보고서만 읽어도 무엇이 왜 실패했고 다음에 무엇을 할지 알게 한다.

## 완료 조건
- main 검증이 실패한 보고서의 Evidence 맨 앞에 `_failure_lines`가 찾은 실패 줄과 로그 경로가 실린다. 시험: 출력 끝부분이 `OK`이고 중간에 `FAIL: test_x`가 있는 main 로그에서 `test_x`가 보고서에 나온다.
- phase가 `reverted`이면 `## Summary` 바로 아래 첫 줄이 revert 상태와 다음 명령 `gs go <feature>`이다. 모델 요약을 다시 부르지 않고 코드로 넣는다.
- `후보 티켓(추정): 후보 없음`일 때 티켓별 실제 변경 파일 목록을 함께 보인다.
- 요약 모델 입력 `report-input.md`에 티켓별 worker 마지막 보고가 들어간다(믿을 수 없는 자료라고 표시한다). 보고서 크기 상한 처리는 그대로 동작한다.

## 범위 밖
- 실패 패턴 설정 키(결정 2-3)
- import 분석이나 시험 이름으로 원인 후보 찾기

## 참고
- spec §3 2-3, 2-4, 2-8
- 아이디어 `report-names-failed-tests`, `report-summary-revert-state`, `v7-blame-test-mapping`, `verify-interrupt-misses-uv-run`
