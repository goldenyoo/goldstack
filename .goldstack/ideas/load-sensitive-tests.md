---
date: "2026-11-05"
severity: "medium"
source: "/retro goldstack-v10"
status: "taken"
feature: "goldstack-v11"
---
worker가 동시에 돌아 부하가 걸리면 실패하는 시험이 전체 검증을 다시 돌게 한다.

**근거**:
- goldstack-v10 02 수정 worker: 전체 검증에서 `test_review_network`의 `test_retry_starts_after_previous_call_ended`가 호출 2번(기대 3번)으로 실패했고 단독으로는 3번 다 통과했다. 이 시험은 호출 제한을 1초로 둔다. 원인은 부하로 추정하며 확정하지 않았다.
- 같은 worker의 다음 전체 검증에서는 02가 만든 `test_someone_else_reverted_while_waiting_is_not_reverted_twice`가 실패했다. "다른 사람"이 gs와 같은 신원으로 같은 초에 revert하면 커밋 SHA가 같아진다. 이 시험은 그 worker가 고쳤다. 전체 검증은 모두 3번 돌았다.
- goldstack-v9: `test_network_wait`의 같은 시험이 전체 검증을 3번 떨어뜨렸고 PR #14에서 고쳤다.

**제안**: `test_review_network`의 1초 제한을 실제 시간에 기대지 않게 바꾼다. 다른 시험에서도 짧은 제한 시간과 초 단위 시각에 기대는 곳을 찾는다. 전체 검증을 worker 3개와 함께 돌려 확인한다.
