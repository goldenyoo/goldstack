# touches 밖 시험 충돌을 바로 수리로

**무엇**: worker가 `touches 밖 충돌: <파일>`을 남기면 gs가 수정 루프를 끝까지 돌리지 않고 바로 수리(touches 제한 없음)로 보낸다.

**왜 밖**: 원인이 grill에서 충돌 시험을 touches에 빠뜨린 것이라 grill 템플릿 지시로 먼저 막는다(goldstack-v39 05). gs 쪽은 코디네이터 상태 전이(large)다.

**다시 볼 조건**: grill 지시를 넣은 뒤에도 touches 밖 시험 충돌로 수정 루프를 끝까지 도는 일이 보고서·회고에 다시 나오면.

결정: goldstack-v39 grill 라운드 2-5 (2026-11-13)
