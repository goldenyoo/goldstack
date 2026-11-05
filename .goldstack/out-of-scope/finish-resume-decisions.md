# 재개 판단까지 순수 함수로 분리

**무엇**: `finish.run`의 재개 분기와 `go._resuming`·`_finished_after_clean`을 `revert_decision`과 같은 방식의 순수 함수로 옮기고, 전이표와 겹치는 시나리오 시험을 줄인다.

**왜 밖**: 구조가 결함의 원인이라는 증거가 아직 없다. 먼저 `_postmerge`의 되돌리기 판단만 빼서 값을 본다.

**다시 볼 조건**: goldstack-v10 01을 마친 뒤 입력 수집이 단순했고, 재개·마무리 판단 결함이 또 나오면.

결정: goldstack-v10 grill 라운드 1-5 (2026-11-05)
