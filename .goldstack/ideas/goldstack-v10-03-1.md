---
date: "2026-11-05"
severity: "high"
source: "goldstack-v10 리뷰 03"
status: "open"
feature: ""
---
이전 verified 실행에 새 티켓을 추가한 뒤, integration 병합 직후 중단되면 --only 재실행이 완료 상태를 무효화하지 않는다. 이후 gs clean이 미병합 변경을 삭제해도 옵션 없는 gs go는 '이미 끝남'으로 종료하여 새 티켓을 base에 반영하지 않는다.

위치: src/gs/go.py:252
근거: 쓰기·git I/O를 mock한 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c ...` 재현: 기존 verified 상태에서 09를 merged로 만든 직후 KeyboardInterrupt를 주입하고 --only 09를 재실행했다. 결과는 `retry exit: 0`, `retry prior: ['09']`, finish.phase는 여전히 verified였다. 정리 후 조건에서는 실제 `_finished_after_clean`이 True를 반환했다. 원인은 `status == state.MERGED and tid not in r.prior` 조건이다. 중단 시 177행의 _stop_only를 건너뛰고, 재실행의 _resume_merged는 09를 prior에 넣으므로 완료 상태가 계속 남는다. clean.py:105는 verified면 --force 없이 삭제를 허용한다. 티켓의 '이어서 치는 옵션 없는 gs go가  …(일부 생략, 보고서에 전체)
판단: _stop_only를 건너뛰는 중단 경로는 코드로 확인되지만, 중단 뒤 바로 치는 옵션 없는 gs go는 finish.run의 새 병합 판정으로 정상 병합되므로 티켓 조건 위반이 아니고, 문제는 중단 직후의 좁은 틈과 gs clean이 겹칠 때만 생기며 옵션 없는 gs go에도 같은 틈이 있어 이 티켓 범위로 보기 애매하다.
보고서: .goldstack/work/goldstack-v10/report.md
