---
id: "04"
title: "_cli_version이 시간 초과를 구분하고 시험이 실제 시간에 기대지 않는다"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_format.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
부하가 걸리면 떨어지던 `test_cli_version_keeps_the_number_only`를 고치고, 결함 보고의 환경 줄에서 시간 초과와 "숫자 없음"을 구분한다.

## 완료 조건
- `feedback._cli_version`은 `subprocess.TimeoutExpired`면 `모름(시간 초과)`, 그 밖의 실행 오류와 숫자 없음은 지금처럼 `모름`을 돌려준다. 버전 숫자만 돌려주는 동작과 빈 임시 디렉터리 cwd는 그대로다.
- `tests/test_feedback_format.py`의 버전 시험은 `subprocess.run`을 mock해 실제 프로세스·시간에 기대지 않는다: 숫자만 남김, 숫자 없음 → `모름`, `TimeoutExpired` → `모름(시간 초과)`, 종료 코드 1 → `모름`. 시간 초과 분기를 지우면 실패한다.
- 결함 보고 형식 시험(`test_feedback_format.py`의 다른 시험)과 `_KIND_WORDS` 규칙은 통과를 유지한다.

## 범위 밖
- 검증 재실행(02), 사용자 문서(05)

## 참고
- spec §3 2-5
- 아이디어 `cli-version-test-timeout`
