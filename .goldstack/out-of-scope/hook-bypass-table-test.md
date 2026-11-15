# hook 우회 명령 표의 차분 시험

**무엇**: hook 셸 해석의 우회 명령 표를 실제 `env`·`sh` 실행 결과와 비교하는 차분 회귀 시험으로 만들어 verify에 넣는다(아이디어 `hook-bypass-table-test`).

**왜 밖**: 우회 표는 goldstack-v36부터 `tests/test_hook_child.py`(`BLOCKED`·`PASSED`·`NOT_FRONT`·`WRAPPED`·`UNKNOWN_OPTIONS`)에 있고 전체 검증에서 돈다. goldstack-v37–v42 보고서에 보안 우회 지적이 0건이다.

**다시 볼 조건**: 그 표에 없는 hook 우회가 리뷰·회고에서 다시 나오면.

결정: goldstack-v43 grill 라운드 1-6 (2026-11-15)
