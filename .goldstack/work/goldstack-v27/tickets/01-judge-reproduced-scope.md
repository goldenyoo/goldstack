---
id: "01"
title: "재현된 결함은 애매하거나 앞서 병합된 파일에 있어도 고치고, 고칠 수 없으면 defer로 남긴다"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/go.py", "src/gs/report.py", "src/gs/findings.py", "tests/test_judge_scope.py", "tests/test_findings_ideas.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
리뷰어가 실행으로 재현한 결함이 "애매하다"·"티켓 범위 밖"이라는 이유만으로 보고만으로 떨어지지 않게 한다.

## 완료 조건
- 판단 기준(`judge_prompt`)이 바뀐다: 리뷰어가 명령을 실행해 재현한 근거가 있고, 티켓 완료 조건·spec·기존 동작에 비춰 기대 동작이 무엇인지 말할 수 있는 결함은 애매해도 fix다. 재현된 현상이 결함인지(기대 동작) 판단할 수 없으면 report다. 티켓 완료 조건이나 spec이 그 동작을 명시적으로 요구하면 report다. "고치면 더 위험한 것은 report"와 수정 상한(티켓당 2회)은 그대로다. "애매하면 report"는 재현 근거가 없는 지적에만 적용된다.
- 이 기준은 판단 모델이 fix를 고를 수 있는 회차(첫 리뷰, 첫 재리뷰)에만 적용된다. 2차 재리뷰의 새 지적과 수리 재리뷰의 지적이 report인 지금 규칙은 그대로다.
- gs가 판단 모델에 "고칠 수 있는 파일" 목록을 넘긴다: 이 티켓의 `touches` + 이번 실행에서 이미 병합된 티켓들의 `touches`. 결함을 고치는 데 필요한 파일이 모두 이 목록 안이면 fix다(예: v24의 앞 티켓이 병합한 `streamfmt.py`). 목록 밖 파일을 고쳐야 하는 재현된 결함은 새 판정 `defer`다. 판단 모델이 그 밖의 값을 내면 지금처럼 report로 읽는다. 옛 state의 지적(`defer` 없음)은 그대로 읽힌다.
- 수정 worker brief(`fix_brief`)는 고칠 수 있는 파일 목록을 알리고 "이 밖의 파일은 고치지 않는다", 그리고 `touches` 밖을 고치면 원래 티켓의 시험도 돌리라고 적는다.
- `defer` 지적은 보고서의 "재현된 미수리 결함" 절에 따로 보이고, 원래 심각도와 상관없이 high 아이디어 파일로 남는다. 남은 high 집계에 들어간다.
- 시험 `tests/test_judge_scope.py`(실제 흐름, 판단 모델은 가짜): 판단 프롬프트의 고칠 수 있는 파일 목록에 이 티켓 touches와 병합된 티켓 touches가 있고 미병합 티켓 것만 있는 파일은 없다. 병합된 티켓 파일의 fix가 수정 worker brief까지 간다. spec이 명시한 동작은 report다. 목록 밖은 `defer`로 보고서 절과 high 아이디어 파일로 가고, medium·low `defer`도 남은 high로 센다. 모르는 판정은 report다. 각 동작을 지우면 실패한다.
- `review.py`·`go.py` 머리말과 docstring에 새 기준과 `defer`를 적는다.

## 범위 밖
- 아직 병합되지 않은 다른 티켓과 겹치지 않는 공용 파일까지 넓히는 것, feature 끝 후속 수리 티켓(`.goldstack/out-of-scope/followup-repair-ticket.md`)
- 사용자 문서(05)

## 참고
- spec §3 1-3·1-4·3-1, §6
- 아이디어 `fix-outside-ticket-scope`
