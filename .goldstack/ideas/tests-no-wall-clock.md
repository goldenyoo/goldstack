---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v36"
status: "open"
issues: []
feature: ""
---
실제 시간(sleep·벽시계)에 기대는 시험이 부하가 걸리면 실패한다. goldstack-v36에서만 세 곳이 문제가 됐다.

- 수리 검증 1회차가 `test_verify.StaleTest.test_group_that_will_not_end_warns_instead_of_raising`에서 실패했다(`run/03/1/repair/verify.log` 617행, 병렬 `xargs -P 6`). 재시도에서 통과했고 report에 flaky로 적혔다.
- `test_async_review.SeatsTest`가 부하로 일시 실패했다. 이 내용은 agy 요약에서 옮긴 것이다.
- 02의 가짜 worker 시험이 실제 sleep 때문에 2라운드 재지적됐다. 개별 지적은 열린 아이디어 `goldstack-v36-02-1`에 있다.
- 고칠 곳: 리뷰 기준이나 시험 규칙에 "벽시계 sleep 금지, 가짜 시계 사용"을 넣는다. 기계로 잡을 수 있으면 시험 파일의 `time.sleep`을 grep하는 검사를 verify에 넣는다. 실제 프로세스가 꼭 필요한 통합 시험은 예외로 둘 기준도 함께 정한다.
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
