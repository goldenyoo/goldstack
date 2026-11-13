---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
새 high 차단 동작과 충돌하는 기존 시험 9개가 남아 있어 spec의 전체 검증 통과 조건을 충족하지 못한다. test_recheck_resolved.py 6개, test_review_target.py 2개, test_async_review.py 1개의 기대나 fixture를 새 동작에 맞춰야 한다.

위치: tests/test_recheck_resolved.py:108
근거: 구현 worktree에서 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -로 해당 9개만 unittest.loadTestsFromNames에 전달해 실행한 결과 testsRun=9, failures=9, errors=0. 예를 들어 test_second_fix_reverting_a_makes_it_unresolved는 '실패: 남은 high: file_01 FIX A: 값이 틀렸다 (미해결)'로 종료 코드 1을 받지만 run_ok(89행)는 0을 요구한다. test_review_target.py:516·611도 high 차단 후 재시도로 늘어난 호출 수 때문에 실패한다. ps 제한은 경고이고, 실패 단언은 high 차단 결과와 기존 기대의 불일치다. 관찰 1에서 확인된 결함이다.
판단: 리뷰어가 9개 시험을 돌려 9개 모두 실패하는 것을 재현했고 티켓이 요구한 high 차단 동작과 맞지 않는 실제 결함이지만, 고쳐야 할 test_recheck_resolved.py·test_review_target.py·test_async_review.py가 모두 고칠 수 있는 파일 밖이다.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: medium
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
