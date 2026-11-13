---
id: "03"
title: "병합 줄에서 기다린 시간을 `병합 대기` 단계로 남긴다"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/state.py", "src/gs/metrics.py", "tests/test_merge_wait_phase.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
다른 티켓의 검증이 끝나기를 기다린 시간이 앞 단계(재리뷰 등)의 소요로 잡히지 않고, 보고서·진행 바·`gs status`에 `병합 대기`로 따로 보이게 한다(spec 결정 2-3, 아이디어 merge-queue-wait-phase).

## 완료 조건
- `go._merge`가 티켓을 병합 줄에 세울 때 그 티켓에 새 단계 `merge_wait`를 연다(`_wait_phase`). `merge_wait`는 그 티켓의 다음 단계가 시작할 때 닫힌다: 보통 `verify`, 늦은 커밋이면 재리뷰. 줄에서 나온 뒤 다음 단계까지의 준비 시간(HEAD 조회 등, 초 단위)은 `merge_wait`에 든다. 바로 병합할 수 있으면(줄을 서지 않으면) `merge_wait` 단계가 생기지 않는다.
- `state.PHASE_LABELS`에 `"merge_wait": "병합 대기"`를 `verify` 바로 앞에 둔다(보고서 단계 순서가 이 사전 순서다). 보고서의 `단계별 소요` 줄에 `병합 대기 N분`이 나온다. 0분으로 반올림되는 단계를 빼는 지금 규칙은 그대로다.
- 옛 state(이 단계가 없는 기록)를 그대로 읽는다.
- `tests/test_merge_wait_phase.py`(새 파일): 가짜 worker 두 티켓에서 둘째 티켓이 첫째 검증 중에 줄을 서면 (1) 둘째 티켓 phases에서 `merge_wait`가 앞 단계(재리뷰 또는 리뷰) 바로 뒤, `verify` 바로 앞에 있다, (2) 줄을 서지 않은 첫째 티켓에는 `merge_wait`가 없다, (3) phases에 시각을 직접 넣은 state(예: `merge_wait` 5분)로 만든 보고서의 단계별 소요 줄에 `병합 대기 5분`이 `검증` 앞에 나온다. (1)은 `_wait_phase` 호출을 지우면 실패한다.
- `go.py`·`metrics.py`의 단계 설명 docstring(`review_wait`·`fix_wait`·`repair_wait`를 나열한 곳)에 `merge_wait`를 더한다.
- 시험은 실제 시간에 기대지 않는다. 대기 순서는 가짜 검증 명령의 파일 신호로 만든다.

## 범위 밖
- 검증 자리 수·순서 변경(범위 밖 verify-pipeline)
- git 호출 줄이기(04)

## 참고
- spec §3 결정 2-3, `docs/internals.md`의 병합 줄 설명
