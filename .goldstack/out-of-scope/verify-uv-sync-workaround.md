# verify 앞 `uv sync` 우회 빼기

**무엇**: 이 레포 spec `verify` 앞의 `uv sync --locked -q`를 빼고 `setup_when`의 setup 재실행에 맡긴다.

**왜 밖**: `setup_when`은 이번 feature가 만들고, 실행 중인 gs는 설치본이라 이번 실행에서는 아직 쓰이지 않는다. 우회는 1초 안팎이다.

**다시 볼 조건**: `setup_when`이 들어간 gs로 버전을 올린 티켓이 한 번 이상 우회 없이도 통과할 근거(setup.log 재실행 기록)가 나오면.

결정: goldstack-v25 grill 라운드 1-2 (2026-11-08)
