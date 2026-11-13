# integration 되돌리기 건너뛰기와 git.sha 캐시

**무엇**: `go._reset_integration`이 integration이 이미 깨끗하고 HEAD가 같으면 `status`·`clean`을 건너뛰고, 한 루프 틱 안의 `git.sha` 결과를 캐시해 git 호출을 더 줄인다.

**왜 밖**: 재개·되돌리기 흐름을 바꾸는 large 티켓이고, 캐시를 비울 시점이 곳곳에 퍼진다. goldstack-v39는 상태 판단을 바꾸지 않는 `setup.marker`·`_tree_state`만 줄인다(측정: `test_final_high` git 호출 9872회 중 `_reset_integration` 약 500, `git.sha` 1274).

**다시 볼 조건**: goldstack-v39 04 뒤에도 티켓 검증과 병합 대기가 일렬 경로의 30% 넘게 보고서에 남으면.

결정: goldstack-v39 grill 라운드 3-1 (2026-11-13)
