---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
새 high 실패 처리에 맞춰야 할 기존 시험 9개가 그대로 남아 spec의 전체 검증을 실패시킵니다. test_recheck_resolved.py, test_async_review.py, test_review_target.py의 해당 fixture나 단언을 함께 갱신해야 합니다.

위치: tests/test_recheck_resolved.py:66
근거: spec 완료 조건은 '전체 검증이 통과한다'입니다. 구현 worktree에서 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest -v 명령에 관찰 1–4의 9개 테스트를 개별 지정한 결과 'Ran 9 tests in 24.348s / FAILED (failures=9)'였습니다. test_recheck_resolved.py는 기본 high인 A를 사용하면서 run_ok()에서 종료 코드 0과 병합을 단언합니다. test_review_target.py:513도 기본 high를 추가하고 재시도 없는 호출 횟수를 단언합니다. 실제 실패는 '남은 high' 처리와 추가 재시도 때문에 발생했습니다. 대표 4개 시험에서 해당 fixture의 심각도만 메모리상 medium으로 바꾸자 모두 통과해, ps 권한 경고가 실패 원인이 아님도 확인했습니다.
판단: The reviewer reproduced it: 9 existing tests fail because their default-high fixtures now hit the new 'remaining high' failure, and the spec requires full verification to pass. The tests to update (test_recheck_resolved.py, test_async_review.py, test_review_target.py) are outside the fixable files.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: medium
보고서: .goldstack/work/goldstack-v36/report.md
