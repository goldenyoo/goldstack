---
id: "01"
title: "마무리: 이미 전체 검증한 트리면 integration 검증을 건너뛴다"
blocked_by: []
touches: ["src/gs/finish.py", "src/gs/report.py", "tests/test_finish_skip_verify.py", "tests/support.py", "tests/test_clean.py", "tests/test_final_report_on_base.py", "tests/test_go_execution.py", "tests/test_go_finish.py", "tests/test_metrics.py", "tests/test_setup.py", "tests/test_squash.py", "tests/test_ticket_verify.py", "tests/test_verify_modes.py", "tests/test_verify_repair.py", "tests/test_verify_rerun.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
마무리의 integration 전체 검증이 이번 실행에서 이미 전체 검증을 통과한 트리를 다시 돌지 않게 한다. 지난 22번 실행에서 이 검증은 매번 403–640초가 걸려 일렬 경로 끝에 붙었고, 실패한 적은 없다.

## 완료 조건
- `finish._run`이 `integration` 검증을 돌리기 전에 판정한다. 근거는 `state.json` `metrics.validations` 중 받아들여진(`accepted`) 티켓 검증 기록의 `tree_sha`다. 기록의 순서나 라벨이 아니라 **트리 일치**로 커밋과 잇는다. integration HEAD에서 첫 부모(first-parent)를 따라 거슬러 가며 커밋 C마다 본다:
  1. C의 트리와 같은 `tree_sha`를 가진 받아들여진 전체 검증(spec `verify`로 돈 기록)이 있으면 건너뛴다.
  2. 없고, C의 트리와 같은 `tree_sha`를 가진 받아들여진 좁은 검증(`verify_for(t)`가 spec `verify`와 다름)이 있으면, C와 그 첫 부모의 차이가 모두 그 티켓의 touches(glob 허용) 안인지 본다. 안이면 첫 부모로 가서 다시 본다. 밖이면 검증한다.
  3. 어느 쪽도 아니면(예: base 합치기, revert 복원, 검증 기록이 없는 커밋) 검증한다.
- 그래서 검증을 통과했지만 늦은 커밋 등으로 병합이 취소된 기록, 수리·끊김·재시도 라벨, setup을 다시 돌린 병합(분리 HEAD 커밋)도 트리로만 판정된다. 지난 실행 23개에 이 규칙을 대 보면 전체 티켓 검증이 없는 v29만 검증하고 22개는 건너뛴다(spec §6).
- 다음 경우에는 지금처럼 검증을 돌린다. 각각 시험한다: 기록이 없을 때(옛 state, `tree_sha`가 빈 기록 포함), integration worktree가 깨끗하지 않을 때, 좁은 검증 커밋의 차이에 touches 밖 파일이 있을 때, 전체 검증 뒤에 검증 기록과 맞지 않는 커밋(base 합치기 등)이 끼었을 때, 검증은 받아들여졌지만 병합이 취소되어 그 트리가 integration 이력에 없을 때.
- 건너뛰면 `run/finish/integration-verify.log`에 근거 한 줄을 쓴다(예: `integration: ticket-03 전체 검증 뒤 좁은 검증 티켓(05)만 바뀜, 건너뜀`, 1번에서 바로 멈췄으면 `integration: ticket-07 전체 검증과 같은 트리, 건너뜀`). 그리고 검증을 통과했을 때처럼 `verified_head`와 `integration_ok`를 남긴다. 그래서 `_verify_final`과 base 검증의 `_same_as_verified`가 지금 규칙 그대로 이어진다. 끊긴 뒤 다음 `gs go`가 마무리를 이어도 같은 판정을 한다.
- 보고서 Summary에서 마무리 줄(남은 high·건너뛴 리뷰가 붙은 그 줄) 바로 다음에 `integration 검증 건너뜀: <근거>` 한 줄을 둔다(`report.py`). flaky 줄처럼 따로 둔 줄이다. 마무리 줄 자체는 바꾸지 않는다. 그래서 그 줄 끝의 줄바꿈까지 단언하는 `tests/test_finding_status.py`는 그대로 통과한다. `tests/test_final_report_on_base.py`처럼 Summary 블록 전체를 단언하는 시험이 건너뛰는 실행이 되면, 새 줄까지 단언하도록 고친다. 보고서의 검증별 측정 표에는 건너뛴 검증의 줄을 만들지 않는다.
- 새 시험 `tests/test_finish_skip_verify.py`: 가짜 worker 실행으로 (a) 마지막 티켓이 전체 검증 → 같은 트리 건너뜀, (b) 전체 검증 뒤 좁은 검증 티켓 하나 → 건너뜀, (c) 좁은 검증 티켓이 touches 밖 파일을 바꿈 → 검증함, (d) 전체 검증 기록 없음 → 검증함, (e) 전체 검증 뒤 기록과 맞지 않는 커밋(예: base를 합친 커밋)이 낌 → 검증함, (f) 받아들여진 검증의 트리가 integration 이력에 없음(병합 취소) → 그 기록을 쓰지 않음, (g) 재개 → 같은 판정. 각각 integration 검증 명령이 불렸는지(횟수)와 로그·보고서 줄을 단언한다. 판정을 지우면 (a)(b)가 실패한다.
- 이 변경으로 깨지는 기존 시험은 grill 시제품 측정(spec §6)에서 10개 파일 12개였다. 대부분 integration 검증 실패·시간 초과·flaky·측정을 일부러 만드는 시험이다. 그 시험들이 계속 integration 검증을 거치게 한다(예: 좁은 검증 티켓 없이 integration 트리를 바꾸거나, 필요한 fixture를 `tests/support.py`에 둔다). 그 시험의 단언을 약하게 만들거나 지우지 않는다.
- `finish.py` 모듈 docstring의 마무리 검증 설명을 고친다.

## 범위 밖
- 건너뛰기를 끄는 config 키(`.goldstack/out-of-scope/finish-skip-config.md`)
- base 검증 규칙(`_same_as_verified`) 자체를 바꾸는 것
- 문서(`docs/`)는 04가 고친다

## 참고
- spec §3 결정 1-3·2-1·2-2·2-3, §6(지난 22번 실행 측정, 시제품에서 깨진 시험 목록)
- 티켓 검증은 integration의 미완 병합 트리에서 돈다(`go._verify`, `tree_sha`는 그 index 트리)
