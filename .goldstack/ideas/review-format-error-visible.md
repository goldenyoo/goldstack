---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v23"
status: "taken"
issues: []
feature: "goldstack-v25"
---
형식이 실패한 리뷰가 측정표에 `passed`·지적 0으로 찍히고, 보고서에 답 원문 경로가 없다.

- v23 report.md "리뷰 호출별 시간" 표에서 agy 행이 passed(516초)다. 반복: goldstack-v7.

고칠 곳: `src/gs/metrics.py`의 리뷰 호출 기록은 파싱 결과까지 반영해 `format-error`로 남긴다. report.md에는 `review.txt` 경로와 앞부분을 붙인다. 관련: [[review-json-invalid-escape]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
