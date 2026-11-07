# worker의 uv 캐시 위치

**무엇**: worker 환경에서 uv 캐시 위치를 쓰기 가능한 곳으로 잡아 준다(issue #36 제안 ④).

**왜 밖**: uv 전용이라 환경을 가정하게 되고, `profile.md`의 sandbox 명령으로 풀린다.

**다시 볼 조건**: `profile.md` 명령으로 풀리지 않는 레포가 나오면.

결정: goldstack-v22 grill 라운드 2-7 (2026-11-07)
