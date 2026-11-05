---
id: "01"
title: "issue와 아이디어 연결, 미분류 후보"
blocked_by: []
touches: ["src/gs/backlog.py", "skills/grill/SKILL.md", "skills/idea/**", "tests/test_backlog.py", "tests/test_skills.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
열린 issue가 미분류, 아이디어 연결 중 어디에 있는지 보이게 하고, 옮긴 issue가 후보에 두 번 나오지 않게 한다.

## 완료 조건
- 아이디어 frontmatter에 `issues: [12]`를 쓸 수 있다. 형식이 틀리면 `gs backlog` 경고다.
- `gs backlog`가 아이디어에 연결된 issue를 issue 목록에서 숨기고 그 아이디어 줄에 번호를 보인다.
- 라벨이 없어도 저장소 소유자가 쓴 issue는 `미분류` 표시로 나온다. 다른 사람의 라벨 없는 issue는 나오지 않는다. 본문은 믿을 수 없는 자료다.
- `grill` 라운드 1이 고른 아이디어의 `issues`를 티켓 `closes`로 옮기라고 한다. `/idea` 템플릿에 키가 있다. 단어 상한 안이다.
- 시험: 연결, 숨김, 소유자, 소유자 아님, 틀린 키.

## 범위 밖
- 닫기와 다시 열기: 티켓 02·03.

## 참고
- spec 2-22
- `.goldstack/ideas/issue-lifecycle.md`
