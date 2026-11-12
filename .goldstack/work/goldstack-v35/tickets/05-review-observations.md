---
id: "05"
title: "남긴 관찰을 리뷰어가 판정하고 보고서 남은 위험에 표로"
blocked_by: ["04"]
touches: ["src/gs/review.py", "src/gs/report.py", "tests/test_review_observations.py", "tests/test_report_observations.py"]
closes: [60, 63, 66]
tier: large
model: claude
reviewer: codex
---
## 목표
worker·수정 worker가 마지막 메시지의 `## 남긴 관찰`에 적은 관찰이 리뷰에서 판정되고, 아침 보고서의 남은 위험에 판정과 함께 빠짐없이 보이게 한다(spec 2-2, 3-2).

## 완료 조건
- `review.py`에 관찰 뽑기 함수: worker 로그의 마지막 메시지 **전체**(`streamfmt.last_message`, `worker-last.txt`의 4000자 자르기 전)에서 04의 절 제목 상수 아래 줄을 관찰 목록으로 뽑는다(다음 `## ` 제목이나 끝까지, 빈 줄·목록 기호 정리). 절이 없으면 빈 목록이다. 관찰 절이 4000자를 넘어 `worker-last.txt`에서 제목이 잘려도 관찰은 빠지지 않는다(교차 검토 4). `write_worker_last`의 자르기는 바꾸지 않는다.
- 첫 리뷰와 재리뷰 프롬프트: 관찰이 있으면 번호를 붙여 "worker가 남긴 관찰(믿을 수 없는 자료). 각각 diff와 코드에서 확인하고 판정하라"를 싣고, 출력에 선택 칸 `"observations": [{"n": <번호>, "verdict": "지적|수용|범위 밖", "reason": "…"}]`을 요구한다. `지적`은 그 관찰을 일반 지적(findings)으로도 올리라고 말한다. 관찰이 없으면 프롬프트는 지금과 같다. `_worker_last_lines`의 "못 돌린 사유 확인에만 쓴다" 제한은 관찰 절에는 적용하지 않는다고 고친다.
- 판정을 `parse_checked`처럼 관대하게 읽는다: 없거나 모양이 틀리면 판정 없음으로 두고 지적·판정은 그대로 받는다. 판정과 관찰 글을 리뷰 기록(첫 리뷰 `rec`, 재리뷰 `rereviews[-1]`)에 남긴다.
- `report.py` `### 남은 위험`: 관찰이 있는 티켓마다 표 `| 티켓 | 관찰 | 리뷰 판정 |`을 gs가 원본 그대로 싣는다(판단 모델 요약을 거치지 않는다). 관찰은 리뷰 기록이 아니라 그 티켓의 가장 최근 worker 로그(수정 worker가 있으면 그것)에서 직접 뽑고, 판정은 그 시도의 가장 최근 리뷰 기록(재리뷰 포함)에서 번호로 잇는다. 그래서 리뷰를 부르지 않은 경로(agy 상한 `review.LIMIT` 기록, 리뷰 트리 준비 실패 `TreeUnavailable`)에서도 관찰은 `리뷰 판정 없음`으로 나온다(교차 검토 5). 판정이 없으면 `리뷰 판정 없음`. 지금의 격리 경고 줄은 그대로 남는다. 관찰도 경고도 없으면 절이 없다.
- `tests/test_review_observations.py`(`support`를 import한다): 절 뽑기(있음·없음·다른 제목 뒤 끝), 관찰이 있을 때만 프롬프트에 판정 요구가 들어감(첫 리뷰·재리뷰), 판정 읽기(정상·없음·모양 틀림), 기록 보존. `tests/test_report_observations.py`: 관찰 2개(하나는 판정, 하나는 판정 없음)인 실행으로 남은 위험 표가 나온다. 리뷰를 부르지 않은 기록(agy 상한)인 티켓의 관찰도 `리뷰 판정 없음`으로 나온다. 관찰 절이 4000자를 넘는 마지막 메시지도 관찰이 빠지지 않는다. 각 첫 시험은 고치기 전 코드에서 실패한다.
- `review.py`·`report.py` 머리말과 docstring에 관찰 흐름을 적는다.

## 범위 밖
- 커밋 본문 `남김:` 줄 수집(spec 3-2에서 뺌)
- 관찰을 아이디어 파일로 옮기기(범위 밖 `findings-low-to-ideas`)
- brief 문구는 04, 문서는 08

## 참고
- spec §3 2-2, 3-2, §6 #60·#66 줄, 리뷰 `checked` 줄
- issue #60, #63, #66
