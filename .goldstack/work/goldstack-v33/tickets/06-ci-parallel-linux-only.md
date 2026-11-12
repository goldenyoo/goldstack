---
id: "06"
title: "CI를 병렬로 돌리고 linux-only 검사를 병합 전에 기다린다"
blocked_by: ["05"]
touches: [".github/workflows/tests.yml", "tests/test_jail.py", "tests/test_sandbox_launch.py", "tests/support.py", ".goldstack/config.toml", "tests/test_ci_workflow.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
CI 전체 시험을 파일별 병렬로 줄이고, 리눅스에서만 실제로 도는 Landlock 시험을 짧은 `linux-only` job으로 떼어 이 레포의 병합 전 관문으로 삼는다(spec 1-3, 1-4, 2-3).

## 완료 조건
- `.github/workflows/tests.yml`에 job 둘:
  - `linux-only`: `name: linux-only`를 명시한다(gs가 읽는 `gh pr checks`의 이름은 job id가 아니라 job `name`이다). `tests/test_jail.py`, `tests/test_sandbox_launch.py`만 돈다. 환경 변수 `GS_REQUIRE_LANDLOCK=1`.
  - `tests`: 전체 시험을 파일별 병렬로(`ls tests | grep '^test_' | xargs -P "$(nproc)" -n 1 .venv/bin/python -m unittest discover -s tests -p`). `uv run`을 xargs로 띄우지 않고 앞에서 `uv sync --locked`. 파일 하나라도 실패하면 job이 실패한다.
  - 두 job 모두 지금의 git identity 단계를 가진다. action 버전은 지금 것을 쓴다.
- `GS_REQUIRE_LANDLOCK=1`이면 두 시험 파일의 Landlock 시험이 skip 대신 실패한다(메시지에 `GS_REQUIRE_LANDLOCK`). 변수가 없으면 지금처럼 skip이다. 판정은 두 파일이 함께 쓰는 한 곳(`tests/support.py` 같은 곳)에 둔다.
- 이 레포 `.goldstack/config.toml` `[git]`에 `wait_checks = true`, `checks = ["linux-only"]`. `gs check`가 이 config에 경고를 내지 않는다.
- `tests/test_ci_workflow.py`: workflow 파일에 두 job 이름이 있고, `linux-only`가 두 시험 파일과 `GS_REQUIRE_LANDLOCK=1`을 쓰며, `tests` job이 `xargs -P`로 돈다(문자열 단언). config의 `checks` 각각이 workflow 어느 job의 `name:` 값과 같다(job id가 아니라). `GS_REQUIRE_LANDLOCK=1`일 때 Landlock을 못 쓰면 실패하는 판정 함수의 단위 시험(맥에서도 돈다).
- 마지막 메시지에 "리눅스에서 병렬 실행·`linux-only` job은 이 티켓 검증으로 확인되지 않는다(맥 검증)"를 적는다.

## 범위 밖
- 느린 시험 파일 쪼개기(범위 밖 `test-git-call-reduction`)
- `[git] checks` 기능 자체는 05
- 문서·profile은 08

## 참고
- spec §3 1-3, 1-4, 2-3, §6 CI·측정 줄
- `.goldstack/ideas/ci-test-speed.md`, `ci-wait-linux-only-tests.md`
