---
id: "03"
title: "hook: worker 세션에서 돈 touches 밖 시험 파일 수를 누적해 막는다"
blocked_by: ["01"]
touches: ["src/gs/hook.py", "src/gs/config.py", "src/gs/adapters.py", "src/gs/worker.py", ".goldstack/config.toml", "tests/test_hook_worker_tests.py", "tests/test_config.py", "tests/test_hook_session_tests.py"]
tier: medium
model: codex
reviewer: claude
second_reviewer: agy
---
## 목표
worker가 grep으로 고른 시험 파일을 `max_files` 아래 묶음으로 나눠 돌리면 명령 하나만 보는 hook이 막지 못한다(goldstack-v40 03 21개, v41 01 14개). worker 세션 전체에서 touches 밖 시험 파일을 누적해 센다.

## 완료 조건
- `[hook.worker_tests]`에 새 키 `max_outside_files`(정수, 1 이상). 없으면 이 판정은 꺼짐이다. `gs init` 템플릿(DEFAULT_CONFIG)은 바꾸지 않는다. 정수가 아니거나 1 미만이면 `gs check` 오류. `runner`·`file`(그래서 `max_files`도. 지금 검사가 셋을 함께 요구한다)과 함께 쓰고, `runner`·`file` 없이 있으면 경고다(`max_files`의 같은 경고와 같은 방식). 기존 짝 검사는 바꾸지 않는다. 시험한다.
- gs가 worker를 띄울 때(첫·재개·수정·수리) 그 티켓의 touches와 누적 기록 파일 경로를 hook에 넘긴다. 기록 파일은 그 worker의 실행 디렉터리(`WorkerInput.rundir`, worktree 밖) 안에 둔다. worker 호출 하나(실행 디렉터리 하나)가 한 세션이다. touches와 상한은 환경 변수로 넘긴다(worker가 바꿀 수 없다. worktree의 config를 고쳐도 그 실행의 규칙은 그대로다). 기록 파일은 이 판정의 상태일 뿐이다. 이 판정은 비용 장치이고 보안 경계가 아니다: hook은 인터프리터 본문을 따라가지 않아 worker가 `python -c`로 기록을 고칠 수 있다(`hook.py` 머리말과 같은 한계). brief에 기록 경로를 적지 않는다.
- hook은 러너(`runner`)에 맞는 명령에서 `file`에 맞는 이름 중 touches(glob 허용, `tests/<이름>`으로 맞춘다) 밖인 것을 기록에 더한다. 서로 다른 이름의 누적 수가 `max_outside_files`를 넘게 되는 명령을 막는다. 막힌 명령의 이름은 기록에 더하지 않는다. 막는 메시지는 누적 수와 상한, 키 이름을 적고 "touches 밖 시험은 gs가 병합 트리에서 전체 검증으로 돈다"는 뜻을 담는다.
- touches 안 시험 파일은 몇 개를 돌려도 이 판정으로 막지 않는다(goldstack-v41 01 수정 worker는 touches 안 12개를 돌렸다). 시험한다.
- 기록 파일이 없거나 읽을 수 없으면(첫 명령, 깨진 JSON) 빈 기록으로 시작한다. touches나 경로가 넘어오지 않은 환경(옛 gs가 띄운 worker, 키 없음)에서는 이 판정을 건너뛴다.
- 이 레포 `.goldstack/config.toml` `[hook.worker_tests]`에 `max_outside_files = 10`과 근거 주석(goldstack-v42, spec §6 측정)을 넣는다.
- 시험(`tests/test_hook_session_tests.py`): (a) touches 밖 7개 + 7개를 두 명령으로 나눠 돌리면 두 번째가 막힌다(v41 01 모양). (b) touches 안 12개를 6+6 두 명령으로 나눠 돌리면 통과(한 명령 12개는 기존 `max_files` 10에 먼저 막힌다). (c) 같은 이름을 여러 번 돌리면 한 번으로 센다. (d) 키가 없으면 꺼짐. (e) 다른 세션(다른 실행 디렉터리)은 기록을 나누지 않는다. (a)는 누적 코드를 지우면 실패해야 한다. 시험은 실제 시간에 기대지 않는다.
- `hook.py` 모듈 docstring, `config.WorkerTestsConfig` docstring, `adapters.py` 모듈 docstring의 `GS_WORKER_TESTS` 설명을 새 동작에 맞게 고친다.

## 범위 밖
- codex worker(`gs jail`로 가두고 이 hook을 쓰지 않는다)의 누적 판정. 명령 분해 방식 변경.

## 참고
- spec §3 결정 2-4·2-5, §6 worker 세션 측정. 아이디어 `hook-session-test-file-count`. docs/guide.md `[hook.worker_tests]` 절
