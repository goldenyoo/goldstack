---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v20 리뷰 02"
status: "dropped"
feature: ""
---
아침 보고 직전의 대기열 확인과 종료가 분리되어 있어, 그 사이에 성공한 add가 실행되지 않고 남는다. 다른 세션은 아직 살아 있는 코디네이터 표시를 보고 종료하고, 코디네이터는 추가된 줄을 다시 확인하지 않은 채 보고를 쓰고 disarm한다.

위치: skills/overnight/SKILL.md:133
근거: 133줄은 '파일을 다시 읽어 `대기` 줄이 생겼으면'만 확인한 뒤 보고를 작성하고, 152줄에서 disarm한다. 이 종료 과정은 add의 잠금에 참여하지 않는다. src/gs/overnight.py:329-337은 보고 제목이 아직 없으면 추가를 허용하고, 347-353은 살아 있는 표시만으로 코디네이터가 있다고 출력한다. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c …`로 파일 쓰기를 메모리로 모킹하고 '대기 0개 확인 → _enqueue(b) → _coordinator → 보고 추가' 순서를 재현한 결과: `report_start_waiting_rows=0`, `enqueue_return=None`, `add_coordinator=코디네이터: 세션 pid 123`, `report_written_with_waiting_b=True`. 티켓 목표인 '도는 실행 뒤에 다음 feature를 붙인다'를 이 경계에서 …(일부 생략, 보고서에 전체)
판단: 보고 직전 확인과 disarm 사이의 틈은 SKILL.md:133,152로 확인했지만, 보고를 쓰는 짧은 동안에만 생기고 add 잠금 밖인 모델 Edit까지 얽혀 있어 종료 절차를 새로 설계해야 하므로 이 티켓에서 고칠 결함인지 애매하다.
보고서: .goldstack/work/goldstack-v20/report.md

- 2026-11-07 닫음: 커밋 `6e78068`이 막았다. `gs overnight disarm`이 잠금 안에서 보고가 있는 밤의 `대기` 줄을 보고 끄지 않는다. 시험 `test_report_written_before_disarm_keeps_the_added_row_alive`. (출처: goldstack-v21 grill 2-4)
