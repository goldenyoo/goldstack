---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 04"
status: "open"
feature: ""
---
`_catch_up`과 `_catch_up_reviewed`가 수정·수리 재리뷰(`_rereview`, `_repair_review`)의 `a.base` 기준을 흐려, catch-up 도중이나 검증 중 늦은 커밋이 생기면 재리뷰 diff에 다른 티켓 변경이 섞이거나 앞서 한 수정·수리 커밋이 diff에서 빠진다.

위치: src/gs/go.py:1527-1535, src/gs/go.py:1604-1614
근거: 티켓 완료 조건은 "`_catch_up`이 만든 커밋은 리뷰 대상을 흐리지 않는다"이고 `src/gs/go.py:1607`은 "기준(a.base)도 옮긴다: 뒤에 늦은 커밋을 재리뷰하면 그 diff에 다른 티켓의 변경이 들지 않는다", `src/gs/go.py:2210`은 "병합 전 대조로 다시 불려도 같은 지적을 본다(a.base..head이므로 수정 뒤에 생긴 커밋도 diff에 든다)"고 명시한다. 그러나 `_rereview`(`src/gs/go.py:2219, 2317`)와 `_repair_review`(`src/gs/go.py:2132, 2174`)는 `review.rereview`·`review.repair_review`에서 2점 diff(`git diff f"{base}..{head}"`)를 쓴다. (1) `_catch_up_reviewed`(`src/gs/go.py:1609`)가 `a.target = a.base = head`로 `a.base`를 catch-up 병합 커 …(일부 생략, 보고서에 전체)
판단: `a.base`를 옮기거나 그대로 두는 경우 모두 2점 diff가 부정확해지는 것은 코드로 확인했지만, 병합 SHA는 맞고 영향은 수정·수리 재리뷰 diff의 좁은 경합에 그치며, 고치려면 `_end_fix`와 커밋 수 계산도 쓰는 `a.base`의 기준 설계를 바꿔야 해 더 위험하다.
보고서: .goldstack/work/goldstack-v15/report.md
