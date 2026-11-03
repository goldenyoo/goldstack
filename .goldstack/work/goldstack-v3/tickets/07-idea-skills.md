---
id: "07"
title: "skill: /idea 새로, /retro <feature>, /grill·/go 고치기"
blocked_by: ["06"]
model: claude
reviewer: codex
---
## 목표
아이디어가 실행 기록(`/retro`)이나 대화(`/idea`)에서 아이디어 함으로 들어가고, 다음 `/grill`이 그것을 첫 라운드에 묻는 고리를 skill로 잇는다.

## 완료 조건
- `skills/idea/SKILL.md` (사람이 부르는 skill, `disable-model-invocation: true`): spec 2-4대로. 열린 아이디어에서 비슷한 것을 먼저 찾고(`gs backlog`와 파일 읽기), 있으면 덧붙일지 묻고, 없으면 §4 형식 파일을 쓰고 경로와 frontmatter를 한 줄로 보인다. 커밋하지 않는다.
- `skills/retro/SKILL.md`: spec 1-9대로. 인자가 `.goldstack/work/`의 feature 이름이면 그 feature의 report.md, `run/state.json`, `run/NN/*/{worker.log, review, fix}`(큰 로그는 끝부분과 오류 줄부터), spec grill 기록, 다른 feature의 report.md(반복 확인), `/insights` 보고서(`~/.claude/usage-data/report-*.html`, 있으면)를 읽는다. `run/`이 없으면(다른 머신에서 돌린 feature) report.md만으로 하고 그 사실을 말한다. 반복된 실패는 [반복] 표시. 제안만 하고, 고른 후보는 `/idea` 형식으로 쓴다. 인자가 feature가 아니면 지금 동작(세션) 그대로. matt 원본 표기는 유지.
- `skills/grill/SKILL.md`: 1단계에서 `gs backlog`를 돌리고, 라운드 1의 첫 질문을 "이번 feature에 넣을 후보"(번호 여러 개)로 한다. 확정 뒤 고른 아이디어를 `status: taken`, `feature: <이름>`으로 바꾼다. 6단계 커밋 경로에 `.goldstack/ideas`를 더한다.
- `skills/go/SKILL.md` 2단계 커밋 경로에 `.goldstack/ideas`를 더한다.
- `tests/test_skills.py`(있는 skill 검사)가 새 skill을 포함해 통과하고 `claude plugin validate .`가 통과한다.

## 범위 밖
- `gs backlog` 코드: 06
- README·guide의 skill 설명: 08

## 참고
- spec §3 1-9, 1-11, 2-4, 2-5, §4 아이디어 파일, §6 `/insights`·실행 기록 위치
- skill 문장은 `skills/writing-for-agents/SKILL.md` 기준
