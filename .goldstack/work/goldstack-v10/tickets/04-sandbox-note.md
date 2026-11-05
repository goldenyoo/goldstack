---
id: "04"
title: "sandbox 안내 통일(네트워크·localhost·홈 쓰기)"
blocked_by: []
touches: ["src/gs/adapters.py", "src/gs/worker.py", "src/gs/review.py", "tests/test_adapters.py", "tests/test_sandbox_brief.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
codex 전용 안내, 공통 worker 지시문, 리뷰 지시문이 같은 기준을 말하게 한다. worker가 sandbox 안에서 고칠 수 없는 실패에 시간을 쓰거나 커밋 없이 끝나지 않게 한다.

## 완료 조건
- `adapters.Codex.NOTE`, `worker.write_brief`, `review.review_prompt`, `review.rereview_prompt`가 같은 세 가지를 면책한다: 네트워크, localhost, 홈 디렉터리 쓰기.
- worker 쪽 문구는 그 단계와 이유를 마지막 메시지에 적고 커밋하라고 한다. 다른 실패를 sandbox 탓으로 돌리지 말고 그 밖의 실패는 고치라고 한다.
- 리뷰 쪽 문구는 이 세 가지를 sandbox 때문에 돌리지 못한 것만으로는 지적하지 않고, 다른 실패를 sandbox 탓으로 돌린 것은 지적하라고 한다.
- gs가 sandbox 밖 병합 트리에서 다시 검증한다는 문장이 worker 쪽에 남는다.
- 시험이 네 문구 모두에서 세 가지가 있는지 확인한다. 네트워크만 말하는 옛 단정을 고친다.

## 범위 밖
- 리뷰어에게 worker 마지막 메시지 넘기기(05).
- worker 전용 검증 명령(범위 밖 `verify-worker-key`).

## 참고
- spec §3의 1-7, `.goldstack/work/goldstack-v9/report.md`의 01 리뷰 지적
