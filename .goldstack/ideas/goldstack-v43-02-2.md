---
date: "2026-11-16"
severity: "medium"
source: "goldstack-v43 리뷰 02"
status: "open"
feature: ""
---
아직 flaky 재검증을 사용하지 않았어도 수리 뒤 검증과 끊김 뒤 검증을 무조건 제외하여, 완료 조건을 만족하는 실패를 수리하거나 새 시도로 보낸다.

위치: src/gs/go.py:2815
근거: 티켓 15행의 조건에는 수리 이력이나 끊김 재검증 이력에 따른 제외가 없고, 재적용 금지는 'flaky 다시 검증의 결과'에 명시돼 있다. 구현은 `if not res.triaged or a.repair or _again(r, a.t.id): return ()`로 두 경우를 모두 제외한다. ReviewRepro.test_first_flaky_after_repair에서 일반 실패→수리→test_a 판별 통과→전체 test_a 재실패를 재현하자 flaky 재검증 없이 attempts=2, failures=1이 됐다. BoundaryRepro.test_first_flaky_after_interruption에서도 최초 끊김 이후 같은 조건을 만족했지만 repairs=1, worker_calls=['01','01']로 불필요한 수리가 실행됐다.
판단: 수리 뒤 검증과 끊김 재검증의 결과를 빼는 것은 docstring에 이유(끊김→flaky→끊김 무한 반복 방지, 수리 뒤 실패는 시도 실패)를 적은 설계 선택이고, 티켓·spec(결정 3-1의 '끊김 다시 검증의 일반 실패는 수리')에 비춰 이 두 경우에 flaky 분기를 적용해야 하는지 기대 동작을 판단할 수 없다.
보고서: .goldstack/work/goldstack-v43/report.md
