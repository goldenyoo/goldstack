---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
tests/test_recheck_resolved.py의 6개 시험(RevertTest 2개, FinalCommitTest 3개, OldStateTest 1개)이 기본 severity high인 A 지적이 2차 재리뷰에서 unresolved로 판정된 뒤에도 병합 성공(self.run_ok())을 단언해, 티켓 03의 2차 재리뷰 미해결 high 병합 차단(spec 3-2) 때문에 실패하며 spec 전체 검증을 깨뜨린다.

위치: tests/test_recheck_resolved.py:108-125,139-152,293-306,330-340,354-374,631-653
근거: 코드 인용: `tests/test_recheck_resolved.py:66` `A = finding("FIX A: 값이 틀렸다")`(기본 `severity="high"`)를 쓰는 `test_second_fix_reverting_a_makes_it_unresolved`(108행), `test_reverted_finding_of_reviewer_without_second_targets`(139행), `test_commit_after_second_rereview_is_rechecked_at_new_head`(293행), `test_head_moving_again_keeps_unresolved`(330행), `test_abort_after_recheck_written_resumes_without_widening_second_fix`(354행), `test_old_state_resumes_second_rereview_and_rechecks`(631행)가 모두 2차 재리뷰 `A=unresolv …(일부 생략, 보고서에 전체)
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
