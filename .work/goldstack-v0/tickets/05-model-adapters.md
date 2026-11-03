---
id: "05"
title: "모델 어댑터: codex, agy"
blocked_by: ["02", "11"]
model: claude
reviewer: codex
---
## 목표
티켓의 `model`이 codex나 agy여도 worker를 띄울 수 있다.

## 완료 조건
- 모델별 어댑터가 같은 입력(brief 경로, worktree, 로그 경로)을 받아 실행 명령을 만들고 종료 코드를 돌려준다. claude 어댑터도 같은 인터페이스로 옮긴다.
- codex: `codex exec --json -s workspace-write`. sandbox에서 못 돌린 시험은 어차피 `gs`가 `verify`로 다시 돌린다.
- agy: 11의 권고대로 띄운다. 차단 장치가 없다고 나오면 agy를 구현 worker로는 거부하고 `gs check`도 경고한다.
- worker 환경에 `GS_ROLE=worker`를 넣는다(09 hook이 이 값을 본다).
- 어댑터별 명령 조립 단위 시험이 있다. 실제 codex·agy로 작은 티켓을 한 번씩 돌린 로그를 PR 본문에 증거로 붙인다.

## 범위 밖
- 리뷰에서의 모델 호출(06), 사용량에 따른 모델 선택(.out-of-scope/usage-adapters.md).

## 참고
- docs/research/agy.md(11 결과)
- spec §7 headless 명령
- docs/ORIGINS.md 실패 13(codex sandbox 빈틈)
