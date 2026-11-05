---
id: "06"
title: "보고서에 리뷰 결과 대기를 더하고 Summary 제목 중복을 없앤다"
blocked_by: ["03"]
touches: ["src/gs/go.py", "src/gs/metrics.py", "src/gs/report.py", "tests/test_result_wait.py", "tests/test_summary_heading.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
검증이 코디네이터 루프를 막아 생긴 리뷰 쪽 대기를 보고서에서 볼 수 있게 한다. 다음 grill이 `async-verify`를 숫자로 판단하게 한다. 보고서 `## Summary` 제목이 두 번 나오지 않게 한다.

## 완료 조건
- 리뷰·판단 호출이 끝난 시각부터 `go._loop`가 그 결과를 받을 때까지의 대기가 metrics에 기록된다. worker의 `처리 대기(초)`와 같은 방식이다.
- `report.md`의 리뷰 쪽 표에 `결과 대기(초)` 열이 있다. 기록이 없는 옛 state는 `기록 없음`이다.
- 측정을 넣어도 검증과 리뷰의 실행 순서는 바뀌지 않는다. 검증을 루프 밖으로 빼지 않는다.
- 판단 모델 답이 `## Summary` 제목으로 시작해도 `report.md`와 PR 본문에 제목이 한 번만 나온다. 보고서 요약 지시문도 제목을 쓰지 말라고 적는다.
- 시험: 검증 중에 끝난 리뷰의 결과 대기가 0보다 크게 기록된다. 옛 state로 보고서가 그려진다. 제목 있는 답과 없는 답 모두 제목이 한 번 나온다. 시험은 `tests/test_result_wait.py`, `tests/test_summary_heading.py`에 둔다.

## 범위 밖
- 검증 비동기화(범위 밖 `async-verify`).
- 이미 커밋된 옛 보고서 수정.
- 문서(10).

## 참고
- spec §3의 1-8, `.goldstack/ideas/verify-blocks-result-wait.md`, `metrics.py` docstring(동작을 바꾸면 고친다)
