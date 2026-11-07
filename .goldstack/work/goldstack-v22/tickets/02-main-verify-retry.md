---
id: "02"
title: "코드가 같으면 revert 전에 main 검증을 한 번 더 돌린다"
blocked_by: ["01"]
touches: ["src/gs/finish.py", "src/gs/revert_decision.py", "tests/test_revert_decision.py", "tests/test_finish_stages.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
검증을 통과한 트리와 코드가 같은 병합이 flaky 시험 한 번으로 revert되는 일을 막는다.

## 완료 조건
- main 검증이 실패하고, 마지막으로 통과한 integration 커밋과 병합 커밋의 차이가 `.goldstack/`뿐이면 revert 전에 같은 worktree 준비 절차로 1회 다시 검증한다. 로그는 `main-retry` 라벨로 남는다.
- 재검증이 통과하면 phase는 `verified`이고 `outcome`에 `flaky: main 재시도 1번 만에 통과`가 들어간다. 재검증도 실패하면 지금처럼 revert한다.
- 차이에 `.goldstack/` 밖 파일이 있으면 재검증 없이 지금처럼 revert한다.
- 판단은 `revert_decision.next_step`에 넣고 표 시험(`tests/test_revert_decision.py`)으로 위 세 경우를 확인한다. 재검증 도중 gs가 죽어도 다음 `gs go`가 revert를 중복하지 않고 이어 가며, 이 경우도 시험한다.
- 옛 state(새 필드 없음)를 읽을 수 있다.

## 범위 밖
- 코드가 달라도 다시 돌리기(결정 2-2)
- `verify_retries` 의미 변경
- flaky 시험 자체의 수정

## 참고
- spec §3 2-2
- 아이디어 `main-verify-retry-before-revert`
