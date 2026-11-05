---
id: "04"
title: "부하에 약한 시험을 실제 시간과 초 단위 시각에 기대지 않게 고친다"
blocked_by: []
touches: ["tests/test_async_review.py", "tests/test_go_review_retry.py", "tests/test_go_finish.py", "tests/test_metrics.py", "tests/test_go_execution.py", "tests/test_network_wait.py", "tests/test_rereview.py", "tests/test_review_network.py", "tests/test_setup.py", "tests/test_verify.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker가 동시에 돌아 부하가 걸려도 전체 검증이 시험 시간 때문에 떨어지지 않게 한다.

## 완료 조건
- `test_review_network.test_retry_starts_after_previous_call_ended`가 1초 제한에 호출 횟수를 맡기지 않는다. 지키려는 사실(앞 호출의 프로세스가 끝난 뒤 다음 호출이 시작한다)은 그대로 시험한다.
- `touches`의 시험 파일에서 짧은 제한 시간, 고정 `sleep` 뒤 단정, 같은 초의 시각에 기대는 곳을 훑어, 부하에서 결과가 달라질 수 있는 곳을 고친다. 고치지 않은 곳은 이유를 worker 마지막 메시지에 적는다.
- 시험을 빠지거나 건너뛰게(`skip`) 하거나 재시도로 감추지 않는다. 고친 시험이 지키던 사실을 잃지 않는다.
- 전체 병렬 시험 3벌을 동시에 돌려(`ls tests | grep '^test_' | xargs -P 6 -n 1 uv run python -m unittest discover -s tests -p`를 셋) 모두 통과한다. 결과와 걸린 시간을 worker 마지막 메시지에 적는다. 못 돌렸으면 이유를 적는다.

## 범위 밖
- 시험 코드 밖(`src/gs/`)의 변경. 시험만으로 고칠 수 없으면 그 시험을 고치지 않고 마지막 메시지에 적는다.
- 검증 병렬 수 변경(spec 1-6에서 뺌).

## 참고
- spec §3의 1-6, `.goldstack/ideas/load-sensitive-tests.md`
