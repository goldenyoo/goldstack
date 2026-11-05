---
id: "01"
title: "시험에서 Apple git shim 우회"
blocked_by: []
touches: ["tests/support.py", "tests/test_environment.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
macOS의 `/usr/bin/git`은 실제 git을 찾아 넘기는 shim이라 프로세스 비용이 크다. 시험 fixture가 shim을 건너뛰게 해 좁은 시험·검증·CI를 한 곳으로 빠르게 한다.

## 완료 조건
- `tests/support.py`를 import하면, `git`이 Apple shim일 때 git 링크 하나만 든 임시 디렉터리가 `PATH` 맨 앞에 온다. CommandLineTools 디렉터리를 통째로 앞에 두지 않아 `python3`·`pip3`·`make`·`cc`를 가리지 않는다.
- `xcrun`이 없거나 실패하는 환경(리눅스 포함)에서는 아무것도 바꾸지 않는다.
- shim 판별과 링크 만들기를 시험한다. 가짜 `xcrun`으로 있는 경우와 없는 경우, 링크 디렉터리에 `git`만 있는 것을 본다.
- 전체 시험이 통과하고, 마지막 메시지에 `test_ticket_verify.py` 시간을 바꾸기 전후로 적는다(spec §6 측정 55.9초 → 38.0초와 견준다).

## 범위 밖
- worker·gs 자체가 쓰는 git(시험 밖)은 건드리지 않는다.
- 시험당 git 호출 줄이기: `out-of-scope/test-git-call-reduction.md`.

## 참고
- spec §6의 측정
- `.goldstack/ideas/e2e-time-reduction-2.md` 제안 1
- `support`를 import하지 않는 시험 파일은 혜택이 없어도 된다
