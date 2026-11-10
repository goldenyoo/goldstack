---
id: "02"
title: "검증이 실패하면 실패한 시험 파일을 따로 돌려 1회성인지 가리고, 그렇다면 전체를 한 번 더 돌린다"
blocked_by: ["01"]
touches: ["src/gs/verify.py", "src/gs/config.py", "src/gs/metrics.py", "src/gs/finish.py", "src/gs/go.py", "src/gs/replay.py", ".goldstack/config.toml", "tests/test_verify_rerun.py", "tests/test_setup.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
바뀐 코드와 무관한 시험 하나의 1회성 실패로 티켓 시도나 feature 병합이 날아가지 않게 한다. 실패한 시험 파일을 따로 돌려 보는 것은 판별에만 쓴다. 통과 판정은 언제나 전체 검증 명령이 한다(spec 3-1).

## 완료 조건
- config `[verify]`(모두 선택, 비면 꺼짐): `failed_file`(Python 정규식, 첫 그룹이 시험 파일 이름의 일부), `rerun`(셸 명령 틀, `{file}` 포함), `max_files`(정수, 기본 3). `failed_file`·`rerun` 중 하나만 있음, 정규식 컴파일 실패, 그룹 없음, `{file}` 없음, `max_files` < 1이면 `gs check`·`gs go`가 config 오류를 낸다. `DEFAULT_CONFIG`에는 넣지 않는다.
- `verify.run`이 이 설정과, 호출자가 주는 "트리가 그대로인가" 확인 함수를 받는다. 호출자(`finish.py` 검증들, `go.py` 티켓 검증, `replay.py`)는 실행 중인 config 값을 넘긴다. worktree의 config를 읽지 않는다.
- 동작(한 시도):
  1. 전체 명령이 실패했고(`Result.ok`가 아님, 시간 초과·끊김이 아님) 설정이 켜져 있으면, 그 실행의 출력만에서 `failed_file` 첫 그룹을 모아 중복을 뺀다.
  2. 매치가 없거나, `max_files`를 넘거나, 값이 `[A-Za-z0-9_.-]+`가 아니거나, 확인 함수가 트리 변경을 알리면 판별하지 않는다. 로그에 이유 한 줄을 남기고 지금처럼 실패로 간다.
  3. 아니면 파일마다 `rerun`의 `{file}`을 그 값으로 바꿔 같은 cwd·환경에서 돌린다. 모든 판별 실행이 합쳐서 `verify_minutes` 하나를 나눠 쓴다. 하나라도 `Result.ok`가 아니면 판별 실패로 보고 지금처럼 실패로 간다.
  4. 모두 통과하고 확인 함수가 트리 그대로라고 하면, 전체 명령을 한 번 더 돌린다. 그 결과가 이 시도의 결과다. 통과하면 로그에 `flaky: <label> <파일들> 따로 돌려 통과, 전체 다시 통과` 줄을 쓴다.
- `verify_retries`와 함께 쓰면 시도마다 위 판별을 먼저 한다. 전체를 한 번 더 돌리는 것은 `verify_retries`와 별개로 시도당 최대 1번이다.
- `metrics.sample`(또는 `validation`)이 판별 여부, 파일, 판별 결과를 남긴다. 키 이름은 docstring에 적는다.
- 이 레포 `.goldstack/config.toml`에 `[verify]`: `failed_file = '^(?:FAIL|ERROR): \S+ \((test_\w+)\.'`, `rerun = ".venv/bin/python -m unittest discover -s tests -p {file}.py"`, `max_files = 3`, 위에 주석 한 줄.
- 기존 시험의 `verify.run`·`validate` mock(`tests/test_setup.py` 등)이 새 인자에서 깨지지 않게 맞춘다.
- 시험 `tests/test_verify_rerun.py`(가짜 명령, 실제 시간에 기대지 않음):
  - 꺼짐 → 지금과 같음
  - 판별 통과 + 전체 다시 통과 → 통과와 flaky 줄
  - 판별 통과 + 전체 다시 실패 → 실패
  - 판별 실패 → 전체를 다시 돌리지 않고 실패
  - 매치 없음, `max_files` 초과, 허용 밖 문자 값(`$(…)`, 따옴표) → 판별 안 함
  - 시간 초과 → 판별 안 함. 판별 실행이 시간 초과(종료 0이어도) → 판별 실패
  - 앞 시도 출력의 매치는 세지 않음
  - 트리 변경 → 판별·전체 재실행 안 함
  - `&&` 사슬의 앞 명령이 실패해 뒤 명령이 안 돈 경우, 판별 통과 뒤 전체 재실행에서 뒤 명령까지 돌았음을 확인
  - config 오류 다섯 가지
  - 이 레포 정규식이 `FAIL: test_x (test_resume_report.ProtectedResumeTest.test_x)`에서 `test_resume_report`를 뽑고 `ERROR: test_x (unittest.loader._FailedTest.test_x)`는 뽑지 않음
  - 각 분기를 지우면 실패한다.
- `verify.py` 머리말, `config.py`·`metrics.py` docstring을 고친다.

## 범위 밖
- 보고서 Summary에 flaky 표시(03)
- 실패 시험이 이번 diff에 있으면 판별하지 않는 조건(spec 2-3에서 뺌)
- 사용자 문서(05)

## 참고
- spec §3 2-3, 3-1, §6 검증 재시도 사실, §7 교차 검토
- 아이디어 `integration-verify-flaky-retry`
