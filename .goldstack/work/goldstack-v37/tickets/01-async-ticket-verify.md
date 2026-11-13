---
id: "01"
title: "티켓 검증을 루프 밖 스레드에서 돌린다"
blocked_by: []
touches: ["src/gs/go.py", "src/gs/verify.py", "tests/test_async_verify.py", "tests/support.py", "tests/test_verify_repair.py", "tests/test_setup_when.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
티켓 검증(약 10분)이 도는 동안에도 코디네이터 루프가 worker 끝, 리뷰 결과, 수정·수리 worker, 새 worker를 처리하게 한다(spec 1-2·1-3·2-1·2-2, 아이디어 `async-verify-revisit`).

## 완료 조건
- `_merge_stage`를 준비(늦은 커밋 대조, catch-up, `merge --no-ff --no-commit`, `_setup_merge`) → 호출(`_verify`의 `verify.run`) → 반영(시간 초과·실패·끊김·트리 변경·늦은 커밋·커밋)으로 나눈다. 호출만 루프 밖 스레드에서 돌고, 준비·반영·state 변경·`say`·`_phase`는 루프 스레드에서 한다(리뷰의 `Reviews`·`_review_tick`과 같은 원칙). 반영의 판정 순서와 메시지는 지금과 같다.
- `verify.run`에 취소 통로를 둔다: 취소되면 도는 명령의 프로세스 그룹을 끝내고, 판별·재시도의 다음 명령을 띄우지 않는다. 시험 seam(`go._verify`)은 유지하거나, 그것에 기대는 `tests/test_verify_repair.py`(`stop_at_verify`)·`tests/test_setup_when.py`(호출 수)를 새 경계에 맞춘다.
- 병합·검증은 한 번에 하나다. 검증 명령이 끊겨(`_verify_interrupted`) 같은 트리로 다시 검증할 때는 병합 자리를 지킨다(줄 맨 앞, 다른 티켓이 끼어들지 않는다). 검증이 도는 동안 병합 차례가 된 다른 티켓은 줄을 서고 `[<id>] 병합 대기: <검증 중 id> 검증 중`을 한 번 출력한다. 검증이 끝나 반영한 뒤 줄의 순서대로 병합한다.
- 검증이 도는 동안 integration worktree(`r.iwt`)와 `r.ihead`를 바꾸는 일(다른 티켓의 병합, `_reset_integration`, `_ticket_error`의 되돌리기, `_prepare_integration` 등)은 하지 않는다. 다른 티켓 경로가 되돌리기를 부르면 검증 반영 뒤로 미루거나, 되돌릴 것이 없으면 건너뛴다. 미룬 되돌리기를 부를 때의 옛 `r.ihead`로 재생하지 않는다(방금 통과한 병합을 지우지 않는다). 검증 반영이 이미 하는 "검증하는 동안 integration이 바뀌었다" 대조는 그대로 둔다.
- 검증 중에도: worker 끝 → 리뷰 호출, 리뷰 결과 → 수정 worker 시작, 새 티켓 worker 시작(base는 지금처럼 마지막으로 검증된 integration 끝)이 진행된다. `max_workers` 상한과 수정·수리 자리 우선 규칙은 그대로다.
- 도는 검증과 병합 줄은 루프의 미완 작업이다: 그것만 남아도 루프가 끝나지 않고, 다른 worker가 도는 동안에도 끝난 검증을 바로 반영한다(`_wait_any`를 한 번씩 보고 돌아온다).
- 네트워크 끊김 중: 도는 검증의 결과는 끊김 중에도 반영한다(검증은 로컬이다). 줄 선 병합은 지금처럼 회복까지 시작하지 않는다.
- 중단(spec 2-1): Ctrl-C·예외로 루프가 떠나면 도는 검증의 프로세스 그룹을 끝내고 스레드를 거둔다. 재개 의미는 지금 그대로다: 첫 검증 도중이었으면 다음 `gs go`가 그 티켓을 worker부터 새로 시작하고, 다시 검증(`verify_again`) 도중이었으면 다시 검증부터 잇는다. 재개 표시를 새로 만들지 않는다. 옛 state도 지금처럼 읽힌다.
- `NetworkAbort`(spec 2-2): 도는 검증이 있으면 끝날 때까지 기다려 결과를 반영한 뒤 떠난다(`■ 중단(네트워크): <id> 검증을 마치고 멈춘다`). 줄 선 병합은 시작하지 않는다.
- 측정(`metrics.validations`, 시도별 처리 대기·결과 대기)은 지금과 같은 값을 남긴다. 검증 중 끝난 worker의 처리 대기는 검증 시간을 포함하지 않는다.
- `tests/test_async_verify.py`(`tests/support.GoTest`의 가짜 worker·리뷰어, 검증은 파일 신호로 멈췄다 풀리는 가짜 명령. 실제 시간에 기대지 않는다):
  - 01 검증이 멈춰 있는 동안 02 worker가 끝나면 02 리뷰가 불리고 지적이 있으면 02 수정 worker가 뜬다. 01 검증이 풀리면 01이 병합된다.
  - 01 검증 중 02가 병합 차례가 되면 기다렸다가 01 반영 뒤 병합된다. 01 검증이 실패하면 02는 01 없는 integration 위에서 병합·검증된다.
  - 01 검증 중 03 worker 오류(`_ticket_error`)가 나도 01 검증이 끝까지 돌고 결과대로 반영되며, integration 브랜치에 01 병합 커밋이 남는다.
  - 검증만 남은 상태에서 루프가 끝나지 않고 병합한다. 검증이 끝났는데 다른 worker가 도는 중이면 그 worker를 기다리지 않고 병합한다.
  - 01 검증 명령이 끊기면(신호) 02가 줄에 있어도 01을 같은 트리(`tree_sha`·`ticket_head` 같음)로 다시 검증한다.
  - `verify.run` 취소: 판별·재시도 사이에 취소되면 다음 명령을 띄우지 않고 자손 프로세스가 남지 않는다.
  - 01 첫 검증 중 gs를 끊으면(시험 seam으로 예외) 검증 프로세스가 남지 않고, 다음 `gs go`가 지금처럼 01을 새로 시작한다. 다시 검증 중 끊으면 다음 `gs go`가 다시 검증부터 잇는다.
  - 01 검증 중 `NetworkAbort`가 나면 검증이 끝나 반영된 뒤 실행이 멈추고, 통과였으면 01은 merged다.
- `go.py` 머리 docstring과 `_loop`·`_merge_stage` docstring의 "병합과 검증은 이 루프 안에서 하나씩 한다(직렬)"를 새 모양으로 고친다.

## 범위 밖
- 마무리(integration·base) 검증(`finish.py`)
- 검증을 겹쳐 돌리기(파이프라인)와 검증 전용 worktree(spec 1-2의 B·C)
- 새 측정 칸(spec 1-6)

## 참고
- `src/gs/go.py` `_loop`(932행), `Reviews`(884행), `_review_tick`(1010행), `_merge_stage`(1744행), `_verify`(2882행), `_verify_interrupted`(2383행), `_reset_integration`(527행). 줄 번호는 v36 병합 전 것이다
- 범위 밖 `async-verify.md`(재개 위험이 뺀 이유였다), `.goldstack/ideas/async-verify-revisit.md`
