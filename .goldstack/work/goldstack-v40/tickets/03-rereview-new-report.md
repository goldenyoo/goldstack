---
id: "03"
title: "재리뷰가 앞 재리뷰의 새 report 지적도 판정한다"
blocked_by: ["02"]
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/report.py", "tests/test_rereview_report_findings.py", "tests/test_recheck_resolved.py", "tests/test_rereview.py", "tests/test_final_high.py", "tests/test_finding_status.py", "tests/test_second_reviewer_rereview.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
1차 재리뷰가 새로 낸 report(보고만) 지적이 판정 없이 보고서 "남은 위험"에 남지 않게, 2차 재리뷰가 그 지적도 판정한다. 병합 판단·수정 worker·리뷰어 호출 수는 바꾸지 않는다.

## 완료 조건
- 대상: 2차 재리뷰가 판정할 지적에 `found_round == 1`이고 action이 report인 지적이 더해진다. 1차 재리뷰 대상, 첫 리뷰(`found_round` 0)의 report 지적, 수리 재리뷰 대상은 바뀌지 않는다.
- 호출 수: report 지적만 가진 리뷰 기록 때문에 리뷰어 자리(호출)를 새로 만들지 않는다. 다른 이유로 부르는 자리에 함께 싣는다. `[review] second_reviewer_rereview = "first"`에서 두 번째 리뷰어 기록의 report 지적은 첫 리뷰어 자리에 빌려 판정하고(`go._rereview_slots`·`_lent_ids`) 판정이 원래 기록의 지적에 적힌다. `"all"`에서 report 지적만 가진 두 번째 리뷰어를 새로 부르지 않는다. 2차 재리뷰가 열리는 조건(2차 수정 worker가 돈 경우)은 그대로다.
- 프롬프트: 2차 재리뷰 프롬프트가 이 지적을 "고치라고 준 적 없는 보고만 지적. 이번 diff로 해소됐는지만 판정"으로 따로 표시한다(`is_recheck` 지적처럼).
- 병합 판단: 이 report 지적이 unresolved로 판정돼도 병합을 막지 않는다. `review._unresolved_high`·`final_highs`가 action이 report인 지적을 세지 않는다(지금처럼 판정받지 않은 report high가 막지 않는 것과 같다). fix 대상(`fix_targets`)이 되지 않고 새 수정 worker를 띄우지 않는다.
- 보고서: resolved로 판정된 report 지적은 `report.finding_status`가 "보고만"이 아니라 재리뷰가 해소를 확인했다는 상태로 보이고, `review.remaining`·`report.remaining_line`의 남은 지적·남은 high 집계와 보고서 "남은 위험"에서 빠진다. unresolved면 지금처럼 "보고만"으로 남는다.
- 재개: 2차 재리뷰 도중 멈췄다 이어도 같은 지적을 대상으로 고른다(state에 이미 있는 필드만으로 가린다). 옛 state(이 동작 전 기록)를 그대로 읽는다.
- 시험(`tests/test_rereview_report_findings.py` 등): 가짜 리뷰어로 (a) 1차 재리뷰의 새 report 지적이 2차 대상에 들고 프롬프트에 구분 표시가 있다, (b) resolved 판정 뒤 보고서 남은 위험에서 빠진다, (c) unresolved high report 지적이 `final_highs`에 들지 않는다, (d) `first` 모드에서 두 번째 리뷰어 기록의 report 지적이 첫 리뷰어 호출로 판정되고 리뷰어 호출 수가 늘지 않는다. 대상에 넣는 줄을 되돌리면 (a)·(b)가 실패한다.
- 바뀐 규칙을 설명하는 docstring(`rereview_targets`, `_unresolved_high`, `finding_status`, `go._to_rereview`, review.py 머리말)을 고친다.

## 범위 밖
- 첫 리뷰 report 지적 재판정(`rereview-first-review-report`), 마지막 회차가 새로 낸 report 지적(판정할 다음 회차가 없다)

## 참고
- spec §3 결정 2-4, §6, §7 교차 검토 1·2·5. goldstack-v39 04 F2(아이디어 `goldstack-v39-04-2`)가 이 경우다
