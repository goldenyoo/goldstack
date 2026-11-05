---
id: "02"
title: "issue 닫기 구멍, 고친 버전, revert 뒤 다시 열기"
blocked_by: []
touches: ["src/gs/finish.py", "tests/test_issue_close.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
issue 닫기가 실제 반영과 맞게 한다.

## 완료 조건
- PR 없이 base에 반영된 티켓의 `closes` issue가 앞 PR이 있어도 닫힌다.
- base에서 되돌린 티켓의 issue는 닫지 않는다. 이미 닫혔으면 다시 연다.
- 닫을 때 고정 문구(`<버전>에서 고침`, 커밋)로 댓글을 남긴다. 다른 레포의 내용이나 리뷰 본문을 댓글에 넣지 않는다.
- not planned 닫기는 자동으로 하지 않는다. 사람이 치는 명령으로만 한다.
- gh 호출이 실패해도 병합과 실행 결과는 바뀌지 않고 보고서에 남는다. 재개 때 같은 댓글을 두 번 달지 않는다.
- 시험: 앞 PR 뒤 직접 반영, revert, 다시 열기, gh 실패, 재개.

## 범위 밖
- 재발 확인: 티켓 03.

## 참고
- spec 2-20
- `.goldstack/ideas/issue-close-revert-gaps.md`
- `finish._closing_numbers`, `finish._close_without_pr`
