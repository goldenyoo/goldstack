---
id: "01"
title: "grep으로 고른 시험 글로브를 러너로 넘기는 명령을 hook이 막는다"
blocked_by: []
touches: [".goldstack/config.toml", "tests/test_hook_worker_tests.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
worker가 `tests/test_*.py` 글로브로 고른 시험 묶음을 러너에 넘겨 hook의 시험 파일 수 상한을 우회하지 못하게, 이 레포 config의 deny에 그 모양을 더한다.

## 완료 조건
- `.goldstack/config.toml` `[hook.worker_tests] deny`에 spec §4 정규식이 한 줄 더해지고, 위 주석에 막는 모양과 근거(goldstack-v39 03)를 한 줄로 적는다. 다른 deny 줄과 `runner`·`file`·`max_files`는 그대로다.
- `tests/test_hook_worker_tests.py`가 이 레포 config 규칙으로 판정하는 기존 표 방식(V25_03 등)대로 아래를 단언한다. 새 deny 줄을 지우면 "막음" 단언이 실패한다.
  - 막음: spec §4 "막을 명령" 네 줄(goldstack-v32 01, v35 04, v36 03, v39 03 원문).
  - 통과: spec §4 "통과할 명령" 네 줄(글자 목록 루프, 조회용 grep 단독, 파일 하나 실행, `ls tests | grep -E '^test_(hook|config)'`).
- hook 코드(`src/gs/hook.py`)는 고치지 않는다.

## 범위 밖
- `-p $변수` 모양 차단(결정 2-1: 글자 목록 루프 오차단)
- `-m` 없이 직접 부르는 `pytest`(이 레포는 unittest만 쓴다. `\bpytest`를 넣으면 `grep -n pytest tests/test_*.py` 같은 조회가 막힌다. §7 교차 검토 6)
- brief 문장(02)

## 참고
- spec §3 결정 2-1, §4 hook 정규식, §6 실측
