# claude 리뷰어에 명령 실행 권한

**무엇**: claude 리뷰어(`--tools Read,Grep,Glob`)도 codex·agy처럼 명령을 돌려 재현하게 한다.

**왜 밖**: 리뷰어가 worktree를 바꿀 위험이 있어 읽기 전용으로 막는 장치가 먼저다.

**다시 볼 조건**: 재현하지 못한 것이 원인으로 claude 리뷰어가 지적을 놓친 일이 나오면.

결정: goldstack-v7 grill 라운드 3 (2026-11-04)
