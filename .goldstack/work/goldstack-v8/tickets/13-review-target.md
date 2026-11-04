---
id: "13"
title: "첫 리뷰를 병합될 커밋의 트리에서 하고, 리뷰한 head를 기록한다"
blocked_by: ["14"]
touches: ["src/gs/go.py", "src/gs/state.py", "tests/test_review_target.py"]
model: claude
reviewer: codex
tier: large
---
## 목표
병합되지 않을 미커밋 코드를 근거로 리뷰 지적이 기각되는 일을 막는다. 재리뷰에는 이미 있는 보호를 첫 리뷰에도 넣는다.

## 완료 조건
- 첫 리뷰가 재리뷰와 같은 트리 선택을 쓴다. 티켓 worktree가 깨끗하고 head가 같으면 그 worktree(비용 그대로), 아니면 head의 임시 worktree. 티켓 worktree의 미커밋 변경은 지우지 않는다. 시험: 미커밋 수정이 있는 worktree로 끝난 worker의 리뷰어가 그 수정을 보지 못한다.
- 임시 worktree를 못 만들면 지금의 리뷰 실패 처리로 간다. 치우기 실패는 경고뿐이다. 시험이 있다.
- 리뷰 기록에 리뷰한 head(`reviewed_head`)가 남는다. 옛 state.json을 읽어도 깨지지 않는다. 시험이 있다.
- 병합 전 티켓 head가 마지막으로 리뷰·재리뷰한 head와 다르면 다시 리뷰한다. catch-up으로 합친 최신 integration은 worker 변경이 아니므로 다시 리뷰하지 않는다. 시험이 두 경우를 본다.
- 리뷰가 병합을 막지 않는다는 규칙과 v7의 네트워크 중단 경로는 그대로다.

## 범위 밖
- 2차 수정이 고친 지적을 되돌리는 경우(`invalidate-stale-review-verdicts`, v9), 리뷰어에 명령 권한 주기.

## 참고
- spec §3 5-1 b. 아이디어 `.goldstack/ideas/immutable-review-target.md`.
- `go._rereview_tree`를 함께 쓰도록 이름·위치를 정리해도 된다.
