---
id: "01"
title: "병합 전 대조가 다시 본 회차의 이전 head high는 대체됨"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/report.py", "tests/test_final_high.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
병합 전 대조 재리뷰가 새 head를 다시 봤을 때, 같은 회차(2차 재리뷰·수리 재리뷰)가 이전 head에서 낸 새 high가 병합을 막지 않게 한다(spec 결정 2-2, 아이디어 goldstack-v36-03-8). 빈 2차 수정 커밋의 미해결 high가 병합을 막는 경우를 직접 시험한다.

## 완료 조건
- 같은 리뷰 기록에서 같은 회차(2차 재리뷰 또는 수리 재리뷰)의 재리뷰가 다시 돌았고, 두 재리뷰 기록(`rec["rereviews"]`)의 `base`가 같으면(병합 전 대조 `_review_again`은 `a.base`를 그대로 둔다) 앞 재리뷰가 낸 새 지적에 `superseded` 표시(대체됨)가 붙고 `review.final_highs`가 그것을 세지 않는다. 지적은 기록에 남는다.
- `base`가 다르면(catch-up 뒤 `_catch_up_reviewed`가 `a.base`를 옮긴 경우: 뒤 diff에 앞 변경이 없다) 표시하지 않고 지금처럼 앞 high가 병합을 막는다.
- 보고서: `report.finding_status`가 `superseded` 지적에 `대체됨`을 돌려주고, `remaining_line`의 남은 high에서 뺀다.
- `tests/test_final_high.py`에 시험 셋: (1) 이전 head 2차 재리뷰의 새 high + 새 head 대조 재리뷰 `findings: []` → 병합된다, (2) 새 head 대조 재리뷰도 high를 내면 → 티켓 실패 `남은 high: …`, (3) 빈 2차 수정 커밋으로 기존 high가 2차 unresolved → 병합되지 않고 티켓 실패, (4) catch-up으로 base가 옮겨진 뒤의 재리뷰는 앞 high를 대체하지 않는다, (5) 대체된 high는 보고서 마무리 줄의 남은 high에 없다. (1)은 대체 표시 코드를 되돌리면 실패한다.
- 옛 state(`superseded` 키 없음)를 읽어도 오류 없이 지금처럼 판정한다.
- `review.py`·`go.py`의 `final_highs`를 설명하는 docstring을 새 동작에 맞춘다.

## 범위 밖
- 보고서의 defer 상태(02), 실패 요약 잘림(03)

## 참고
- spec §3 결정 2-2, `.goldstack/work/goldstack-v36/report.md` "03 재현된 미수리", 아이디어 `goldstack-v36-03-8`
