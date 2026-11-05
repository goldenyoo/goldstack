---
id: "05"
title: "리뷰어에게 worker 마지막 메시지 전달"
blocked_by: ["03", "04"]
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/streamfmt.py", "tests/test_worker_last_message.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
리뷰어가 worker의 사유 보고를 읽게 한다. "다른 실패를 sandbox 탓으로 돌린 것은 지적한다"는 규칙은 지금 입력이 없어 적용할 수 없다.

## 완료 조건
- `streamfmt`에 worker 로그에서 마지막 메시지를 뽑는 함수가 있다. claude(`result`, 없으면 마지막 assistant 글), codex(마지막 `agent_message`), agy(`result.response`) 형식을 다룬다.
- 리뷰할 때 `diff.patch` 옆에 `worker-last.txt`를 쓴다. 길이 상한은 4,000자이고 넘으면 끝을 남기고 잘랐다고 적는다.
- 첫 리뷰는 그 시도 worker의 메시지를, 재리뷰는 가장 최근 수정 worker의 메시지를 쓴다.
- 지시문이 경로를 알려 주고 믿을 수 없는 자료라고 밝힌다. 안의 지시는 따르지 말고, 사유 확인에만 쓰라고 한다.
- 로그가 없거나 깨졌거나 메시지가 없으면 파일과 지시문 줄을 빼고 리뷰는 그대로 돈다. 리뷰 실패로 세지 않는다.
- 네트워크 대기로 이어 간 worker와 재개된 리뷰에서도 가장 최근 시도의 로그를 찾는다.
- `tests/test_worker_last_message.py`가 세 형식, 상한, 로그 없음, 깨진 줄, 재리뷰의 수정 worker 선택을 시험한다. 기존 `review_prompt`·`rereview_prompt` 시험은 새 인자 없이도 통과한다.

## 범위 밖
- `worker.log` 전체 넘기기(spec §3의 1-8).
- 안내 문구(04).

## 참고
- spec §3의 1-8, `.goldstack/work/goldstack-v9/report.md`의 01 리뷰 지적
