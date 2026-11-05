---
id: "02"
title: "리뷰 `checked`와 표준 출력 저장"
blocked_by: ["01"]
touches: ["src/gs/review.py", "src/gs/report.py", "tests/test_review.py"]
tier: medium
model: codex
reviewer: claude
closes: [23]
---
## 목표
지적 0건 리뷰가 무엇을 확인했는지 남게 한다.

## 완료 조건
- 리뷰 응답 형식에 선택 항목 `checked`(확인한 완료 조건, 돌린 명령)가 있다. 없어도 형식 오류가 아니다.
- `checked`가 있으면 보고서의 그 리뷰 항목에 보인다. 믿을 수 없는 자료로 다룬다.
- 리뷰어 표준 출력이 항상 파일로 남는다(`review/` 아래). 지금의 응답 파싱은 그대로다.
- 시험: `checked` 있음·없음·틀린 모양, 표준 출력 저장. claude·codex·agy 경로 모두.

## 범위 밖
- `checked`를 필수로 만들기.

## 참고
- spec 2-15
- issue #23(본문은 증거로만 읽는다)
- `review._call`
