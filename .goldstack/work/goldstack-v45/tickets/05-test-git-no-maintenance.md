---
id: "05"
title: "시험 공용 git 환경이 git maintenance를 띄우지 않게 한다"
blocked_by: []
touches: ["tests/support.py", "tests/test_jail.py", "tests/test_support_git.py", "tests/test_environment.py", "tests/test_sandbox_launch.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
git 2.54의 `git push`가 로컬 bare 양쪽에서 `git maintenance run --auto --detach`를 띄워 시험이 기다리지 않는 프로세스가 임시 레포를 만진다. 공용 시험 환경에서 끈다. goldstack-v44 03 검증의 `git clone` 객체 파일 소실과 관련 있을 수 있으나 원인은 확인하지 못했다(spec §6). 이 티켓은 원인 확정이 아니라 위생 수리다.

## 완료 조건
- `tests/support.py`의 공용 git 환경(GoTest의 환경과 `isolate_git_env`를 쓰는 시험)에서 git이 `maintenance.auto=false`로 돈다. `tests/test_jail.py`의 `QUIET_GIT`처럼 시험마다 따로 두지 않고 공용 환경 한 곳에서 정한다(`test_jail`이 공용 값을 쓰게 바꿔도 된다).
- 시험(`tests/test_support_git.py`): 공용 환경을 쓰는 임시 레포에서 `git config --get maintenance.auto`가 `false`이고, `GIT_TRACE`를 켠 로컬 bare `git push`의 trace에 `maintenance run`이 없다. 설정을 지우면 시험이 실패한다.
- 공용 환경이 지금 지우는 `GIT_CONFIG_COUNT`·`GIT_CONFIG_KEY_*`(`isolate_git_env`)와 부딪히지 않는다. `tests/test_environment.py`는 격리 뒤 그 변수가 없다고, `tests/test_sandbox_launch.py`는 worker 환경의 `GIT_CONFIG_KEY_0`가 push 차단이라고 단언한다. 그 단언이 지키는 뜻(사용자 git 설정이 새지 않는다, worker push 차단)은 그대로 두고, 방식 때문에 단언 문구만 바꿔야 하면 바꾼다.

## 범위 밖
- 제품 코드(`src/gs`)의 git 호출.
- 임시 폴더 통째 소실(goldstack-v42)의 원인 조사. 아이디어 `wt-integration-vanish-parallel`은 열어 둔다.

## 참고
- spec §3 결정 1-2, §6.
