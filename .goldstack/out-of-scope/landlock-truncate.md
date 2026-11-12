# Landlock ABI 1의 truncate·chmod

**무엇**: landlock 모드에서 쓰기 목록 밖 파일을 경로로 부르는 `truncate(2)`로 비우거나 `chmod`로 권한을 바꾸는 것을 막는다(seccomp 필터 등).

**왜 밖**: Landlock ABI 1은 이 둘을 다루지 않는다(ABI 3부터 truncate). pod에서 `os.truncate(<목록 밖 파일>, 0)`과 `chmod`가 통과하는 것을 쟀다(2026-11-12). `open`을 거치는 쓰기(`echo >`, coreutils `truncate`)는 막힌다. 막으려면 seccomp 필터를 새로 짜야 하고, worktree 안의 정상 `chmod`까지 가를 규칙이 필요하다. 지키려는 것(자격 증명 읽기, push·gh 쓰기)은 이 한계와 무관하다.

**다시 볼 조건**: landlock 모드에서 worker·리뷰어가 쓰기 목록 밖 파일을 비우거나 권한을 바꾼 기록이 나오면, 또는 그 머신 커널이 ABI 3 이상이 되면.

결정: goldstack-v32 grill 라운드 4-1 (2026-11-12)
