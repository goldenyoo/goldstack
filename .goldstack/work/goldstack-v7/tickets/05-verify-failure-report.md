---
id: "05"
title: "마무리 전체 검증이 실패하면 보고서에 실패 줄과 후보 티켓을 적는다"
blocked_by: ["02"]
touches: ["src/gs/finish.py", "src/gs/report.py", "tests/test_verify_failure_report.py"]
model: codex
reviewer: claude
---
## 목표
빠른 티켓 검증을 뚫고 나온 회귀가 마무리에서 잡혔을 때, 사람이 원인을 찾을 출발점을 보고서에 남긴다.

## 완료 조건
- `integration` 또는 `integration-final` 검증이 실패해 `not_merged`로 끝나면 report.md에 "검증 실패" 부분이 있고, 다음을 담는다.
  - 검증 로그의 실패 줄 최대 10개(`FAIL`, `ERROR`, `failed`, `not ok`를 포함하는 줄)와 로그 경로.
  - 후보 티켓: 실패 줄에 나온 파일 경로·이름이 티켓의 `touches`나 그 티켓이 실제 바꾼 파일과 겹치는 티켓. 없으면 `후보 없음`.
  - 후보가 추정이라는 표시.
- 시험 러너를 가정하지 않는다. unittest 형식이 아닌 로그(예: `not ok 3 test/foo.test.js`)로도 시험한다.
- 후보를 찾는 코드의 오류는 보고서 쓰기를 막지 않는다. 시험이 있다.
- 검증 통과 때 보고서는 지금과 같다. 시험이 있다.

## 범위 밖
- 실패 시험 되짚기, 수리 worker(`repair-worker`). 병합 판단 자체는 바꾸지 않는다.

## 참고
- spec §3 2-5, §6 integration 전체 검증 실패.
- `finish.run`의 `not_merged` 경로, `finish/integration-verify.log`.
