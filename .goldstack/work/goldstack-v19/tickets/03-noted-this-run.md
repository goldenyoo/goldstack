---
id: "03"
title: "_noted는 이번 실행에서 처리한 예외로 판단"
blocked_by: []
touches: ["src/gs/finish.py", "tests/test_finish_noted.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
재개에서 같은 글자의 오류가 나도 마무리 결과가 옛 문구로 남지 않게 한다.

## 완료 조건
- `_noted`가 글자 비교 대신 이번 `finish.run`에서 `_note_failure`가 처리한 예외인지 원인 사슬에서 본다. 뒤따른 보고서 갱신 실패가 원인을 덮지 않는 지금 동작은 유지한다.
- 시험: 재개 때 `finish.error`에 같은 글자가 남아 있고 `outcome`이 비실패 문구면 `outcome`이 `마무리 실패: …`로 바뀐다. `finish_errors`는 중복되지 않는다. 고친 코드를 되돌리면 실패하는 것을 worker가 직접 본다.

## 범위 밖
- 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 1-4, §6. 아이디어 `goldstack-v14-06-4`.
