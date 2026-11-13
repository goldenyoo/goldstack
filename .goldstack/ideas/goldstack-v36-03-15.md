---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
PreMergeTest.test_commit_after_second_rereview_is_seen_even_when_all_resolved(2차 재리뷰 대조 호출이 기본 severity high 새 지적을 반환)와 test_empty_fix_commit_needs_no_second_look(빈 2차 수정 커밋으로 기본 severity high 지적이 2차 unresolved가 됨)가 티켓 03의 바뀐 동작(2차 재리뷰 새 high·미해결 high 시 병합 차단 및 재시도)에 맞춰 갱신되지 않아 실패하며, spec 전체 검증을 깨뜨린다.

위치: tests/test_review_target.py:508-521,605-617
근거: 코드 인용: `tests/test_review_target.py:513` `self.answer("codex", 3, [(1, "resolved", "늦은 커밋까지 확인")], [finding("FIX 늦은 커밋의 새 문제")])`와 `tests/test_review_target.py:606-608` `self.findings("codex", finding("FIX A: 값이 틀렸다"))` + `fixempty_1`·`fixempty_2`는 `test_second_review.finding`의 기본 `severity="high"`를 쓰면서 1회 시도로 병합됨을 전제한다. 어긴 명세 문장: `spec.md` §1 완료 조건(`01–06이 병합되고 전체 검증이 통과한다`), §3 결정 1-6·3-2, §5 티켓 03 `verify: 전체`(`ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover - …(일부 생략, 보고서에 전체)
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v36/report.md
