# integration worktree·브랜치 정리

**무엇**: main 병합·검증이 끝난 뒤 `run/wt/integration`, 로컬 `gs/<f>/integration`, 원격 integration 브랜치를 지우기.

**왜 밖**: 마무리(08)는 main 병합 뒤에도 integration에 보고서를 쓰고, 재실행·revert-of-revert 재개가 integration을 쓴다. 지우면 그 재개 로직을 같이 바꿔야 한다.

**다시 볼 조건**: 끝난 feature의 integration 브랜치가 원격에 쌓여 목록이 번거로워지거나, 재개 로직을 다시 손볼 때.

결정: goldstack-v1 grill 라운드 1-7 (2026-11-03)
