---
id: "01"
title: "claude worker가 ScheduleWakeup·CronCreate를 쓰지 못하게 막는다"
blocked_by: []
touches: ["src/gs/adapters.py", "tests/test_adapters.py", "tests/test_isolation.py", "tests/test_hook.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
claude worker(구현·수정·수리)가 건 wakeup이 일이 끝났거나 턴이 죽은 뒤에도 세션을 붙잡아 티켓이 노는 일을 없앤다(spec 결정 2-1, 아이디어 worker-disallow-schedule-wakeup).

## 완료 조건
- `adapters.Claude`의 `--disallowedTools` 목록이 `"Bash(git push *)" "Bash(gh *)" Monitor ScheduleWakeup CronCreate`다. 수정·수리 worker도 같은 명령을 쓴다(지금처럼).
- 클래스 docstring에 두 도구를 막는 이유(일을 마친 뒤에도 세션을 붙잡는다. 백그라운드 Bash는 끝나면 스스로 알린다)를 적는다.
- `tests/test_adapters.py`·`tests/test_isolation.py`·`tests/test_hook.py`(`test_worker_keeps_tool_block_as_second_guard`)의 `--disallowedTools` 단언이 두 도구를 포함하는 새 목록을 확인한다. 두 도구 중 하나를 빼면 실패한다.
- 시험은 실제 시간에 기대지 않는다.

## 범위 밖
- 리뷰어(`--tools` 허용 목록을 쓴다)와 판단 모델 호출
- 403 분류(02)

## 참고
- spec §3 결정 2-1, §6 환경 사실
