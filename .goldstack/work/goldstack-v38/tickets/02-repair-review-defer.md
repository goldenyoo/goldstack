---
id: "02"
title: "수리 재리뷰가 defer 지적을 판정하고 보고서가 해소를 반영"
blocked_by: ["01"]
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/report.py", "tests/test_repair_review_defer.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
수리로 해소된 defer 지적(재현됐지만 고칠 수 있는 파일 밖이라 고치지 않은 지적)이 보고서에서 "재현된 미수리"로 남아 남은 high를 부풀리지 않게 한다(spec 결정 2-1, 아이디어 report-repaired-findings-status).

## 완료 조건
- 수리 재리뷰 프롬프트(`review.repair_review_prompt`)에 그 리뷰어의 defer 지적이 id와 함께 실리고, 답 형식에 지적별 판정(resolved/unresolved와 근거)이 있다. defer 지적이 없으면 프롬프트는 지금 그대로다.
- 판정이 resolved이고 근거가 있으면 `report.finding_status`가 `수정됨(수리 재리뷰 확인)`을 돌려주고 `remaining_line`의 남은 high와 "재현된 미수리 결함" 절에서 빠진다. unresolved·판정 없음·근거 없음·재리뷰 실패는 지금처럼 `재현된 미수리`다.
- `tests/test_repair_review_defer.py`: 가짜 리뷰어로 수리 재리뷰를 돌려 (1) resolved → 보고서 마무리 줄의 남은 high에서 빠짐, (2) unresolved → 그대로 셈, (3) defer 없음 → 프롬프트에 defer 절 없음을 본다. (1)은 판정 반영 코드를 되돌리면 실패한다.
- 옛 state(판정 키 없음)도 오류 없이 지금처럼 센다. 관련 docstring(`report.py` 머리, `review.py` defer 설명)을 고친다.

## 범위 밖
- 병합 판정(`final_highs`)은 바꾸지 않는다(01). 2차 재리뷰에서 defer 판정은 하지 않는다.

## 참고
- spec §3 결정 2-1, `.goldstack/work/goldstack-v36/report.md` 마무리 줄
