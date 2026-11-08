---
id: "01"
title: "재현된 결함은 애매하거나 범위 밖이어도 고치고, 고칠 수 없으면 defer로 남긴다"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/report.py", "src/gs/findings.py", "tests/test_judge_scope.py", "tests/test_findings_ideas.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
리뷰어가 실행으로 재현한 결함이 "애매하다"·"티켓 범위 밖"이라는 이유만으로 보고만으로 떨어지지 않게 한다.

## 완료 조건
- 판단 기준(`judge_prompt`)이 바뀐다: 리뷰어가 명령을 실행해 재현한 근거가 있는 결함은 애매해도 fix다. 단 티켓 완료 조건이나 spec이 그 동작을 명시적으로 요구하면 report다. "애매하면 report"는 재현 근거가 없는 지적에만 적용된다.
- gs가 판단 모델에 "고치지 못하는 파일" 목록을 넘긴다: 이 feature에서 아직 병합되지 않은 다른 티켓(대기·진행 중)의 `touches`. 결함 위치가 이 목록 밖이면 이 티켓 `touches` 밖이어도 fix다(예: 앞 티켓이 이미 병합한 파일).
- 재현된 결함인데 위치가 "고치지 못하는 파일"에 있으면 새 판정 `defer`다. 판단 모델이 그 밖의 값을 내면 지금처럼 report로 읽는다. 옛 state의 지적(`defer` 없음)은 그대로 읽힌다.
- `defer` 지적은 보고서의 "재현된 미수리 결함" 절에 따로 보이고, 원래 심각도와 상관없이 high 아이디어 파일로 남는다. 남은 high 집계에 들어간다.
- 수정 worker brief(`fix_brief`)는 `touches` 밖 파일을 고치는 지적이면 그 사실을 알린다.
- 시험 `tests/test_judge_scope.py`: 판단 프롬프트에 고치지 못하는 파일 목록이 들어간다(미병합 티켓의 touches만, 병합된 티켓 것은 빠진다). `defer` 판정이 보고서 절과 high 아이디어 파일로 간다. 모르는 판정은 report다. 각 동작을 지우면 실패한다.
- `review.py`·`go.py` 머리말과 docstring에 새 기준과 `defer`를 적는다.

## 범위 밖
- feature 끝 후속 수리 티켓(`.goldstack/out-of-scope/followup-repair-ticket.md`)
- 사용자 문서(05)

## 참고
- spec §3 1-3·1-4, §6
- 아이디어 `fix-outside-ticket-scope`
