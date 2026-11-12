---
id: "02"
title: "판별이 실패로 끝난 검증은 다시 돌리지 않는다"
blocked_by: []
touches: ["src/gs/verify.py", "tests/test_verify_rerun.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
판별(`[verify]`)이 실패한 파일을 따로 돌려서도 실패해 결정적 실패로 가렸으면, `verify_retries`로 같은 전체 검증을 한 번 더 돌리지 않고 바로 실패로 돌려준다(spec 1-5, 아이디어 `verify-retry-skip-deterministic`).

## 완료 조건
- `verify.run`: 판별에서 따로 돌린 시험 파일이 시간 안에 신호 없이 실패 종료한 시도(결정적 실패)는 `verify_retries`가 남아 있어도 재시도하지 않고 그 시도의 결과를 돌려준다. 로그는 `판별 실패: <파일>. 전체 검증은 다시 돌리지 않는다` 뒤에 `검증 재시도 N` 줄이 없다.
- 판별을 하지 못한 경우(전체 검증의 시간 초과·끊김, 매치 없음, `max_files` 초과, 값 오류, 확인 함수 없음)와, 판별에서 따로 돌린 파일이 시간 초과(판별 시간 예산 소진 포함)나 끊김(`verify.Result.interrupted`와 같은 판정)으로 끝난 경우, 판별이 꺼진 경우는 지금처럼 `verify_retries`만큼 재시도한다. 판별 통과 뒤 전체가 다시 실패한 경우도 지금처럼이다. 트리가 바뀐 경우는 지금처럼 재시도하지 않는다(`검증 재시도 안 함`).
- `Result.retries`와 측정 표본(`metrics.triage`)이 바뀐 동작과 맞는다(재시도하지 않았으면 retries 0).
- `tests/test_verify_rerun.py`(실제 시간에 기대지 않음): 판별 실패 + `verify_retries: 1` → 전체 명령이 한 번만 돈다. 매치 없음 + `verify_retries: 1` → 두 번 돈다. 판별 파일 시간 초과 + `verify_retries: 1` → 두 번 돈다. 판별 통과 뒤 전체 실패 + `verify_retries: 1` → 지금 횟수 그대로. 첫 시험은 고치기 전 코드에서 실패한다.
- `verify.py` 머리말의 "verify_retries와 함께 쓰면" 문단과 `run` docstring을 고친다.

## 범위 밖
- `docs/guide.md`의 "`verify_retries`와의 관계"는 08
- 수리로 넘기는 쪽(`go.py`)은 바꾸지 않는다. 실패 결과를 받으면 지금처럼 수리로 간다

## 참고
- spec §3 1-5, §6 verify 줄
- `.goldstack/ideas/verify-retry-skip-deterministic.md`
