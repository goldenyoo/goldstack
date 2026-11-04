---
date: "2026-11-04"
severity: "high"
source: "2026-11-04 Codex 리뷰(Claude가 코드 대조)"
status: "taken"
feature: "goldstack-v8"
---
첫 리뷰가 미커밋 변경이 남은 worktree를 읽어, 병합되지 않을 코드를 근거로 지적을 기각할 수 있다.

**근거(코드 확인, 재현 안 함)**: `go._finish`는 worktree가 깨끗하지 않아도 경고만 하고 `_review`로 간다. `_review`는 리뷰어에게 `a.wt`를 그대로 준다. diff는 `review.write_diff`가 브랜치로 만들어 커밋만 담지만, 코드 맥락을 읽는 worktree에는 미커밋 수정이 보인다. 리뷰 기록에 리뷰한 head SHA도 없다.

**시나리오**: worker가 결함 있는 코드를 커밋하고 실제 수정은 커밋하지 않는다. 리뷰어나 판단 모델이 worktree의 고친 코드를 보고 지적을 기각한다. 병합에는 결함 있는 커밋만 들어간다.

**재리뷰는 이미 막혀 있다**: v6 01의 같은 지적을 `go._rereview_tree`가 고쳤다(head와 다르거나 미커밋이 있으면 임시 worktree). 첫 리뷰에만 빠져 있다.

**제안(M)**: 첫 리뷰도 `_rereview_tree`와 같은 트리를 쓰고 `reviewed_head`를 기록한다. 병합 전에 티켓 head가 그 값과 다르면 다시 리뷰한다. 깨끗하고 head가 같으면 지금처럼 worktree를 써서 비용을 늘리지 않는다.
