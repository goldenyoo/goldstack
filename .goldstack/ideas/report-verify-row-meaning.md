---
date: "2026-11-05"
severity: "medium"
source: "/retro goldstack-v11"
status: "taken"
feature: "goldstack-v14"
---
보고서 검증 표의 SHA와 시도 번호가 티켓 코드와 티켓 시도를 뜻하지 않아, 요약 모델이 틀린 추론을 적는다.

**근거(goldstack-v11 report.md)**:
- 재실행 보고서가 "09는 같은 SHA `2064f3b`에서 전체 검증이 실패한 뒤 통과했다"며 불안정한 시험 가능성을 적었다. `2064f3b`는 integration 끝(`Merge remote-tracking branch 'origin/main'`)이다. 3차는 `grill` 451단어로 실제 실패했고 4차는 다른 코드로 통과했다.
- `ticket-09/1`처럼 `/1`이 티켓 시도 번호처럼 보이지만 09의 네 시도가 모두 `/1`이다.
- 최종 보고서는 "티켓 09 검증이 세 번 실패했지만 입력 자료에는 그 원인이 없다"고 적었다. 원인은 `run/09/*/verify.log`에 있다.

**제안**: `metrics.validation`에 티켓 시도와 티켓 head를 더하고 표 열 이름을 뜻에 맞춘다. 보고서 판단 입력(`report-input.md`)에 실패한 시험 줄을 넣는다. `metrics.py`·`docs/internals.md`도 함께 고친다.
