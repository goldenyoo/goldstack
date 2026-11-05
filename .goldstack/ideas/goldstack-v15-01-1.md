---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v15 리뷰 01"
status: "open"
feature: ""
---
숨길 번호는 dropped·taken을 포함한 모든 아이디어에서 모으는데, 기본 `gs backlog`의 아이디어 줄은 open만 찍는다. 그래서 dropped·taken 아이디어에 연결된 열린 issue는 issue 목록과 아이디어 줄 어디에도 나오지 않는다. `/grill` 후보에서도 사라지고, `--all`에서만 보인다.

위치: src/gs/backlog.py:91
근거: 코드 읽기로 확인했고 실행은 못 했다. `backlog.py:76` `if not show_all and idea.status != "open": continue`, `backlog.py:91` `{n for idea in ideas for n in idea.issues}`. 시험이 이 동작을 굳힌다: `tests/test_backlog.py:110`의 `dropped`(`issues='[14]'`)가 `tests/test_backlog.py:142`의 기본 실행 rows에 없고, 시험은 `issues: #14` 표시를 확인하지 않는다. 어긴 문장은 티켓의 '열린 issue가 미분류, 아이디어 연결 중 어디에 있는지 보이게 하고'와 '그 아이디어 줄에 번호를 보인다'다. 실패 시나리오 1: 아이디어를 dropped로 바꿔도 v12 결정 2-20('not planned 닫기는 사람 명령일 때만')에 따라 issue는 열려 있는데, 기본 목록에서 사라져 사람이 닫을 단서가 없다. 실패  …(일부 생략, 보고서에 전체)
판단: `backlog.py:76`과 `:91`로 dropped·taken 아이디어에 연결된 열린 issue가 기본 목록에서 빠지는 것은 확인했지만, 티켓은 상태별 숨김 규칙을 정하지 않았고 시험은 이 동작을 고정하며 taken을 다시 보이면 진행 중 issue가 후보로 되살아나므로 사람이 정할 설계 문제이고, 재오픈 시나리오는 티켓 02·03 범위다.
보고서: .goldstack/work/goldstack-v15/report.md
