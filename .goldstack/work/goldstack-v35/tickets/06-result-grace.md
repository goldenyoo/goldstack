---
id: "06"
title: "성공 result 뒤 끝나지 않는 worker를 유예 뒤 정리한다"
blocked_by: ["04"]
touches: ["src/gs/go.py", "src/gs/worker.py", "src/gs/streamfmt.py", "src/gs/config.py", "tests/test_result_grace.py", "tests/test_config.py"]
closes: [65]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker가 성공 결과를 낸 뒤 남은 자식 프로세스 때문에 끝나지 않으면, `idle_minutes`(기본 20분) 시간 초과로 실패·재시도하지 않고 짧은 유예 뒤 정리하고 리뷰로 넘긴다(spec 3-3, issue #65).

## 완료 조건
- config `[timeouts] result_grace_seconds`(정수, 기본 60, 0이면 끔). `DEFAULT_CONFIG`·`TimeoutsConfig`·값 검사(음수·정수 아님은 다른 timeouts 키와 같은 오류)에 들어간다.
- `streamfmt`에 worker 로그에서 성공 끝 이벤트를 찾는 함수: claude는 `type: result`·`is_error: false`. 다른 계열은 `streamfmt`가 이미 성공 끝으로 알아보는 이벤트가 있을 때만, 없으면 None(지금 동작).
- `go._wait_any`: worker가 아직 돌고 있고(`poll()`이 None) 로그에 성공 끝 이벤트가 있으며 그 이벤트를 처음 본 뒤 `result_grace_seconds`가 지났으면, 그 worker의 남은 프로세스 목록(명령 줄)을 실행 디렉터리의 `leftover-procs.txt`에 쓰고 `Proc.stop`으로 정리한 뒤 종료 코드 0으로 끝난 것처럼 다음 단계(어댑터 판정 → 리뷰)로 넘긴다. 사건 줄 `result 뒤 <초>초 지나도 끝나지 않아 정리: 남은 프로세스 <n>개`를 남긴다.
- 성공 끝 이벤트가 없거나 `is_error: true`면 지금처럼 `idle_minutes` 시간 초과만 본다. 유예 중 로그가 다시 자라도 유예 시계는 처음 본 때부터다.
- 이 정리는 실행기(`SubprocessRunner`, `HerdrRunner`) 모두에서 같다. 정리한 worker의 소요 시간은 정리한 때까지다.
- `tests/test_result_grace.py`(`support`를 import한다, 실제 대기는 1초 안): 가짜 worker가 성공 `result`를 쓰고 자식 `sleep`을 남긴 채 끝나지 않으면 유예(시험에서는 짧게) 뒤 리뷰로 넘어가고 `leftover-procs.txt`에 그 자식이 있다. `is_error: true`면 넘기지 않는다. `result_grace_seconds = 0`이면 지금 동작. `tests/test_config.py`에 기본값·값 오류. 첫 시험은 고치기 전 코드에서 실패한다.
- `go.py` 머리말·`_wait_any` docstring에 이 경로를 적는다.

## 범위 밖
- worker가 백그라운드 작업을 띄우지 못하게 막기
- 리뷰·검증 프로세스의 같은 문제
- 문서는 08

## 참고
- spec §3 3-3, §6 #65 줄
- issue #65
