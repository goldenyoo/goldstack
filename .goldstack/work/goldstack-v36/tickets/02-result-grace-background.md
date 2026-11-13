---
id: "02"
title: "유예 정리: 배경 작업을 기다리는 worker는 정리하지 않는다"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/streamfmt.py", "tests/test_result_grace.py"]
closes: [65]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
성공 `result` 뒤 배경 작업을 기다리다 다시 깨어나는 claude worker를 유예 정리가 죽이지 않게 한다(spec 1-8, 아이디어 `result-grace-kills-resumed-worker`).

## 완료 조건
- `streamfmt.ResultWatch`가 마지막 끝 이벤트와 함께 마지막 `{"type":"system","subtype":"background_tasks_changed"}`의 `tasks` 수를 기억한다. 그 이벤트가 없으면 0이다.
- `go`의 유예 정리(`Active.result_seconds`·`_overdue_result`): 마지막 끝 이벤트가 성공이어도 그 시점의 배경 작업 수가 0보다 크면 유예를 쓰지 않는다(`idle_minutes` 시간 초과만 본다). 그 뒤 `background_tasks_changed`가 빈 목록이 되고 성공 끝 이벤트가 다시 나오면 그때부터 잰다.
- 유예 시계는 로그가 자라거나 브랜치 커밋이 바뀌면 다시 시작한다(`Active.idle`과 같은 신호, 모든 계열). `_wait_any`는 정리 판정 전에 그 활동을 새로 읽는다(지금은 `_overdue_result`가 `idle`보다 먼저다). `Active.result_seconds`·`go.py` 머리 docstring의 "처음 본 때부터, 로그가 자라도 다시 시작하지 않는다" 문장을 고친다.
- `tests/test_result_grace.py`에 가짜 worker 시험:
  - 성공 `result`(직전 `background_tasks_changed` 작업 1개) → 유예보다 긴 침묵 → `task_notification` → 커밋 → `result`(작업 0개) → 종료. 정리되지 않고 종료 코드·커밋이 그대로다.
  - 작업 없는 성공 `result` 뒤 끝나지 않는 worker(#65 형태)는 지금처럼 유예 뒤 정리된다.
  - 성공 `result` 뒤 유예 안에 로그가 자라면 시계가 다시 시작한다. 유예가 끝나는 회차에 로그만 자란 경우, 커밋만 바뀐 경우 모두 정리하지 않는다.
  - `ResultClockTest.test_clock_starts_at_first_success_and_does_not_restart_when_log_grows`(217행)는 새 동작을 단언하는 시험으로 바꾼다.
- 시험은 실제 시간에 기대지 않는다(유예는 `_result_grace`를 바꾸고, 시계는 바꿀 수 있게).

## 범위 밖
- `result_grace_seconds` 기본값과 이 레포 `.goldstack/config.toml`의 `0`(v37 마지막 티켓이 지운다)
- codex의 배경 작업 판정(codex 로그에는 배경 작업 이벤트가 없다. 배경 작업 판정만 claude `background_tasks_changed`로 하고, 시계 재시작은 codex에도 적용한다)

## 참고
- spec §6 측정(v30–v35에서 `result`가 둘 이상인 6개 시도)
- `.goldstack/ideas/result-grace-kills-resumed-worker.md`, `.goldstack/work/goldstack-v35/run/06/1/fix/worker.log` 341–372행
