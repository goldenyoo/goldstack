---
id: "02"
title: "병합된 티켓 worktree·브랜치 정리"
blocked_by: ["01"]
model: codex
reviewer: claude
---
## 목표
integration에 병합된 티켓의 worktree와 로컬 티켓 브랜치를 `gs go`가 스스로 지운다. 미커밋 변경이 남은 것과 실패 worktree는 남긴다.

## 완료 조건
- 티켓이 integration에 병합되면 바로 그 티켓의 worktree(`run/wt/NN` 또는 `NN-retry-k`)와 로컬 브랜치가 사라지고, 출력에 `[NN] worktree 정리: <경로>` 줄이 보인다(시험: 가짜 worker로 `gs go` 뒤 `git worktree list`와 `git branch`에 그 티켓이 없다).
- 브랜치는 끝이 integration에 포함될 때만(`merge-base --is-ancestor`) 지운다. 아니면 브랜치를 남기고 경고한다.
- 병합 때 worktree에 미커밋 변경이 있으면 worktree·브랜치를 남기고 state `kept_worktrees`에 적으며, report.md 티켓 결과에 `남긴 worktree: <경로> (미커밋 변경)`이 나온다(시험).
- 실패한 시도의 worktree(`failed_worktrees`)는 같은 티켓의 재시도가 병합돼도 남는다(시험: 첫 시도 실패 → 재시도 병합 뒤 `run/wt/NN`은 있고 `NN-retry-1`은 없다).
- `gs go`를 시작할 때 이미 merged인데 worktree나 브랜치가 남은 티켓(병합 직후 gs가 죽은 경우)도 같은 규칙으로 정리한다(시험: 병합 뒤 정리 전 상태를 만들어 다시 실행).
- 지우기가 실패해도 경고만 하고 티켓은 merged, `gs go` 결과는 바뀌지 않는다(시험).
- integration worktree와 로컬·원격 integration 브랜치는 그대로다. 기존 시험이 모두 통과한다.
- README의 실행 흔적·실패 처리 설명에 정리 규칙이 들어간다.

## 범위 밖
- 실패 worktree 정리(`.out-of-scope/failed-worktree-cleanup.md`)
- integration worktree·브랜치 정리(`.out-of-scope/integration-cleanup.md`)
- goldstack-v0에 이미 남은 worktree(grill 세션이 손으로 지운다, spec 1-10)

## 참고
- spec §3(1-6–1-9), §4 "정리", §6
- 병합 커밋을 만드는 곳: `src/gs/go.py` `_finish`, 시작 처리 `_begin`. 보고서 `src/gs/report.py`, 상태 `src/gs/state.py`
