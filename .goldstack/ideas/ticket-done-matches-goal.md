---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v24"
status: "taken"
issues: []
feature: "goldstack-v25"
---
완료 조건이 티켓 목표보다 약해서, 실제 결함이 "애매하면 보고만"으로 빠졌다.

- v24 01: 판단 사유는 "완료 조건과 spec 2-7은 codex에 exit_code만 요구"였다. 티켓 목표는 "worker 글이 아니라 실행 기록으로 확인"이다.
- 보고만 지적 2건의 원인은 하나다. 표시용 `_short`를 데이터로 다시 썼다.

고칠 곳: grill 템플릿 §5나 티켓 완료 조건 규칙. 목표의 동사마다 완료 조건이 하나씩 있는지, 표시용 값과 원본 데이터를 구분했는지 확인하게 한다. 관련: [[fix-outside-ticket-scope]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
