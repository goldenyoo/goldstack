---
id: "02"
title: "원인을 없앤 worker에서 hook의 `=` 단어 판정을 뺀다"
blocked_by: ["01"]
touches: ["src/gs/hook.py", "tests/test_hook.py", "tests/test_hook_equals_cases.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
놓침과 오차단을 반복한 `=` 단어 판정을 더 고치지 않고, 원인이 없어진 worker에서는 판정 자체를 하지 않는다.

## 완료 조건
- 01의 실측 표를 읽는다. claude·agy·codex 모두 통과했으면 `=` 단어 판정(`equals_word`와 그 판정만 쓰는 코드·`Ctx.zsh`)을 지운다. 하나라도 실패했으면 판정을 남기고, 환경에 `GS_NOEQUALS=1`이 있을 때만 건너뛴다. 어느 쪽을 했는지 `hook.py` 머리말에 적는다.
- 다른 판정(push, gh 쓰기, worktree 밖 쓰기, 비밀 파일, `pkill`, v26의 `[hook.worker_tests]`)의 결과는 바뀌지 않는다. `tests/test_hook.py`와 `tests/test_hook_worker_tests.py`의 그 밖 시험은 그대로 통과한다. `=` 판정 시험은 지우거나 `GS_NOEQUALS` 조건에 맞게 고친다.
- 시험 `tests/test_hook_equals_cases.py`: spec §6의 여섯 명령(놓침 2·오차단 4)이 `GS_NOEQUALS=1` worker에서 막히지 않는다. 판정을 남긴 경우에는 `GS_NOEQUALS`가 없을 때 `echo ===`가 지금처럼 막힌다.
- `hook.py`에서 `=` 판정만 쓰던 코드가 남지 않는다(지운 경우).

## 범위 밖
- 단어 단위 파서 재작성(`.goldstack/out-of-scope/hook-word-parser.md`)
- 사용자 문서(03)

## 참고
- spec §3 1-3·1-4·1-6, §6
- 아이디어 `hook-missed-agy-findings`, `goldstack-v23-01-2`
