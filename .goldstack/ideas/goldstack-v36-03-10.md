---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
tests/test_async_review.py의 test_commit_while_waiting_is_rechecked_at_the_new_head가 2차 재리뷰 대조에서 high 지적 A가 unresolved로 판정되는데도 병합 성공(code == 0)을 단언해 실패한다.

위치: tests/test_async_review.py:891-899
근거: 코드 인용: `tests/test_async_review.py:891-893` `def test_commit_while_waiting_is_rechecked_at_the_new_head(self): out = self.commit_while_waiting("rm fixed_A")` → `887행` `return self.run_ok()`(`A`는 `test_recheck_resolved.A`, `severity="high"`). 어긴 명세 문장: `spec.md` §1 완료 조건("01–06이 병합되고 전체 검증이 통과한다"), §3 결정 3-2("1-6에 더해 2차 재리뷰가 `unresolved`로 판정한 기존 high도 센다"), §5 표 티켓 03 `verify: 전체`. 실행 명령과 결과: `PYTHONPATH=tests .venv/bin/python -m unittest test_async_review.SecondRereviewWaitTest.test_commit_while …(일부 생략, 보고서에 전체)
판단: The failure was reproduced: the test asserts a merge even though the 2nd re-review judged high finding A unresolved, which breaks full verification. The fix is in tests/test_async_review.py, which is outside the fixable files.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: high
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
