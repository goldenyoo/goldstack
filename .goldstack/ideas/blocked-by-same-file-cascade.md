---
date: "2026-11-15"
severity: "high"
source: "/retro goldstack-v42"
status: "taken"
issues: []
feature: "goldstack-v43"
---
`blocked_by`가 "같은 파일" 이유(순서만 필요)로 걸려도 상류가 실패하면 하류가 통째로 건너뛰어진다. 한 문장짜리 티켓의 실패가 큰 티켓과 문서 티켓을 함께 뺀다.

- goldstack-v42: 03(medium, 예상 29분)이 01과 `src/gs/worker.py`를 함께 건드려 "01 같은 파일"로 걸렸다. 01이 flaky 검증으로 실패하자 03·04가 `attempts=0`, "막힘: 01"로 건너뛰어졌다. 버전은 0.2.25 그대로, 02 문서도 빠졌다(보고서 "문서 미반영: 04")(retro subagent 보고).
- spec 템플릿 §5 주석은 blocked_by 이유를 "같은 파일"과 "앞 결과 필요"로 나눠 적게 하지만 gs는 둘을 같게 다룬다.
- [반복] goldstack-v11: 09 실패로 10이 건너뛰어졌다(taken `docs-ticket-blocked-by-all`, goldstack-v14가 문서 티켓만 다뤘다).
- 고칠 곳 후보: 티켓 형식에서 순서 의존(같은 파일)과 내용 의존을 나눈다. 순서 의존 상류가 실패하면 하류를 지금 integration 위에서 돌린다. 또는 grill이 작은 같은 파일 티켓을 큰 티켓에 합치게 한다(템플릿 §5 "묶기").
