# 벽시계에 기대는 시험 금지 검사

**무엇**: 시험 파일의 `time.sleep`·벽시계 의존을 verify에서 grep으로 막거나 리뷰 기준에 넣는다(아이디어 `tests-no-wall-clock`, 개별 사례 `goldstack-v36-02-1`의 `tests/test_result_grace.py`).

**왜 밖**: profile 주의점에 "시험을 새로 쓸 때 실제 시간에 기대지 않는다"가 이미 있다. 시험 파일 10개가 정상 폴링에 sleep을 써서 grep 검사는 예외 목록이 필요하다. goldstack-v42의 flaky(`StaleTest`)는 벽시계가 아니라 `ps` 행 오집힘이었고(goldstack-v43 01), `test_result_grace`는 v42 flaky 목록에 없었다.

**다시 볼 조건**: 검증 로그에서 sleep·제한 시간 때문에 떨어진 시험이 다시 나오면.

결정: goldstack-v43 grill 라운드 1-7 (2026-11-15)
