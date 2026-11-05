---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 02"
status: "open"
feature: ""
---
완료 후 '이미 끝남' 경로에서 발생한 issue 처리 실패는 보고서에 기록되지 않는다. 재시도가 성공해도 기존 보고서의 실패 기록은 그대로 남는다.

위치: src/gs/go.py:180
근거: 완료 조건: 'gh 호출이 실패해도 병합과 실행 결과는 바뀌지 않고 보고서에 남는다.' 이 분기는 `finish.sync_issues(r)`와 정리만 수행하며 보고서를 갱신하지 않는다. `.venv/bin/python -B -c`로 완료된 Run과 `_finished_after_clean=True`를 구성하고 gh에 OSError를 주입해 실제 `go.go`·`sync_issues`를 실행했다. 결과는 'go exit: 0', issue 기록의 'ok: False', 'report.write calls: 0 finish._update calls: 0'였다. 실패 문구는 state에만 추가되고 report.md에는 반영되지 않는다.
판단: '이미 끝남' 경로에서 report.md가 갱신되지 않는 것은 코드로 확인했지만 첫 마무리의 실패는 보고서에 남아 완료 조건 위반인지 애매하고, 고치려면 끝난 실행이 보고서를 다시 써서 base에 넣어야 해 '지난 시도 뒤 재시도 없음'(spec 2-6) 및 base판과 맞추는 설계와 부딪혀 더 위험하다.
보고서: .goldstack/work/goldstack-v15/report.md
