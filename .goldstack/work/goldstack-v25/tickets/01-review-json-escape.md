---
id: "01"
title: "허용되지 않는 JSON 이스케이프를 고쳐 읽고, 형식 오류 리뷰를 측정·보고서에 드러낸다"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/metrics.py", "src/gs/report.py", "tests/test_review.py", "tests/test_metrics.py", "tests/data/*"]
tier: medium
model: claude
reviewer: codex
---
## 목표
리뷰 답 속 이스케이프 하나 때문에 지적이 담긴 리뷰 전체를 버리지 않게 하고, 끝내 못 읽은 리뷰가 `passed`·지적 0으로 보이지 않게 한다.

## 완료 조건
- `extract_json`이 그대로 읽히는 후보가 없을 때, JSON이 허용하지 않는 `\X`(X가 `"\/bfnrtu`가 아닌 것)의 역슬래시를 두 번 써서 글자를 보존한 뒤 다시 읽는다. `\'` 처리는 지금대로다. 키 글자가 바뀌는 고치기는 하지 않는다(예: `"statu\s"`는 `status` 키로 읽히지 않는다).
- v23 `run/01/1/review-agy/review.txt` 원문을 `tests/data/`에 표본으로 두고, `parse_findings`가 이 답에서 지적 2건을 읽는 시험이 있다. 고치기를 지우면 이 시험이 실패한다.
- 끝내 파싱하지 못한 리뷰 호출은 측정 기록 `result`가 `format-error`다. 고쳐서 읽은 호출은 `passed`다. 둘 다 시험한다.
- 보고서의 리뷰 호출 표나 그 아래에 형식 오류 호출의 `review.txt` 경로와 바이트 수가 보인다. 답 원문은 옮기지 않는다.

## 범위 밖
- 답 원문을 보고서에 옮기기(믿을 수 없는 글)
- hook 파서가 놓친 결함(아이디어 `hook-missed-agy-findings`)

## 참고
- spec §3 1-4
- 아이디어 `review-json-invalid-escape`, `review-format-error-visible`
