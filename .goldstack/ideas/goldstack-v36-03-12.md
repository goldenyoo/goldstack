---
date: "2026-11-13"
severity: "high"
source: "goldstack-v36 리뷰 03"
status: "dropped"
feature: ""
---
tests/test_review_target.py의 test_empty_fix_commit_needs_no_second_look이 빈 2차 수정 커밋으로 기본 high 지적 A가 2차 unresolved로 판정되는데도 병합(code == 0, rereview.calls == [])을 단언해 실패한다.

위치: tests/test_review_target.py:605-617
근거: 코드 인용: `tests/test_review_target.py:605-611` `self.findings("codex", finding("FIX A: 값이 틀렸다")); (self.bin / "fixempty_1").touch(); (self.bin / "fixempty_2").touch(); code, out, err = self.go("--only", "01"); self.assertEqual(code, 0, out + err); self.assertEqual(self.lines("rereview.calls"), [])` 및 `src/gs/go.py:2730-2732` `review.mark_rereview(left, nth, review.UNRESOLVED, "", "수정 커밋의 diff가 비었다")`. 빈 커밋의 2차 `UNRESOLVED` high를 세는 것은 `--allow-empty` 2차 수정이 미해결 high 차단을 우회하지 못하게 하므로 `spec 3-2`에 부합 …(일부 생략, 보고서에 전체)
판단: The failure was reproduced: the test asserts a merge even though the empty 2nd fix commit leaves a default-high finding unresolved, which goes against spec 3-2. The fix is in tests/test_review_target.py, which is outside the fixable files.
재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: high
보고서: .goldstack/work/goldstack-v36/report.md

- 닫음(2026-11-13, goldstack-v38 grill 1-2): v36 수리 커밋이 fixture를 고쳐 해소됐다. 세 시험 파일 174개 통과.
