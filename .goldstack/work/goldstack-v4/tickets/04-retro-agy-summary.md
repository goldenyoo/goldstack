---
id: "04"
title: "/retro의 큰 로그를 Gemini가 요약"
blocked_by: []
model: claude
reviewer: codex
---
## 목표
`/retro <feature>`가 worker 로그가 클 때 긴 문맥에 강한 Gemini(agy)에게 요약을 맡기고, Claude는 요약으로 후보를 정한다.

## 완료 조건
- `skills/retro/SKILL.md`: feature 회고에서 읽을 `run/NN/*/worker.log` 합계가 200KB 이상이면 `agy -p --sandbox`(읽기 전용)로 로그 요약을 맡긴다. 요약에 넣을 것: 티켓·시도별 실패 이유, 재시도 횟수, 리뷰 지적의 반복, 오래 걸린 단계. 부르기 전에 "agy로 로그 N개 요약(한도 1회, gs 상한에는 안 셈)"을 한 줄로 알린다.
- agy가 없거나(명령 없음) 실패하면 Claude가 로그마다 끝부분과 오류 줄만 읽는 지금 방식으로 간다고 적는다.
- 모델은 `gs config models.agy`로 읽는다(하드코딩 없음).
- `tests/test_skills.py`와 `claude plugin validate .` 통과.

## 범위 밖
- gs가 세는 agy 상한: 02·03
- 세션 회고(인자가 feature가 아닐 때)는 그대로

## 참고
- spec §3 2-6, 아이디어 `.goldstack/ideas/agy-gemini-usage.md`. touches: `skills/retro/**`
