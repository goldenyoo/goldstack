---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v36 리뷰 03"
status: "open"
feature: ""
---
apply_rereview와 apply_repair_review가 _add_found로 새 지적을 rec['findings'] 끝에 덧붙이기만 하고 final_highs가 found_round in (2, REPAIR_ROUND)인 모든 high를 세어, 병합 전 대조(-again)가 새 커밋(h2)을 다시 리뷰해 새 high가 사라져도(findings: []) 이전 커밋(h1)의 2차·수리 재리뷰 새 high가 그대로 남아 병합을 막는다.

위치: src/gs/review.py:1274,1280,1293-1296,1323-1336
근거: 코드 인용: `src/gs/review.py:1293-1296` `def _add_found(rec: dict, res: dict, nth) -> None:`는 `rec["findings"].append({**f, "id": next_id + i, "found_round": nth})`로 누적만 하고 같은 회차(`2` 또는 `REPAIR_ROUND`)의 앞선 head 지적을 교체하거나 최종 리뷰 head와 대조하지 않으며, `src/gs/review.py:1323-1325` `_new_final_high`는 `f.get("severity") == "high" and f.get("found_round") in (2, REPAIR_ROUND)`만 본다. 어긴 명세·계약: `spec.md` 결정 1-6("2차 재리뷰·수리 재리뷰에 새 high가 있으면 병합하지 않고 일반 티켓 실패") 및 `src/gs/go.py:2001,2141-2143` 병합 전 대조 규칙(새 head 대조가 성공하면 …(일부 생략, 보고서에 전체)
판단: The behaviour was reproduced only by calling the functions directly, not end to end. The existing code keeps appending findings, and nothing in the spec or ticket says whether the pre-merge re-review at the new head (h2) replaces the earlier head's (h1) new findings, so the expected behaviour can't be determined.
보고서: .goldstack/work/goldstack-v36/report.md
