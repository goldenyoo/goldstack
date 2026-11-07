---
date: "2026-11-07"
severity: "medium"
source: "goldstack-v21 리뷰 04"
status: "dropped"
feature: ""
---
종료 코드가 0이면 현재 출력의 신호 종료 문구를 검사하지 않는다. 따라서 파이프라인 마지막 명령 등이 성공하면 실제 xargs 자식이 신호로 죽었어도 재검증 없이 통과·병합한다.

위치: src/gs/verify.py:120
근거: 완료 조건은 이번 실행 로그에 줄 처음부터 지정된 신호 문구가 “있으면 끊김”이며 종료 코드 0을 제외하지 않는다. 실제 `printf 'a\nb\n' | xargs -P 2 -n 1 sh -c 'kill -TERM $$'; true`를 bash로 실행한 결과 종료 코드 0과 'xargs: sh: terminated with signal 15; aborting' 줄을 얻었다. 이 실측 출력을 _output에 제공해 판정한 결과 'signal_line_match: True', 'code: 0 interrupted: False ok: True'였다. 원인은 `if code == 0: return False`이며, Result.ok도 interrupted를 확인하지 않아 go._merge_stage의 실패 분기로 들어가지 않는다.
판단: `if code == 0: return False`는 확인되고 티켓 문구에 종료 코드 0 예외가 없지만, 통과는 수리 오진을 일으키지 않는다는 티켓 목표와 어긋나지 않고 구현은 통과를 끊김에서 일부러 제외했으며, 통과 출력의 문구만으로 다시 검증하면 그 문구를 찍는 시험이 병합되지 못할 위험이 있고 재현도 `; true`로 만든 경우라 명세 위반인지 애매하다.
보고서: .goldstack/work/goldstack-v21/report.md

닫은 이유(goldstack-v22 grill 1-2, 2026-11-07): `verify`가 `&&`로 이어져 있어 종료 코드 0에 신호 줄이 남으려면 `; true` 같은 모양이 필요하고, 그 문구를 찍는 시험까지 병합을 막을 위험이 있다.
