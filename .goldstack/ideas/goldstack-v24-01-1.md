---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v24 리뷰 01"
status: "taken"
feature: "goldstack-v25"
---
Codex 명령의 실패 출력을 버려 실패 사유를 대조할 수 없다. sandbox 권한 오류와 실제 시험 실패가 같은 종료 코드를 내면 리뷰어에게 동일한 기록이 전달되어, 실제 실패를 sandbox 탓으로 보고해도 기록으로 구분할 수 없다.

위치: src/gs/streamfmt.py:217
근거: 쓰기 없는 좁은 재현으로 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B -c ...`에서 Path.open을 StringIO로 대체하고 commands()를 호출했다. 동일한 command·exit_code=1에 aggregated_output만 각각 'PermissionError: [Errno 1] Operation not permitted: /Users/x/.cache', 'FAIL: test_answer\nAssertionError: 1 != 2'로 주자 두 결과가 동일했다: [{"command":"python -m unittest","ok":false,"detail":"종료 1"}]. 해당 코드는 `_entry(item["command"], ok, f"종료 {code}" ...)`만 반환하고 aggregated_output을 읽지 않는다. 원본 worker.log 경로도 프롬프트에 제공하지 않는다. 티켓 목표는  …(일부 생략, 보고서에 전체)
판단: Codex 항목이 aggregated_output을 읽지 않아 실패 원인이 기록에 남지 않는 것은 diff(streamfmt.py `_commands_of`)로 확인했지만, 티켓 완료 조건과 spec 2-7은 Codex에 exit_code와 종료 코드만 요구하고 성공 명령·시도 유무 대조는 지금도 가능해 위반이나 실제 결함인지 애매하므로 출력 요약 추가 여부는 사람이 정할 개선 사항이다.
보고서: .goldstack/work/goldstack-v24/report.md
