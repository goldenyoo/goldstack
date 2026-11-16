---
id: "02"
title: "base 재검증(main-retry)을 지운다: base 검증이 실패하면 코드가 같아도 되돌린다"
blocked_by: []
touches: ["src/gs/finish.py", "src/gs/revert_decision.py", "src/gs/report.py", "src/gs/verify.py", "tests/test_revert_decision.py", "tests/test_finish_stages.py", "tests/test_postmerge_skip.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
goldstack-v22 02가 더한 base 재검증을 지운다. 병합 뒤 base 검증이 처음 실패했을 때, 코드가 integration에서 통과한 것과 같으면 revert 전에 한 번 더 돌리던 단계다. 남은 실행 기록에서 한 번도 돌지 않았다(spec §6). base 검증에는 판별과 `verify_retries`가 그대로 남는다.

## 완료 조건
- `revert_decision.next_step`이 재시도를 답하지 않는다: `MARK_RETRY`, `RETRY_MAIN`, `KEEP_RETRY`, `RECORD_FLAKY`, `Facts.code_same`이 사라진다. base 검증이 실패하면 코드가 같든 다르든 지금 "코드가 다른 첫 실패"와 같은 단계를 답한다.
- `finish.py`에서 `_code_same`, phase `main_retry`를 쓰는 곳, `main-retry` 검증 라벨, `_postmerge`가 처음부터 한 번 더 읽는 분기가 사라진다. `_same_as_verified`(통과한 코드 그대로면 base 검증을 건너뜀)는 그대로다.
- `report.py`가 phase `main_retry`와 `main-retry-verify.log`를 따로 다루지 않는다. `verify.py` 머리말의 `main-retry` 언급을 지운다.
- 옛 state, 시험으로: phase가 `main_retry`인 state(0.2.26 이하가 남긴 값)는 `main_failed`로 바꿔 읽는다(spec 결정 2-2). 그 뒤의 판단은 `main_failed`와 같고 `next_step`에 `main_retry` 전용 분기는 없다. 재개 판정(`RESUME_PHASES`)은 이 phase를 계속 마무리 재개로 본다. 시험 하나(`tests/test_finish_stages.py`): base가 그대로이고 준비가 성공하면 옛 state의 `main_retry`가 다시 검증 없이 revert 길로 간다.
- 확인 명령(리뷰어가 다시 돌린다): `grep -rnE 'MARK_RETRY|RETRY_MAIN|KEEP_RETRY|RECORD_FLAKY|code_same|main-retry' src tests`가 아무 줄도 내지 않는다. `grep -rn 'main_retry' src`는 `finish.py`의 옛 state 읽기(재개 판정 목록과 `main_failed`로 바꿔 읽는 자리)만 낸다.
- 새 동작의 시험 하나: 코드가 같은(`.goldstack/`만 다른) base 검증 실패가 다시 검증 없이 revert로 간다. 재시도 분기를 되살리면 실패해야 한다. 재시도를 보던 기존 시험은 지우거나 이 동작으로 고친다.
- 마무리의 나머지 흐름을 보는 기존 시험(base 검증 건너뜀, 보호된 base, revert PR, 승인 대기 중 재검증 `main-recheck`)의 단언은 그대로 통과한다. 예외 하나: `tests/test_postmerge_skip.py`의 `test_other_goldstack_file_runs_verify`는 `finish._code_same`을 직접 부르는 단언만 지우고, 다른 `.goldstack/` 파일이 바뀌면 base 검증을 돈다는 단언은 남긴다.

## 범위 밖
- 승인 대기 중 base가 바뀌었을 때의 재검증(`main-recheck`). 다른 장치다. 남긴다.
- 티켓 검증 쪽의 다시 검증(01).
- 문서와 CHANGELOG(05).

## 참고
- spec §3 결정 1-2·2-2, §6.
- `docs/internals.md`의 "main 재검증 (`main-retry`)" 절이 지금 동작의 설명이다.
