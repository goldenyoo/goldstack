---
id: "11"
title: "시험 도우미 sh가 실패 메시지에 stderr를 싣는다"
blocked_by: []
touches: ["tests/support.py", "tests/test_support_sh.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
시험 안의 명령이 실패했을 때 원인이 로그에 남게 한다. v21 main 검증은 `git clone` 실패의 stderr가 버려져 원인을 알 수 없었다.

## 완료 조건
- `tests/support.py`의 `sh`가 실패하면 예외 메시지에 그 명령의 stderr가 보인다.
- 예외 종류는 `subprocess.CalledProcessError` 그대로이고 `returncode`, `cmd`, `stdout`, `stderr`도 그대로다. 성공할 때의 반환값은 바뀌지 않는다.
- `tests/test_support_sh.py`가 실패 메시지의 stderr, 예외 속성, 성공 반환값을 시험한다. stderr를 싣는 코드를 지우면 실패한다.

## 범위 밖
- main 검증 실패 전 재검증: 아이디어 `main-verify-retry-before-revert`. 보고서의 실패 시험 이름: 아이디어 `report-names-failed-tests`.
- `sh` 밖의 시험 도우미와 `test_revert_landed_through_side_pr` 자체는 고치지 않는다.

## 참고
- spec 결정 3-1, §6. 아이디어 `test-helper-keeps-stderr`.
