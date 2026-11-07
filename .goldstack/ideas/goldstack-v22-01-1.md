---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v22 리뷰 01"
status: "open"
feature: ""
---
verify가 `exec`를 사용하면 표지가 사라져 다음 gs go가 살아남은 검증을 정리하지 못한다. 예를 들어 `exec sleep 300`은 허용되는 검증 명령이지만, 덧붙인 `exit $?`가 실행되기 전에 표지가 있는 bash를 대체하므로 새 검증과 동시에 남는다.

위치: src/gs/verify.py:114
근거: 코드는 `subprocess.Popen(["bash", "-c", spec.verify + KEEP_BASH, mark(...)], ...)`로 실행하며, 정리는 `^bash -c ... gs-verify:...$`에 맞는 프로세스만 찾는다. `.venv/bin/python -B -c`로 동일한 실행 형식에서 `exec <python> -c <대기 코드>`를 실행한 좁은 재현 결과: `valid verify: True`, `same PID as launched bash: True`, `marker in running argv: False`. 대체된 명령의 ps 행을 `_ps`에 주입하면 `detected groups: {}`였다(ps 직접 실행은 sandbox에서 거부됨). 티켓의 '새 검증을 시작하기 전에 같은 표지의 프로세스를 ps에서 찾아 그 프로세스 그룹을 끝낸다' 조건을 충족하지 못한다.
판단: `exec`로 bash를 대신하면 명령줄에서 표지가 사라지는 것은 spec 2-1이 고른 표지 방식의 한계이고 verify.py 머리말에도 '못 찾는 것'으로 적혀 있으며, 고치려면 티켓이 범위 밖으로 둔 번호 저장 같은 다른 방식이 필요하므로 이 티켓에서 고칠 결함이 아니다.
보고서: .goldstack/work/goldstack-v22/report.md
