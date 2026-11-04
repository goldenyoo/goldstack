# 세션 이어 가기로 worker 재시작

**무엇**: 끊긴 worker를 `claude --resume <id>`처럼 세션째 잇는다.

**왜 밖**: CLI마다 방법이 달라 어댑터 셋을 따로 만들어야 한다. 같은 worktree에서 새 worker를 띄우면 작업은 대부분 살아남는다.

**다시 볼 조건**: 같은 worktree 재시작이 맥락 부족으로 실패하거나 반복 작업을 많이 하면.

결정: goldstack-v7 grill 라운드 2-11 (2026-11-04)
