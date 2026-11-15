---
id: "03"
title: "brief: 백그라운드 출력은 자기 파일 하나만 읽는다 · replay brief touches 시험"
blocked_by: []
touches: ["src/gs/worker.py", "tests/test_brief_rules.py", "tests/test_fix_brief.py", "tests/test_replay_run.py", "src/gs/replay.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
worker가 백그라운드 작업 출력을 글로브로 읽다가 지금 도는 명령 자신의 출력까지 읽어 출력이 불어나는 일을 brief 규칙으로 막는다. replay가 brief에 티켓 touches를 넘기는지 실제 replay 경로로 시험한다.

## 완료 조건
- `src/gs/worker.py`에 새 규칙 상수를 두고 `write_brief`가 모든 brief(첫 worker, 재개, 수정, 수리)에 싣는다. 내용: 백그라운드 작업의 출력은 그 작업의 출력 파일 하나를 경로로 읽는다. 출력 디렉터리를 글로브로 읽지 않는다(예: `tasks/*.output`은 지금 도는 명령의 출력까지 읽어 끝없이 커진다). 계열마다 나누지 않는다. `write_brief` docstring의 규칙 목록에도 더한다.
- `tests/test_brief_rules.py`가 첫 worker brief와 수정·수리 brief에 그 상수가 있음을 단언한다. 상수를 brief에서 빼면 실패한다.
- `tests/test_replay_run.py`의 replay 실행 시험이 replay가 쓴 `brief.md`에 티켓 touches 줄(`worker.TOUCHES_LABEL`과 `src/a.py`)이 있음을 단언한다. `src/gs/replay.py`에서 `write_brief`에 `touches`를 넘기는 인자를 잠깐 빼면 이 단언이 실패하는 것을 보고(커밋하지 않는다), 본 실패를 마지막 메시지에 적는다. `src/gs/replay.py`는 이 변이 확인 때문에만 touches에 있다. 커밋에 그 파일의 변경이 없어야 한다.

## 범위 밖
- hook이 `tasks/*.output` 글로브 읽기를 막는 것(`.goldstack/out-of-scope/hook-task-output-glob.md`)

## 참고
- spec §3 결정 1-5·2-4, 아이디어 `worker-glob-own-task-output`, `goldstack-v36-04-1`
- `tests/test_replay_run.py`는 sandbox `ps` 차단 목록에 있다(profile). claude worker로 돈다
