---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v14 리뷰 01"
status: "open"
feature: ""
---
실패한 시도의 verify.log가 없어도 다른 시도의 로그가 하나라도 있으면 누락을 표시하지 않는다. 성공한 시도의 로그만 보여 주므로 실패 원인을 확인할 수 없는 상태가 숨겨진다.

위치: src/gs/report.py:362
근거: 티켓 완료 조건: 'verify.log가 없으면 없다고 적는다.' `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c`로 validations에 티켓 09의 시도 1 failed와 시도 2 passed를 넣고, Path.glob/stat/open을 mock해 09/2/verify.log('Ran 1 test\nOK')만 존재하도록 재현했다. 출력은 '티켓 09: `09/2/verify.log` / 해당 실패 줄 없음'이었고, 'verify.log 없음' 포함 여부는 False였다. 363행은 실패 기록별 로그 존재 여부가 아니라 티켓의 전체 로그 목록이 비었는지만 검사한다.
판단: 362-364행의 티켓 단위 검사는 확인했지만, 실패한 시도의 로그만 사라지는 경로는 Path mock 재현뿐이고 go.py의 읽은 범위에서도 확인되지 않으며, ticket_attempt를 로그 디렉터리에 맞추는 수정은 옛 state와 수리·재시작 디렉터리 때문에 위험해 애매하다.
보고서: .goldstack/work/goldstack-v14/report.md
