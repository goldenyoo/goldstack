---
id: "01"
title: "flaky 다시 검증을 지운다: 판별 통과 파일이 전체에서 다시 실패하면 수리로 간다"
blocked_by: []
touches: ["src/gs/go.py", "tests/test_flaky_reverify.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
goldstack-v43 02가 더한 flaky 다시 검증을 지운다. 지난 실행 기록에서 쓰인 적이 없고 열린 결함 셋을 달고 있다(spec §6). 판별에서 따로 통과한 파일이 판별 뒤 전체 실행에서 다시 실패한 티켓 검증은 goldstack-v43 전처럼 수리 자리로 간다.

## 완료 조건
- `go.py`에서 flaky 다시 검증의 판정·실행·표시가 사라진다: `_flaky_files`, `_verify_flaky`, `_after_triage`, `_rerun_suffix`, `_test_suffix`, `_wanted`, `_in_diff`, `_flaky_marked`, `AGAIN_FLAKY`, `FLAKY_AGAIN`, `Active.flaky_used`, 재개 표시의 `flaky_files`·`flaky_used`, `_mark_resume`의 `flaky` 인자. 이것들을 설명하던 머리말·docstring 문장도 함께 지운다.
- 확인 명령(리뷰어가 다시 돌린다): `grep -rnwE '_flaky_files|_verify_flaky|_flaky_marked|flaky_used|flaky_files|AGAIN_FLAKY|FLAKY_AGAIN|_after_triage|_rerun_suffix|_test_suffix|_in_diff' src tests --include='*.py'`가 아무 줄도 내지 않는다. `-w`(낱말 단위)가 있어야 한다: 남기는 판별 시험 `test_pass_on_a_retry_after_triage_…`는 걸리지 않는다.
- `tests/test_flaky_reverify.py`를 지운다. 지울 이름을 쓰는 시험 파일은 이것뿐이다.
- 남는 동작, 시험으로: 판별 통과 뒤 전체 실행이 다시 실패한 티켓 검증(끊김·시간 초과 아님)은 수리 worker 자리로 간다(`_verify_failed`). 이 경우를 보는 시험이 이미 있으면 그대로 두고, 없으면 `tests/test_verify_repair.py`에 하나 둔다. 시험은 병합 단계가 수리로 가지 않고 같은 트리를 다시 검증하면 실패해야 한다.
- 옛 state, 시험으로: 재개 표시의 `verify_again`이 `"flaky"`(0.2.26이 남긴 값)면 끊김의 다시 검증과 같게 읽어 같은 트리로 한 번 다시 검증한다(`_again_of`가 모르는 값을 끊김으로 읽는 지금 규칙). `flaky_files`·`flaky_used` 키는 읽지 않는다. `tests/test_verify_repair.py`의 재개 시험에 이 경우 하나를 둔다.
- 끊김의 다시 검증(`_verify_interrupted`), 판별, `verify_retries`의 동작은 그대로다. 이들을 보는 기존 시험이 고치지 않고 통과한다.

## 범위 밖
- 판별(`verify._triage`, config `[verify]`)과 보고서 flaky 줄(`report.flaky_lines`). 남긴다(spec 결정 1-2).
- 문서와 CHANGELOG(05).

## 참고
- spec §3 결정 1-2·2-1, §6(쓰인 횟수와 삭제 후보의 자리).
- goldstack-v43 spec 결정 1-2·2-1·3-1: 이 장치를 넣은 결정이다.
