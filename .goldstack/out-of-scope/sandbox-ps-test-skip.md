# sandbox `ps` 차단 시험 skip

**무엇**: 시험이 sandbox의 `ps` 차단을 감지하면 `ps`가 필요한 시험을 skip한다.

**왜 밖**: gs 검증 환경까지 `ps`를 막게 되면 시험이 조용히 빠진다. 제품 코드(`verify.py`, `worker.py`)도 `ps`를 불러 시험에서만 걷어 낼 수 없다(`alive-without-ps`). goldstack-v40은 brief·리뷰 지시와 profile 목록으로 다시 돌리는 시간만 없앤다.

**다시 볼 조건**: 글 규칙 뒤에도 worker·리뷰어가 `ps` 차단 실패 시험을 되풀이해 돌린 일이 다음 실행 로그에 나오면.

결정: goldstack-v40 grill 라운드 2-5 (2026-11-14)
