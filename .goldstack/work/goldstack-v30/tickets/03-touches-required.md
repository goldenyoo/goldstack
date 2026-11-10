---
id: "03"
title: "gs check 명령이 touches 없는 티켓을 오류로 막는다"
blocked_by: []
touches: ["src/gs/cli.py", "tests/test_touches.py", "tests/test_check.py", "tests/test_agy_config.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
grill이 touches 없는 티켓을 남기지 못하게, 사람이 치는 `gs check <f>`가 그 티켓을 오류로 막는다. `gs go`의 검사와 리뷰의 빈 touches 처리는 바꾸지 않는다(spec 3-3).

## 완료 조건
- `gs check` 명령(`cli.cmd_check`가 붙이는 검사, 예: `guard_problems` 옆)에서 티켓 frontmatter에 `touches`가 없거나 빈 목록이면 그 티켓 파일에 오류를 낸다. 예: `오류: .goldstack/work/f/tickets/01-x.md: touches가 없다(고칠 파일을 레포 루트 기준 경로로 적는다)`. 종료 1. `--only`면 그 범위의 티켓만 본다.
- `go.py`가 쓰는 `check.check()`의 결과와 `gs go`의 동작, `review.py`의 빈 touches 문장은 바뀌지 않는다. 시험 fixture(`tests/support.py` 등)의 touches 없는 티켓은 그대로 돈다.
- 시험(`tests/test_touches.py`): 키 없음 → 오류, `touches: []` → 오류, touches 있음 → 없음, `--only`로 범위 밖인 빈 티켓 → 없음, 같은 feature에 `gs go`가 쓰는 `check.check()`는 이 오류를 내지 않음. 판정을 지우면 실패한다.
- 옛 feature 호환 시험 셋(`tests/test_check.py` `test_goldstack_v0_passes`, `tests/test_agy_config.py` `test_v0_through_v3_tickets_and_legacy_config_still_pass`, `tests/test_touches.py` `test_v0_through_v3_have_no_errors_or_warnings`)은 v1–v3로 종료 0·stderr 빈 문자열을 유지하고, v0은 touches 오류로 종료 1인 것을 확인하게 바꾼다. `.goldstack/work/goldstack-v0/` 기록 파일은 고치지 않는다.

## 범위 밖
- `gs go`가 touches 없는 티켓을 거부하는 것과 `review.py` 예외 삭제(`.goldstack/out-of-scope/touches-required-in-go.md`)
- 교차 검토 경고(04), 사용자 문서(07)

## 참고
- spec §3 1-4, 3-1, 3-3
- 아이디어 `goldstack-v27-01-1`
