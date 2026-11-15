---
id: "01"
title: "StaleTest와 stop_stale이 세션 리더 행만 그룹으로 받는다"
blocked_by: []
touches: ["src/gs/verify.py", "tests/test_verify.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
`test_verify.StaleTest`가 병렬 전체 검증에서 흔들리지 않게 한다. 시험의 `left_behind`가 아직 `setsid` 전인 bash의 `ps` 행(명령줄은 표지, 그룹은 부모 그룹)을 집어 부모의 그룹을 검증 그룹으로 잘못 고른다(spec §6). 같은 틈이 `verify._marked_groups`에도 있다.

## 완료 조건
- `tests/test_verify.py`의 `StaleTest.rows()`와 `left_behind`는 `ps -A -ww -o pid=,pgid=,command=`로 읽고, 표지가 붙은 행 중 `pid == pgid`인 행(세션 리더)만 그룹으로 받는다. 맞는 행이 없으면 지금처럼 다음 반복에서 다시 본다. `test_mark_is_the_last_word_and_differs_per_verify`도 같은 행 기준으로 단언한다.
- `src/gs/verify.py`의 `_ps`가 pid도 돌려주고(그것을 쓰는 `_group_alive`도 맞춘다) `_marked_groups`는 `pid == pgid`인 행만 그룹으로 모은다. `_ps`가 실패하면 예외인 것은 그대로다. 이 필터를 지우면 실패하는 시험을 하나 둔다: `_ps`를 바꿔 "표지가 붙었지만 pid ≠ pgid"인 행을 주면 `stop_stale`이 그 그룹에 신호를 보내지 않는다(`test_rows_that_are_not_stale_verifies_are_left_alone`의 행 목록에 더해도 된다).
- 측정: 레포 루트에서 아래 명령을 6라운드 돌려 실패 0/36이다. 고치기 전 기준(spec §6) 10/36. 명령과 라운드별 결과를 마지막 메시지에 적는다. 리뷰어 sandbox가 `ps`를 막아 다시 재지 못하면 그 사실을 리뷰에 적는다.
  `for i in 1 2 3 4 5 6; do .venv/bin/python -m unittest discover -s tests -p test_verify.py -k StaleTest > /tmp/stale_$i.log 2>&1 & done; wait; grep -L '^OK' /tmp/stale_*.log`
  (출력이 없으면 6벌 모두 통과)
- `tests/test_verify.py`에서 `verify._ps`를 바꾸는 시험(예: `test_rows_that_are_not_stale_verifies_are_left_alone`, `test_ps_failing_while_ending_warns_instead_of_raising`)은 새 행 형식에 맞추기만 하고 단언 뜻은 바꾸지 않는다. `tests/test_verify_repair.py`(`gs.verify._ps`를 `OSError`로 바꾸는 시험)는 고치지 않고 통과한다.

## 범위 밖
- 같은 실행의 다른 간섭 모양(가짜 레포 `wt/integration` 소실): 아이디어 `wt-integration-vanish-parallel`.
- 실제 시간에 기대는 다른 시험: 범위 밖 `tests-no-wall-clock`.

## 참고
- spec §3 결정 1-10, §6 `StaleTest` 원인.
- `src/gs/verify.py` 머리말의 표지(mark) 설명. 동작을 바꾸면 `_marked_groups` docstring도 고친다.
