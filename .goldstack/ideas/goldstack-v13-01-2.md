---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v13 리뷰 01"
status: "dropped"
feature: ""
---
`herdr machine status`의 제한 시간 10초가 herdr의 SSH `ConnectTimeout=10`과 같다. 다른 저장 머신이 패킷을 버려 연결 시간 초과까지 가면 명령이 10초 안에 끝나지 않을 수 있다. 그러면 `TimeoutExpired`로 대상 머신의 줄까지 버려지고 `빠짐: 원격 검사 → 시간 초과`, 종료 1이 된다. 다른 머신의 실패가 대상 머신의 판정을 깨는 경우로, 티켓의 '머신 연결은 그 머신 줄로 판단한다. 다른 머신이 실패해도…'를 어긴다.

위치: src/gs/remote.py:183
근거: 코드: `cp = _run([herdr.bin(), "machine", "status"], 10)`. 바이너리 `~/.local/bin/herdr`의 문자열에 `ConnectTimeout=10`이 있다. worker.log 19행의 실제 출력 `remote platform detection failed: ssh: connect to host 143.248.148.154 port 22`는 status가 저장 머신마다 ssh 접속을 시도함을 보여 준다. spec §6에도 실패하는 머신(`Yseungjae_154` error)이 있다. 가짜 herdr는 즉시 반환하므로 시험이 이 경우를 다루지 못한다. 그 머신이 패킷을 버리는지(시간 초과인지 즉시 거부인지)는 확인하지 못했다.
판단: 실패 머신이 실제로 10초 넘게 걸리는지 확인되지 않았고 리뷰어도 패킷 폐기 여부를 확인하지 못해 가능성에 그친다.
보고서: .goldstack/work/goldstack-v13/report.md

- 2026-11-06 실제 맥미니 첫 검사에서 재현됐다. `herdr machine status`가 10.6초 걸려 대상까지 시간 초과가 됐다. 대상 머신만 묻게 고쳤다.
버린 이유: 직접 고쳤다(`src/gs/remote.py`).
