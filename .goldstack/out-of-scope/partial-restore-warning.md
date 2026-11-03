# 일부만 복구된 merged 티켓의 반복 경고

**무엇**: state가 일부만 복구된 merged 티켓에서 `gs go`를 돌릴 때마다 잘못된 경고가 나오고, 기본 위치에 남은 worktree도 지우지 않는다(goldstack-v1 리뷰 02 low).

**왜 밖**: integration 표시가 사라지는 드문 경우에만 나고, 고치려면 재시도·리셋 정책을 건드려야 한다. v3는 `kept_worktrees` 재확인(g1)과 `--only` 밖 표시(g2)만 다룬다.

**다시 볼 조건**: 실제 실행에서 이 경고가 한 번이라도 나오면.

결정: goldstack-v3 grill 라운드 1-6 (2026-11-03)
