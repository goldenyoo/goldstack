---
id: "10"
title: "skill /grill, /go"
blocked_by: ["09"]
model: claude
reviewer: codex
---
## 목표
사람은 `/grill <feature>`와 `/go <feature>` 두 명령만으로 goldstack을 쓴다.

## 완료 조건
- `/grill <feature>`(사용자 호출):
  - 사실은 직접 확인하고 사람에게 묻지 않는다. 결정만 묻는다.
  - design tree를 세우고, frontier 전체를 번호 붙인 라운드로 묻는다. 질문마다 선택지, 선택지별 짧은 구체 예시, 추천과 이유를 붙인다. "yes"는 추천 전부 수락이다.
  - 라운드마다 질문·추천·확정 답을 `.work/<f>/spec.md`에 바로 기록한다.
  - 마지막 라운드에서 티켓 분해(그래프, wave, 티켓별 모델·리뷰 계열)를 확인받고, `tickets/`와 `.out-of-scope/`를 쓰고, `gs check`가 통과할 때까지 고친다.
  - AskUserQuestion 같은 미리 만든 선택 UI는 쓰지 않는다.
- `/go <feature>`(사용자 호출): `gs check` → herdr pane에서 `gs go` → 끝나면 report.md에서 세 줄 요약과 PR 링크를 보여 준다. 중간에 사람에게 묻지 않는다.
- spec 템플릿 파일이 있고 `/grill`은 그것을 가리킨다(형식을 skill 글에 다시 적지 않는다).
- skill 글은 짧다. `/grill`이 이 spec(goldstack-v0)의 grill 기록 방식과 같은 결과물을 만든다는 것을 작은 가상 feature로 한 번 시험해 그 기록을 PR에 붙인다.

## 범위 밖
- 그 밖의 사용자 호출 skill, router.

## 참고
- 이 feature의 grill 기록(spec §8): 사용자가 "옵션별 차이를 예시와 함께"를 요청함
- docs/research/mattpocock-skills.md §6(grilling), §10(writing-for-agents)
