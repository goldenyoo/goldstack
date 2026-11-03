# 실패 worktree 정리

**무엇**: 실패한 시도의 worktree(state `failed_worktrees`)를 재시도가 병합된 뒤나 일정 기간 뒤에 지우기.

**왜 밖**: v0 07에서 실패 증거로 보존하기로 정했고, 이번에 뒤집을 근거가 없다. 실패는 드물어 쌓이는 양이 적다.

**다시 볼 조건**: 실패 worktree가 feature마다 여럿 쌓여 손으로 지우는 일이 반복되면.

결정: goldstack-v1 grill 라운드 1-9 (2026-11-03)
