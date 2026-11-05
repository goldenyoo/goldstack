---
date: "2026-11-05"
severity: "low"
source: "goldstack-v9 06 agy 리뷰(Claude가 재현)"
status: "taken"
feature: "goldstack-v15"
---
앞 티켓이 병합되면 `_review_tick`이 바로 돌아가, 끝나 있던 다른 티켓의 리뷰 결과를 거두기 전에 새 티켓이 빈 worker 자리를 먼저 얻는다.

**근거(2026-11-05 재현)**: 11이 병합될 때 12의 리뷰가 끝나 있으면 14가 먼저 시작하고 12는 `fix_wait`로 밀린다. `Reviews.fix_waiting`의 "빈 자리는 수정 worker가 먼저 얻는다"와 어긋난다. 순서가 밀릴 뿐 결과는 틀리지 않는다.

**제안(S)**: 병합 뒤 돌아가기 전에 끝난 호출을 모두 거두거나, `fix_waiting`이 끝난 호출도 함께 본다.
