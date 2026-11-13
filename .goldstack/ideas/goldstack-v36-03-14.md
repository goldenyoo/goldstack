---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
이 티켓이 2차 재리뷰의 미해결·새 high 지적을 병합 차단(`go._fail`)으로 바꾸면서, 기본 severity가 `high`인 `test_second_review.finding` 픽스처로 2차 재리뷰 뒤 병합(`merged`, `code == 0`)을 단언하던 기존 시험 9개가 갱신되지 않아 실패하고 `spec.md`의 전체 검증(`verify`)이 깨진다.

위치: tests/test_recheck_resolved.py:108,139,293,330,354,631, tests/test_review_target.py:508,605, tests/test_async_review.py:889
근거: 코드 인용: `tests/test_recheck_resolved.py:66`(`A = finding("FIX A: 값이 틀렸다")`, 기본 severity `high`)을 쓰는 `RevertTest.test_second_fix_reverting_a_makes_it_unresolved`(`108행`), `RevertTest.test_reverted_finding_of_reviewer_without_second_targets`(`139행`), `FinalCommitTest.test_commit_after_second_rereview_is_rechecked_at_new_head`(`293행`), `FinalCommitTest.test_head_moving_again_keeps_unresolved`(`330행`), `FinalCommitTest.test_abort_after_recheck_written_resumes_without_widening_second_fix`(`354행`), `Ol …(일부 생략, 보고서에 전체)
판단: 리뷰어가 9개 시험을 실행해 모두 실패하는 것을 재현했고, 티켓이 요구한 새 동작에 맞춰 시험 기대를 바꾸는 것이 고칠 방향이다. 그러나 고칠 파일 tests/test_recheck_resolved.py, tests/test_review_target.py, tests/test_async_review.py는 고칠 수 있는 파일 밖에 있다.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: high
보고서: .goldstack/work/goldstack-v36/report.md
