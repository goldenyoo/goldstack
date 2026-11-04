---
id: "01"
title: "worker·리뷰 지시문에 sandbox 네트워크 안내"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/review.py", "tests/test_sandbox_brief.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
sandbox에서 네트워크가 막혀 검증 명령 일부를 못 돌린 worker가 무엇을 해야 하는지, 리뷰어가 그것을 어떻게 읽어야 하는지 정한다. v7 01과 v8 02·10에서 `uv build`가 hatchling을 받지 못했다.

## 완료 조건
- `worker.write_brief`의 지시문이 말한다: 네트워크가 필요한 단계만 못 돌렸으면 어떤 단계가 왜 못 돌았는지 마지막 메시지에 적고 커밋한다. 그 밖의 실패는 지금처럼 고쳐야 한다. gs가 커밋된 내용을 sandbox 밖 병합 트리에서 다시 검증한다.
- 첫 리뷰와 재리뷰 지시문이 말한다: 네트워크가 필요한 단계를 worker가 sandbox에서 못 돌린 것만으로 지적하지 않는다. 다른 실패를 네트워크 탓으로 돌린 것은 지적한다.
- 시험이 지시문 세 곳에 위 내용이 있는지 확인한다.
- 새 config 키는 없다.

## 범위 밖
- worker 전용 검증 명령(`.goldstack/out-of-scope/verify-worker-key.md`).
- sandbox에 네트워크 열기.

## 참고
- spec §3 1-10, §6 worker verify. 아이디어 `.goldstack/ideas/worker-sandbox-verify-note.md`.
