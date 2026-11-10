---
date: "2026-11-08"
severity: "medium"
source: "goldstack-v27 리뷰 03"
status: "taken"
feature: "goldstack-v30"
---
이번 실행의 수리 worker가 표식을 남기고 네트워크 오류로 종료하면 retry=False 처리가 실행되지 않는다. 표식 판정이 _end_repair에만 있어, 먼저 실행되는 일시 오류 분기가 worker를 다시 띄운다.

위치: src/gs/go.py:2354
근거: 티켓 완료 조건: '이번 실행에서 시작해 커밋 없이 끝난 수리 worker의 마지막 메시지에 ... 표식이 있으면 종료 코드와 상관없이 retry=False로 실패한다.' 그러나 go.py:1570–1573은 _transient_end가 이유를 반환하면 _net_hold 후 즉시 반환한다. `.venv/bin/python -B -c`로 파일 쓰기 없는 좁은 재현을 실행했다. codex의 agent_message에 '브랜치 밖 원인: integration 환경에 필요한 도구가 없다', 뒤이은 turn.failed에 'stream disconnected before completion'을 넣고 launched=True·종료 1·커밋 0으로 _check_worker를 호출했다. 실제 streamfmt.last_message는 표식을 추출했지만, 호출 결과는 network_hold_calls=1, end_repair_calls=0이었다. 따라서 추가된 표식 판정에 도달하지 않는다.
판단: _transient_end 분기(go.py:1570)는 이 티켓 전부터 있었고, 네트워크로 끊긴 worker는 끝난 것이 아니라 끊긴 실행이라 다시 띄워 잇는 경로라서, 완료 조건의 '커밋 없이 끝난 수리 worker'에 들어가는지 애매하다. spec·티켓 어디에도 일시 오류보다 표식을 먼저 봐야 한다는 요구가 없다.
보고서: .goldstack/work/goldstack-v27/report.md
