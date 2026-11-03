---
id: "03"
title: "두 리뷰 동시 실행, agy 횟수 세기·건너뜀, 보고서"
blocked_by: ["02"]
model: claude
reviewer: codex
---
## 목표
`second_reviewer`가 있는 티켓에서 두 리뷰를 함께 돌려 지적을 합치고, gs가 부르는 agy 호출을 세어 상한에 닿으면 건너뛴다.

## 완료 조건
- `second_reviewer`가 있으면 리뷰 단계에서 두 리뷰를 동시에 띄우고, 둘이 끝나거나 시간 제한에 닿으면 지적을 합쳐 수정 단계 한 번으로 넘긴다. 한쪽이 실패·시간 초과·거부여도 다른 쪽 결과로 진행한다(시험: 둘 다 성공, 한쪽 실패, 둘 다 실패).
- 진행 바·`gs status`에서 두 리뷰가 보인다(예: `03 리뷰 중(codex+agy)`).
- state에 이번 실행의 agy 호출 수를 센다(worker 1번, 리뷰 1번 = 1회, 재시도·수정 포함). 상한에 닿으면 이후 agy 리뷰는 띄우지 않고 "건너뜀(한도)"으로 적는다. agy worker가 상한에 닿으면 그 티켓은 실패로 적고 이유에 한도를 쓴다(시험: 상한 1에서 agy 리뷰 두 장).
- 보고서: 티켓 결과에 리뷰마다(계열 이름 붙여) 지적이 나오고, 건너뛴 리뷰는 `건너뜀(한도)`, Evidence 끝에 `agy 사용: N/상한`(시험).
- `second_reviewer`가 없는 티켓의 리뷰 흐름은 바뀌지 않는다(기존 시험 통과).

## 범위 밖
- 남은 사용량을 읽어 판단(out-of-scope `usage-adapters`)
- 한도 걸린 codex·claude를 agy로 대신(아이디어 `agy-gemini-usage` 보류 항목)

## 참고
- spec §3 1-8, 1-9, 2-4, 2-5. touches: `src/gs/go.py` `src/gs/review.py` `src/gs/report.py` `src/gs/state.py` `tests/test_second_review.py`
