---
date: "2026-11-09"
severity: "medium"
source: "goldstack-v29 회고"
status: "open"
issues: []
feature: ""
---
integration 검증에 flaky 재시도가 없어, diff 밖 시험 하나의 1회성 실패로 feature 전체가 병합되지 않는다.

- goldstack-v29: 티켓 3장 병합·리뷰 지적 0인데 마무리 integration 검증이 `test_feedback_format.RedactionTest.test_cli_version_keeps_the_number_only` 하나로 실패해 not_merged. 이 diff는 feedback 코드·시험을 건드리지 않았고, 같은 integration 트리에서 3번 다시 돌리면 모두 통과했다. 로그: `.goldstack/work/goldstack-v29/run/finish/integration-verify.log`.
- 같은 날 재실행(gs 0.2.12): 이번에는 `test_feedback_format`이 통과하고 다른 diff 밖 시험 `test_verify.StaleTest.test_cleanup_ends_every_verify_of_the_run`이 실패(`AssertionError: False is not true : 부모가 죽어도 검증은 살아 있어야 한다`, `tests/test_verify.py` `left_behind`). 두 번 연속 서로 다른 시험 하나로 not_merged.
- 회고 subagent 보고: v17 report·v22 report에도 원인 모를 1회성 실패가 있었다. v22는 main 검증에만 재시도 1회를 넣었다.

고칠 곳: `src/gs/finish.py` integration 검증. 실패 시험 파일과 그 대상 모듈이 diff에 없으면 1회 다시 돌리고, 통과하면 보고서에 flaky로 적는다. 관련: [[cli-version-test-timeout]]
