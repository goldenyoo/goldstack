---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
변경된 high 차단 정책과 충돌하는 기존 시험 9개가 그대로 남아 전체 검증을 실패시킨다. 실패·재시도를 기대하도록 바꾸거나, 병합 동작을 검증하는 시험의 지적 severity를 조정해야 한다.

위치: tests/test_review_target.py:513; tests/test_async_review.py:892; tests/test_recheck_resolved.py:87
근거: worker 관찰의 9개 메서드만 구현 worktree에서 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest -v로 실행한 결과 FAILED (failures=9), 25.158초였다. test_review_target의 두 시험은 재시도 때문에 재리뷰 호출이 각각 기대 3회 대비 4회, 기대 0회 대비 1회로 실패했다. 나머지 7개는 '남은 high: file_01 FIX A: 값이 틀렸다 (미해결)'로 실패·재시도한 뒤 종료 코드 1을 반환하지만 run_ok가 0과 병합을 요구한다. test_review_target.py:513은 기본 severity가 high인 새 지적을 추가하며, test_recheck_resolved.py:66의 A도 high인데 :87–90은 병합 성공을 단언한다. 실행 중 ps 권한 경고도 있었지만 위 assertion 실패는 high 차단에 따른 결과다. touche …(일부 생략, 보고서에 전체)
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v36/report.md
