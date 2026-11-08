---
id: "05"
title: "재실행할 때 앞 시도의 지적을 보존해 보고서에 따로 보인다"
blocked_by: ["01", "03"]
touches: ["src/gs/state.py", "src/gs/go.py", "src/gs/report.py", "tests/test_state.py", "tests/test_resume_report.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
실패한 티켓을 다시 돌려도 앞 시도의 리뷰 지적이 기록에서 사라지지 않게 한다.

## 완료 조건
- 새 시도가 티켓의 리뷰 기록(`review`, `second_review`)을 비우기 전에, 지적이 있으면 시도 번호·리뷰어·리뷰 대상 SHA와 함께 state `prior_findings`에 옮긴다. 옛 state(값 없음)도 읽힌다.
- 보고서에 "버려진 시도의 지적" 절이 있고 시도 번호·리뷰어·severity·지적 한 줄이 보인다. 없으면 절이 없다.
- 이 지적은 남은 high 집계와 아이디어 파일 쓰기에 들어가지 않는다. 시험한다.

## 범위 밖
- 버려진 시도의 지적을 다음 시도 brief에 넘기기

## 참고
- spec §3 1-6
- 아이디어 `rerun-keeps-prior-findings`
