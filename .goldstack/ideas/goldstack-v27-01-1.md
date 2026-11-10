---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v27 리뷰 01"
status: "taken"
feature: "goldstack-v30"
---
touches가 빈 티켓은 diff에 포함된 파일까지 수정하도록 허용해 명세의 수정 범위를 넓힌다. 해당 파일이 다른 미병합 티켓의 작업 대상이어도 defer 대신 fix할 수 있다.

위치: src/gs/review.py:781
근거: 완료 조건은 고칠 수 있는 파일을 '이 티켓의 touches + 이번 실행에서 이미 병합된 티켓들의 touches'로 한정한다. 그러나 _fixable_rows는 빈 touches에 '이 티켓 diff가 바꾼 파일을 이 티켓의 파일로 본다'를 추가한다. .venv/bin/python -B -c로 judge_prompt와 fix_brief를 touches=[], merged={}로 호출한 결과 두 곳 모두 이 예외가 출력됐으며, fixable_files([], {})는 []였다. _load_ticket도 touches 생략 입력을 problems=[]로 정상 수용하므로 실제 가능한 입력이다.
판단: 빈 touches 예외는 diff에서 확인되고 프롬프트에 그 문장이 찍히는 것도 재현됐지만, 재현된 것은 문장 출력뿐이고 오동작은 아니며, 완료 조건과 spec이 touches 없는 티켓의 기대 동작을 정하지 않아 결함인지 판단할 수 없다.
보고서: .goldstack/work/goldstack-v27/report.md
