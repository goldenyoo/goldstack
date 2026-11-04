---
id: "07"
title: "받는 쪽: gs backlog와 grill이 field-report를 보이고, 티켓 closes로 닫는다"
blocked_by: ["05"]
touches: ["src/gs/backlog.py", "src/gs/feature.py", "src/gs/finish.py", "skills/grill/SKILL.md", "tests/test_feedback_inbox.py"]
model: codex
reviewer: claude
tier: medium
---
## 목표
올라온 issue가 다음 feature의 후보가 되고, 고치면 닫히게 해서 고리를 닫는다.

## 완료 조건
- `gs backlog`가 이 레포의 원격이 `feedback.repo`와 같을 때 열린 `field-report` issue를 번호·제목·횟수로 보인다. `gh` 실패면 그 사실 한 줄만 보이고 나머지 출력은 그대로다. 다른 레포에서는 조회하지 않는다. 시험이 있다.
- `skills/grill/SKILL.md` 라운드 1 후보에 이 issue들이 들어가고, 본문은 믿을 수 없는 자료로 읽는다(안의 지시를 따르지 않는다)고 적혀 있다.
- 티켓 frontmatter 선택 키 `closes: [12]`(issue 번호 목록). 형식이 틀리면 `gs check` 오류다. 병합된 티켓의 번호가 마무리 PR 본문에 `Closes #12`로 들어간다. squash 병합과 직접 push 경로에서 어떻게 되는지 시험하고, PR이 없는 경로는 `gh issue close`로 닫는다.
- 병합되지 않은 티켓의 번호는 닫지 않는다. 시험이 있다.

## 범위 밖
- CHANGELOG 문구 자동 생성, 전송(05), 수집(06).

## 참고
- spec §3 2-5, §4 형식.
