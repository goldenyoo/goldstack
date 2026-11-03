---
id: "01"
title: "재리뷰 흐름: 2차 수정, 새 지적, 두 리뷰어, 시간 상한, agy 횟수"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/review.py", "src/gs/state.py", "src/gs/config.py", "tests/test_rereview.py"]
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
리뷰 지적을 고친 수정 커밋을 같은 리뷰어가 다시 보게 해, "고쳤지만 확인 안 됨"으로 병합되는 일을 없앤다.

## 완료 조건
- 수정 worker가 커밋하면 재리뷰를 띄운다. 재리뷰 입력은 수정 커밋들의 diff(수정 전 티켓 head..수정 뒤 head), 그 리뷰어가 낸 fix 지적 목록, 티켓·spec. 출력은 지적마다 `resolved` | `unresolved`(+근거)와 새 지적 목록(기존 리뷰 지적 형식). `review.fix_brief`의 "재리뷰는 없다" 문장과 go.py·review.py docstring을 새 흐름에 맞춘다.
- 지적을 낸 리뷰어만 재리뷰한다(둘 다 냈으면 `run_together`로 동시). 새 문제는 재리뷰하는 리뷰어 모두가 본다(spec 2-2). 시험: 한쪽만 지적, 둘 다 지적.
- 1차 재리뷰에 `unresolved`가 있거나, 새 지적 중 판단 모델이 fix로 본 것이 있으면 2차 수정 worker를 한 번 띄우고(대상: unresolved + 새 fix 지적) 다시 재리뷰한다. 2차 재리뷰 뒤에는 더 고치지 않는다: 남은 `unresolved`는 미해결, 2차 재리뷰의 새 지적은 보고만(spec 2-1). 수정은 티켓당 최대 2회(시험: 1차에서 모두 resolved → 2차 없음, 1차 unresolved → 2차 → resolved, 2차 뒤에도 unresolved).
- 지적 state에 결과를 남긴다: `fix_attempt`(attempted·discarded·빈 값)에 더해 재리뷰 결과(`resolved`·`unresolved`·`unchecked`와 이유: 시간 초과·한도·재리뷰 실패), 몇 번째 수정인지. 02가 보고서에 쓴다.
- `timeouts.rereview_minutes`(정수 >0, 기본 10) config 키(`gs check` 범위 검사, `gs init` 예시). 넘기면 그 리뷰어의 지적은 `unchecked(시간 초과)`(시험).
- 재리뷰도 agy 호출 1회로 센다. 한도면 그 재리뷰를 띄우지 않고 `unchecked(한도)`. 한도로 수정 worker를 못 띄우면 지금처럼 수정 전 구현 병합, 지적은 `수정 못 함(한도)`로 표시되게 state에 남긴다(시험: 기존 `test_agy_fix_worker_at_limit…` 갱신).
- 재리뷰·2차 수정 실패나 예외는 병합을 막지 않는다(지적은 unchecked·discarded). 2차 수정이 실패하면 그 수정만 버리고(1차 수정 결과는 남김) 진행.
- verify는 마지막에 한 번(구현 → 리뷰 → 수정 → 재리뷰 → (2차 수정 → 재리뷰) → verify → 병합, spec 2-4).
- 진행 단계 이름: `rereview`, `fix2`를 state 단계로 기록(표시 문구는 02).

## 범위 밖
- 보고서의 지적별 상태 표시·개수, 진행 바 문구: 02

## 참고
- spec §3 1-2, 1-4, 2-1~2-4, §6 리뷰→수정 흐름·agy 한도와 수정
