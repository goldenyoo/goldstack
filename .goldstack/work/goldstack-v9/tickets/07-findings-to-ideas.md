---
id: "07"
title: "보고만 지적(high·medium)을 ideas로, 보고서 커밋에 함께"
blocked_by: []
touches: ["src/gs/findings.py", "src/gs/finish.py", "tests/test_findings_ideas.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
고치지 않기로 한 리뷰 지적이 보고서에 묻히지 않고 `gs backlog`와 다음 grill의 후보로 보이게 한다.

## 완료 조건
- 마무리가 보고서를 쓸 때 상태가 "보고만"인 high·medium 지적마다 spec §4 형식의 `.goldstack/ideas/` 파일을 만든다. low는 보고서에만 남는다.
- 그 파일들이 보고서 커밋에 함께 들어가 main에 올라간다. 직접 push 경로와 보호된 base의 보고서 PR 경로를 모두 시험한다.
- 보고서와 아이디어 파일만 다르면 `_verify_final`이 최종 검증을 지금처럼 건너뛴다.
- 재개나 다시 쓰기로 같은 지적이 두 번 생기지 않는다. 이미 있는 파일은 덮어쓰지 않아 `taken`·`dropped`와 사람이 고친 내용이 남는다. 시험이 있다.
- 파일이 `gs backlog`에 경고 없이 나온다. 시험이 있다.
- 파일을 쓰지 못해도 마무리 결과가 바뀌지 않고 경고만 남는다. 시험이 있다.
- 옛 `state.json`을 읽어도 깨지지 않는다.

## 범위 밖
- low 지적(`.goldstack/out-of-scope/findings-low-to-ideas.md`).
- 미해결·수정 못 함·확인 못 함 지적. 이번 결정은 보고만 지적이다.
- `field-report` issue로 올리기. v8 결정대로 리뷰 지적은 올리지 않는다.

## 참고
- spec §3 1-8, §4. 아이디어 `.goldstack/ideas/report-findings-to-ideas.md`. 지적 상태 표시는 `report.finding_status`를 쓴다.
- 시작 전에 v8이 병합한 `finish.py`를 읽는다.
