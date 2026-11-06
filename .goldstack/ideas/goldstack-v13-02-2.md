---
date: "2026-11-06"
severity: "medium"
source: "goldstack-v13 리뷰 02"
status: "dropped"
feature: ""
---
실행 중 확인과 세션 생성 사이에 잠금이나 예약이 없어, 같은 feature를 동시에 시작하면 이미 gs go가 실행 중인데도 추가 Claude 세션을 띄울 수 있다. PREPARE는 pull 전에 읽은 running 값만 반환하고, 이후 launch까지 다시 확인하지 않는다.

위치: src/gs/remote.py:135
근거: running()은 공유 잠금을 즉시 풀고(130행), result['running']을 정한 다음 git pull을 수행한다(135~139행). go는 이 과거 값으로만 판정한 뒤 launch한다(358~375행). PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c로 실제 PREPARE 문자열을 실행하되 pull 도중 다른 gs go가 잠금을 획득하는 상황을 모의한 좁은 재현 결과: 'prepare.running = None ; gs go became active during pull = True', 'launch called while gs go is active = True', 'go returned: 0'. 티켓은 '이미 그 feature의 gs go가 원격에서 돌고 있으면 띄우지 않고 그 사실을 말한다'고 요구한다. 이후 gs go 자체의 잠금은 추가 Claude 세션 생성을 막지 못한다.
판단: 확인과 launch 사이의 경합은 코드상 존재하지만 pull 중에 시작된 드문 동시 실행에서만 생기고, 재확인으로는 창을 좁힐 뿐이며, 막으려면 `/go`가 `gs go` 잠금을 잡을 때까지 이어지는 원격 예약을 새로 설계해야 해서 티켓 범위를 넘고 애매하다.
보고서: .goldstack/work/goldstack-v13/report.md

버린 이유: goldstack-v19 grill에서 닫았다. 근거와 다시 볼 조건은 범위 밖 `remote-go-reservation`.
