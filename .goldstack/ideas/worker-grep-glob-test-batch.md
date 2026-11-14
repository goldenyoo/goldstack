---
date: "2026-11-14"
severity: "high"
source: "/retro goldstack-v39"
status: "taken"
issues: []
feature: "goldstack-v40"
---
worker가 grep으로 고른 시험 파일 목록을 `xargs`·`$변수`로 러너에 넘겨 hook의 시험 파일 수 상한(10)을 우회하고, 느린 파일까지 넓게 돌려 일렬 경로 머리 티켓에서 약 10분을 썼다.

- goldstack-v39 03 `run/03/1/worker.log`: `files=$(grep -lE "phases|PHASE_LABELS|_merge\b|…" tests/test_*.py) … xargs -P 4 … -p $0`로 시험 파일 37개를 돌렸다. 600초 Bash 시간 제한을 넘겼고 목록에 가장 느린 `test_verify_repair`·`test_review_target`이 들어 있었다. 880초 worker 중 약 10분. 03은 일렬 경로(03→04→06)의 머리다.
- 같은 시간대의 01 검증이 790초로 다른 회차(646–672초)보다 길었다. 경합 탓으로 보지만 확인하지 않았다.
- [반복] goldstack-v36 03과 03 fix에도 같은 `grep -l … tests/test_*.py | xargs` 모양이 있다. taken `worker-full-test-hook-block`(v26)과 같은 종류의 실패다.
- 원인: brief `CHANGED_NAMES_RULE`(`src/gs/worker.py`)이 "grep해 나온 시험 파일을 모두 파일마다 따로 돌린다"고 지시한다. hook `max_files`는 명령에 글자로 적힌 파일 이름만 센다. deny에는 `ls tests | … xargs`만 있다.
- 고칠 곳 두 가지:
  - `.goldstack/config.toml` `[hook.worker_tests] deny`: `tests/test_*.py` glob을 `xargs`·러너로 넘기는 모양과 `-p $변수` 모양.
  - `worker.py` `CHANGED_NAMES_RULE`: 바꾼 식별자를 정확히 grep하고, 나온 파일이 상한을 넘으면 그 식별자를 직접 부르는 파일만 돌린다.
- 근거 출처: retro subagent 보고(로그를 직접 열었다고 함). 이 세션이 다시 확인하지는 않았다.
