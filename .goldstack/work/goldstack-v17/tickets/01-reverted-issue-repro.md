---
id: "01"
title: "되돌린 티켓의 issue 재현 시험"
blocked_by: []
touches: ["src/gs/finish.py", "tests/test_issue_close.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
되돌린 티켓의 issue가 다음 PR의 `Closes #N`으로 다시 닫히면서 보고서는 `다시 엶`으로 남는지를 재현 시험으로 확인한다. 재현되면 고친다.

## 완료 조건
- 시험이 이 순서를 끝까지 돈다: 티켓 병합 → PR 병합으로 issue 닫힘 → 그 티켓을 base에서 되돌림 → gs가 다시 엶 → 다음 PR 병합. 끝에 issue가 열려 있고 보고서 기록과 같은지 단언한다.
- 같은 issue를 다른 티켓이 함께 `closes`한 경우도 같은 시험에 있다.
- 재현되지 않으면 `src/gs/finish.py`를 바꾸지 않고, 커밋 메시지에 재현되지 않았다고 적는다. 재현되면 `finish.py`를 고치고, 고친 코드를 되돌리면 그 시험이 실패하는 것을 worker가 직접 본다.

## 범위 밖
- 문서는 티켓 06이 맡는다.

## 참고
- spec §2, §6. 아이디어 `reverted-issue-closes-repro`. `finish._closing_lines`, `tests/test_issue_close.py`의 기존 시험을 먼저 읽는다.
