---
id: "02"
title: "끝난 실행에 새 티켓이 병합되는 순간 완료 상태를 무효화한다"
blocked_by: []
touches: ["src/gs/go.py", "tests/test_only_no_merge.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
끝난 실행에 티켓을 추가하고 integration에 병합한 직후 중단돼도, `gs clean`이 미병합 변경을 지우거나 `gs go`가 "이미 끝남"으로 멈추지 않게 한다.

## 완료 조건
- finish phase가 `verified`·`reverted`인 실행에서 새 티켓이 integration에 병합되면, 그 티켓의 `merged` 기록과 phase 무효화가 같은 state 저장에 들어간다. 저장 뒤 어느 지점에서 죽어도 완료 상태가 남지 않는다.
- integration 커밋 뒤 state 저장 전에 죽은 경우도 같다. 재실행의 `_resume_merged`가 그 티켓을 표시로 회복할 때, 끝난 실행의 범위에 없던 티켓이면 같은 무효화를 한다.
- 무효화된 뒤 `gs clean`은 `--force` 없이 거부하고, `_finished_after_clean`은 끝난 것으로 보지 않는다. 옵션 없는 `gs go`는 새 티켓을 base까지 병합한다.
- `--only`와 옵션 없는 `gs go` 두 경로 모두 위 동작이다. outcome은 `--only`로 멈춘 경우에만 `병합하지 않음(--only)`이라고 적는다.
- 새 티켓이 없는 끝난 실행은 지금처럼 `이미 끝남`으로 끝나고 phase가 바뀌지 않는다.
- 옛 `state.json`을 읽을 수 있다. 무효화 뒤에도 `head` 등 다음 마무리가 읽는 기록은 남는다.
- `tests/test_only_no_merge.py`에 시나리오 시험이 있다: 병합 직후 중단 뒤 `--only` 재실행, 병합 직후 중단 뒤 옵션 없는 재실행, 저장 전 중단, 중단 뒤 `gs clean` 거부, 새 티켓 없는 재실행.

## 범위 밖
- `gs clean`이 base에 없는 integration 커밋을 검사하는 것(spec 1-5에서 뺌. `squash` 병합에서 잘못 거부한다).
- 재개 판단 분리(범위 밖 `finish-resume-decisions`).
- 문서(10).

## 참고
- spec §3의 1-5, `.goldstack/ideas/goldstack-v10-03-1.md`, `docs/internals.md`의 재개 흐름. `go.py`의 docstring이 이 동작을 적고 있으면 함께 고친다.
