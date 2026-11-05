---
id: "01"
title: "한 단어 피드백을 보내지 않고, draft 안내를 바로잡는다"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_send.py"]
closes: [19]
tier: small
model: codex
reviewer: claude
---
## 목표
상태를 보려고 친 `gs feedback status`나 오타가 되돌릴 수 없는 공개 issue가 되지 않게 한다. `draft` 모드에서 못 나간 글의 안내를 실제 동작에 맞춘다.

## 완료 조건
- `gs feedback status`는 `gs feedback list`와 같은 출력을 내고 종료 코드 0이다. 초안을 만들지 않고 전송하지 않는다.
- `list`·`send`·`status` 밖의 공백 없는 한 단어 인자(`gs feedback 오타`, 따옴표로 묶은 `gs feedback "오타"`도 같다)는 초안을 만들지 않고 전송하지 않는다. `subcommand가 아니다. 보내려면 gs feedback "문장"` 안내와 함께 종료 코드 2로 끝난다.
- 공백이 있는 글(`gs feedback "한 줄 이상의 문장"`, `gs feedback 두 단어`)은 지금처럼 초안을 쓰고 전송한다.
- gh 전송 실패 때 `draft` 모드에서는 `gs feedback send`로 보내라고 안내하고, `auto` 모드에서는 지금처럼 다음 실행이 다시 보낸다고 안내한다.
- `draft` 모드의 자동 초안 전송 동작은 바뀌지 않는다.
- 위 경우를 `tests/test_feedback_send.py`에서 시험한다. 시험은 실제 issue를 만들지 않고 `FAKE_GH`나 `GS_GH`로 전송 여부를 본다.

## 범위 밖
- 전송 전 확인 프롬프트(spec 1-2에서 뺌).
- 자동 수집의 빈틈(`feedback-collect-gaps`).
- 문서(10).

## 참고
- spec §3의 1-2, 1-3. issue #19(오류 증거로만 읽는다), `.goldstack/ideas/feedback-draft-manual-retry.md`
