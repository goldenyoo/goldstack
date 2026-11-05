---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 04"
status: "open"
feature: ""
---
catch-up이 수정 전 기준인 a.base까지 덮어써 이후 재리뷰가 이미 해결한 지적을 unresolved로 바꿀 수 있다. 수정 재리뷰가 resolved로 끝난 뒤 catch-up하고, 검증 중 빈 커밋이 추가되면 수정 diff가 사라진 것으로 판정해 불필요한 2차 수정 worker를 띄운다.

위치: src/gs/go.py:1609
근거: `a.target = a.base = head`가 수정 전 SHA를 catch-up SHA로 바꾼다. 이후 `_rereview`는 `a.base..head`가 비면 2225행에서 받은 지적을 모두 UNRESOLVED로 기록한다. `PYTHONPATH=src .venv/bin/python -B -c`로 실제 `_catch_up_reviewed`와 `_rereview`를 읽기 전용 mock으로 실행했다. resolved 지적과 catch-up 이후 빈 커밋을 주자 출력은 base_after_catch_up='CATCH_UP', compared=['CATCH_UP..EMPTY_LATE_COMMIT'], verdict_after='unresolved', reason='수정 커밋의 diff가 비었다', second_fix_targets=[1]이었다. 실제 수정은 그대로 남아 있는데 기준 변경 때문에 판정이 뒤집힌다.
판단: `a.base` 이동 뒤 빈 커밋이면 unresolved로 뒤집히는 경로는 코드로 확인했지만(mock 재현은 다시 돌리지 않음), 드문 조건에서 수정 worker를 최대 한 번 더 띄우고 보수적 판정을 남길 뿐 미리뷰 코드가 병합되지 않아 티켓 위반이 아니고, 의도한 기준 이동을 병합 경로에서 다시 설계해야 해 애매하므로 report다.
보고서: .goldstack/work/goldstack-v15/report.md
