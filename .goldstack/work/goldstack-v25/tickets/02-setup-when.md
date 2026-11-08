---
id: "02"
title: "병합 diff가 config `setup_when`에 걸리면 integration setup을 다시 돌린다"
blocked_by: []
touches: ["src/gs/config.py", "src/gs/go.py", "src/gs/setup.py", ".goldstack/config.toml", "tests/test_setup_when.py", "tests/test_config.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
버전·의존성을 바꾼 티켓이 병합된 뒤 integration 검증이 옛 환경에서 돌지 않게 한다.

## 완료 조건
- config `[worktree] setup_when`(glob 목록)을 읽는다. 기본은 빈 목록이고 그때 동작은 지금과 같다. `gs init`이 쓰는 기본 config는 바꾸지 않는다.
- 티켓 병합의 변경 파일이 glob 하나에라도 걸리면, 병합 커밋 뒤·티켓 검증 전에 integration worktree에서 `worktree.setup`을 다시 돌리고 setup.log를 시도 디렉터리에 남긴다. 걸리지 않으면 돌리지 않는다. 두 경우를 시험한다.
- 커밋되지 않은 병합 중에는 `setup.run`을 부르지 않는다(`_restore_tracked`가 병합한 추적 파일을 되돌린다). 다시 돈 setup 뒤에도 병합한 추적 파일의 내용이 그대로인지 시험한다.
- 검증 실패 등으로 그 병합을 integration에서 취소하면, 다음 검증 전에 setup을 다시 돌려 환경을 integration head에 맞춘다.
- 다시 돈 setup이 실패하면 그 티켓의 검증 실패로 처리하고 이유에 setup.log 경로를 담는다.
- 이 레포 `.goldstack/config.toml`에 `setup_when = ["uv.lock", "pyproject.toml"]`.
- 옛 state·config(값 없음)도 읽힌다.

## 범위 밖
- 이 레포 spec `verify` 앞의 `uv sync` 우회를 빼기
- 티켓 worktree의 setup 재실행

## 참고
- spec §3 1-2
- 아이디어 `integration-setup-after-merge`
