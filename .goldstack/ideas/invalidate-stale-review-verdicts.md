---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 Codex 리뷰(Claude가 코드 대조)"
status: "taken"
feature: "goldstack-v9"
---
2차 수정이 1차에서 고친 지적을 되돌려도 그 지적은 계속 `resolved`로 남는다.

**근거(코드 확인, 재현 안 함)**: `review.fix_targets`는 2차 대상으로 unresolved와 새 fix 지적만 고르고, `go._run_rereviews`도 그 대상의 리뷰어만 부른다. `tests/test_rereview.py`는 1차 resolved(`rereview_round` 1)가 2차 뒤에도 유지되는 것을 고정한다.

**시나리오**: 1차 수정으로 A를 고치고 B가 남는다. 2차 worker가 B를 고치면서 A의 수정을 덮어쓴다. A를 낸 리뷰어는 다시 불리지 않을 수 있고, 보고서는 A를 "수정됨"으로 센다. 마지막 검증이 A를 잡는 시험을 갖고 있지 않으면 그대로 병합된다.

**제안(M)**: 고칠 대상과 확인할 대상을 나눈다. 2차 수정은 남은 지적만 받고, 2차 재리뷰는 앞서 resolved인 지적도 최종 head에서 본다. 확인하지 못하면 unchecked로 둔다. 수정 횟수 상한 2회는 그대로다. 재리뷰 입력과 agy 호출이 늘어나는 비용이 있다. Codex는 high로 냈지만 2차 수정이 있는 티켓에서 되돌림까지 겹칠 때만 생겨 medium으로 낮췄다.
