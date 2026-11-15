---
id: "02"
title: "재리뷰: 첫 리뷰어와 겹치는 지적만 낸 두 번째 리뷰어를 부르지 않는다"
blocked_by: []
touches: ["src/gs/go.py", "tests/test_second_reviewer_rereview.py", "tests/test_second_reviewer_overlap.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
두 번째 리뷰어(티켓 `second_reviewer`)의 첫 리뷰 fix 지적이 모두 첫 리뷰어 지적과 같은 곳이면, 재리뷰에 그 리뷰어를 다시 부르지 않고 첫 리뷰어가 함께 판정하게 해 일렬 경로를 줄인다(goldstack-v41 01: 두 번째 리뷰어 1차 재리뷰 583초).

## 완료 조건
- 겹침 판정: 두 번째 리뷰 기록의 첫 리뷰 지적(`found_round` 0) 중 `action`이 `fix`인 것 하나하나가, 첫 리뷰 기록의 첫 리뷰 지적(action 무관) 중 하나와 겹치면 "모두 겹친다"이다. 두 지적이 겹친다 = `location`에서 뽑은 (파일, 줄 범위) 중 파일 이름이 같고 줄 범위가 ±5줄 안에서 맞닿는 쌍이 있다. `location` 형식: `파일:줄`, `파일:줄-줄`(`–`도), 한 파일 뒤 `,`로 이은 여러 줄·범위, `;`로 이은 여러 파일. 줄 번호가 없는 위치(`file_01`, `a`)는 어느 것과도 겹치지 않는다. fix 지적이 하나도 없으면 이 판정으로 빼지 않는다(지금처럼 config대로. defer·report만 낸 두 번째 리뷰어의 수리 재리뷰는 그대로다. `tests/test_second_reviewer_rereview.py` `test_all_calls_both_reviewers_in_repair_review`가 이 경우다).
- "모두 겹친다"이면 그 티켓의 모든 재리뷰 회차(1차·2차·수리 재리뷰)에서 두 번째 리뷰어를 부르지 않는다. config `[review] second_reviewer_rereview`가 이미 빼는 회차는 그대로 뺀다. 빠진 회차의 판정할 지적은 기존 장치대로 첫 리뷰어 재리뷰에 함께 싣는다(`_rereview_slots`, `_lent_ids`). config 키는 더하지 않는다.
- 판정은 state에 남은 지적만으로 정해지므로, 재개한 `gs go`도 같은 판정을 낸다. 시험한다.
- 건너뛸 때 실행 로그에 한 줄을 남긴다. 예: `02 두 번째 리뷰어(agy) 재리뷰 건너뜀: fix 지적이 모두 첫 리뷰어와 겹침(agy-1~codex-1)`.
- 시험(`tests/test_second_reviewer_overlap.py`, 가짜 리뷰어): (a) 겹치면 1차 재리뷰에 두 번째 리뷰어가 불리지 않고 그 지적이 첫 리뷰어 재리뷰 호출에 실려 판정된다. (b) 하나라도 겹치지 않으면 지금처럼 불린다. (c) 줄 번호 없는 위치는 불린다. (c2) fix 지적이 없으면(defer만) 지금처럼 config대로 불린다. (d) ±5줄 경계(5줄 차이는 겹침, 6줄은 아님). (e) 위치 형식 단위 시험(`,`·`;`·범위·`–`). (a)·(b)는 판정 코드를 지우면 실패해야 한다.
- 기존 `tests/test_second_reviewer_rereview.py`의 fixture가 새 규칙에 걸려 의도가 바뀌면, 그 시험의 의도(설정 키 동작)가 유지되도록 지적 위치를 겹치지 않게 고친다. 단언을 약하게 하지 않는다.
- `go.py` 모듈 docstring(두 번째 리뷰어 재리뷰 절)과 `_rereview_slots`·`_second_skipped` docstring을 새 동작에 맞게 고친다.

## 범위 밖
- 판단 모델이 같은 결함을 표시하는 방식, 첫 리뷰에서 두 번째 리뷰어를 빼는 것(spec 결정 2-2).

## 참고
- spec §3 결정 2-2·2-3, §6 위치 겹침 모의. 아이디어 `second-reviewer-duplicate-rereview`. docs/guide.md `[review] second_reviewer_rereview` 절
