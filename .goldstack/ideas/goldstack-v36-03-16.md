---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
SecondRereviewWaitTest.test_commit_while_waiting_is_rechecked_at_the_new_head가 기본 severity high인 test_recheck_resolved.A를 늦은 커밋에서 되돌려 2차 재리뷰 unresolved로 만든 뒤 병합 성공(self.run_ok())을 단언해, 티켓 03의 2차 재리뷰 미해결 high 병합 차단(spec 3-2) 때문에 실패하며 spec 전체 검증을 깨뜨린다.

위치: tests/test_async_review.py:889-900
근거: 코드 인용: `tests/test_async_review.py:890-892` `self.findings("codex", test_recheck_resolved.A, test_recheck_resolved.B)` 후 `out = self.commit_while_waiting("rm fixed_A")`가 `self.run_ok()`(`tests/test_recheck_resolved.py:87-90`, `code == 0` 및 `merged == ["01"]`)를 호출하는데 `A`의 severity가 기본값 `high`다. 어긴 명세 문장: `spec.md` §1 완료 조건(`01–06이 병합되고 전체 검증이 통과한다`), §3 결정 3-2, §5 티켓 03 `verify: 전체`. 실행 명령과 결과: `.venv/bin/python -m unittest discover -s tests -p test_async_review.py -k test_commit_while_waiting_is …(일부 생략, 보고서에 전체)
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v36/report.md
