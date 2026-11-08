---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v23"
status: "taken"
issues: []
feature: "goldstack-v25"
---
JSON이 허용하지 않는 이스케이프(`\x5d`) 하나 때문에 agy 리뷰 전체가 버려진다.

- v23 01: `run/01/1/review-agy/review.txt`(3825B)는 지적이 담긴 답인데, `review.extract_json`이 `답에서 JSON 객체를 찾지 못했다`로 버렸다. 이 실패는 2026-11-08 오케스트레이터 세션이 직접 재현했다. 고친 뒤 지적 2건이 살아나는지는 확인하지 않았다.
- `src/gs/review.py`의 `_repair_escapes`는 `\'`만 고친다(v9 수정). 반복: goldstack-v9에서도 같은 agy 실패가 있었다.

고칠 곳: `extract_json`. 허용되지 않는 `\X`를 고쳐 다시 읽게 하고, 이 답을 시험 표본으로 고정한다. 관련: [[review-format-error-visible]], [[hook-missed-agy-findings]]
