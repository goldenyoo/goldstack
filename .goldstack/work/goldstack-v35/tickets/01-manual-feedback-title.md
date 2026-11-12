---
id: "01"
title: "수동 피드백 issue 제목을 본문 첫 줄로"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_manual_title.py"]
closes: [61]
tier: small
model: codex
reviewer: claude
---
## 목표
`gs feedback --body-file`(사람이 쓴 피드백)으로 만든 issue 제목이 본문 내용을 보이게 한다(spec 2-1).

## 완료 조건
- `feedback.record_manual`이 쓰는 초안의 제목이 `[field] <제목> (gs <ver>)`이다. `<제목>`은 본문의 첫 `# ` 줄에서 `# `를 뗀 글이고, 그런 줄이 없으면 비어 있지 않은 첫 줄이다. 앞뒤 공백을 지우고 80자에서 자른다(자르면 끝에 `…`).
- 제목은 가리지 않는다. 본문(`## 사람이 쓴 피드백` 아래)과 같은 기준으로 사람이 쓴 글을 원문으로 쓴다(spec 2-1, 라운드 4). `redactor_for`(허용 낱말 밖을 지움)를 제목에 쓰지 않는다. 줄바꿈·제어 문자는 제목에 들어가지 않는다.
- 지문 계산, 라벨(`field-report`, `feedback`, `gs-<ver>`), 같은 issue 찾기(본문 줄 대조)는 바뀌지 않는다. 자동 수집(`compose`를 부르는 다른 경로)의 제목은 그대로다.
- `tests/test_feedback_manual_title.py`(`support`를 import한다): 첫 줄이 다른 두 수동 피드백이 서로 다른 제목을 갖는다, `# ` 없는 본문은 첫 비어 있지 않은 줄을 쓴다, 81자 이상은 잘린다, 한국어 낱말이 든 첫 줄이 그대로 제목에 나온다(가림으로 지워지지 않는다), 자동 수집 제목은 `[field] <phase>: <kind> (gs <ver>)` 그대로다. 첫 시험은 고치기 전 코드에서 실패한다.

## 범위 밖
- 이미 열린 issue(#59–#66)의 제목 고치기
- 문서는 08

## 참고
- spec §3 2-1, §6 #61 줄
- issue #61
