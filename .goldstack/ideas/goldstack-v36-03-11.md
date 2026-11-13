---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
tests/test_review_target.py의 test_commit_after_second_rereview_is_seen_even_when_all_resolved가 2차 재리뷰 대조의 새 지적을 기본 severity high로 내면서 재시도 없는 병합을 단언해 실패한다.

위치: tests/test_review_target.py:508-520
근거: 코드 인용: `tests/test_review_target.py:512-516` `self.answer("codex", 3, [(1, "resolved", "확인"), (2, "resolved", "확인")], [finding("늦은 커밋의 문제")])` 후 `code, out, err = self.go("--only", "01"); self.assertEqual(code, 0, out + err); self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2", "codex 3"])`. 어긴 명세 문장: `spec.md` §1 완료 조건("01–06이 병합되고 전체 검증이 통과한다"), §3 결정 1-6("2차 재리뷰·수리 재리뷰에 새 high가 있으면 병합하지 않고 일반 티켓 실패"), §5 표 티켓 03 `verify: 전체`. 실행 명령과 결과: `PYTHONPATH=tests .venv/bin/python -m u …(일부 생략, 보고서에 전체)
판단: The failure was reproduced: the test asserts a merge with no retry even though the pre-merge re-review raised a default-high finding, which goes against spec 1-6. The fix is in tests/test_review_target.py, which is outside the fixable files.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: high
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
