---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 04"
status: "taken"
feature: "goldstack-v19"
---
`_late_commit`으로 재리뷰로 돌아가는 도중 `gs go`가 중단되었다가 재개되면 `moved`와 `reviewed_again` 상태가 사라져, `_review_again` 대신 `_review_to_head`로 돌면서 재리뷰 상한(합쳐 한 번)을 넘어 3번째 리뷰를 호출하고 대조 기록도 남기지 않는다.

위치: src/gs/go.py:1420-1423, src/gs/go.py:1497, src/gs/go.py:1598-1601
근거: `src/gs/go.py:21-24`와 `src/gs/go.py:1587`은 "여기서도 다시 보는 것은 합쳐 한 번이다: 이미 더 봤으면 늦은 커밋을 뺀 SHA를 병합하고 브랜치는 남긴다"고 규정하고,티켓 완료 조건은 "재개와 옛 `state.json`을 읽는다"이다. 그러나 `_late_commit`(`src/gs/go.py:1599`)은 `_mark_resume(r, a, done=True)`만 저장하고 `reviewed_again`이나 `moved`를 남기지 않는다. 재개 시 `_resume` → `_finish`(`src/gs/go.py:1423`)가 `Reviewing(a)`(`moved=""`, `a.reviewed_again=False`)를 만들므로 `_review_stage`(`src/gs/go.py:1497`)가 `_review_again` 대신 `_review_to_head`를 탄다. 그 결과 `rec["fix"]`에 `다시 리뷰를 띄웠다` 기록이 남지 않고 `a. …(일부 생략, 보고서에 전체)
판단: `reviewed_again`을 표시에 남기지 않아 재개 뒤 리뷰가 한 번 더 돌 수 있는 것은 사실이지만, 중단과 또 다른 늦은 커밋이 겹칠 때만 생기고 리뷰 없는 코드가 병합되지는 않으며 티켓의 재개 조건을 어기지도 않는다.
보고서: .goldstack/work/goldstack-v15/report.md
