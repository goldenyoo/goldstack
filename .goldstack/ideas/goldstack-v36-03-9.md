---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
tests/test_recheck_resolved.py의 6개 시험이 2차 재리뷰에서 기본 severity가 high인 지적 A가 unresolved로 판정되는데도 병합 성공(code == 0)을 단언해 spec 3-2 적용 후 실패한다.

위치: tests/test_recheck_resolved.py:21,107,139,293,330,354,642
근거: 코드 인용: `tests/test_recheck_resolved.py:21` `A = finding("FIX A: 값이 틀렸다")`(`tests/test_second_review.py:20` 기본 `severity="high"`), `tests/test_recheck_resolved.py:111,144,297,335,368,648` `self.run_ok()`(`self.assertEqual(code, 0, out + err)`). 어긴 명세 문장: `spec.md` §1 완료 조건("01–06이 병합되고 전체 검증이 통과한다"), §3 결정 3-2("1-6에 더해 2차 재리뷰가 `unresolved`로 판정한 기존 high도 센다"), §5 표 티켓 03 `verify: 전체`. 실행 명령과 결과: `PYTHONPATH=tests .venv/bin/python -m unittest test_recheck_resolved.RevertTest.test_second_fix_reverti …(일부 생략, 보고서에 전체)
판단: The six tests were reproduced failing because they assert that an unresolved high still merges, which spec 3-2 now forbids, so they break the full verification the ticket requires. Fixing them means editing tests/test_recheck_resolved.py, which is outside the fixable files.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: high
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
