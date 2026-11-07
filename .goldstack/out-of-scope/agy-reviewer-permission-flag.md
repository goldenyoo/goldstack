# agy 리뷰어의 권한 플래그

**무엇**: `src/gs/review.py`의 agy 리뷰어 호출에서 `--dangerously-skip-permissions`를 뺀다.

**왜 밖**: 리뷰어는 deny 규칙을 함께 쓰고 #33의 auto mode 거부와 경로가 다르다. 빼면 리뷰가 명령을 돌리지 못할 수 있어 따로 재야 한다.

**다시 볼 조건**: 신뢰할 수 없는 diff를 읽는 agy 리뷰어가 그 권한을 실제로 쓴 기록이 나오면.

결정: goldstack-v21 grill 라운드 3 (2026-11-07)
