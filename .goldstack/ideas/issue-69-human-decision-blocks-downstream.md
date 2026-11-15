---
date: "2026-11-15"
severity: "medium"
source: "issue #69 (goldstack-v42 grill 라운드 1-4)"
status: "open"
issues: [69]
feature: ""
---
worker가 최종 보고에 "다음 티켓 전에 사람이 정해야 한다"를 적어도 gs는 blocked_by만 보고 하류 티켓을 시작한다. 하류 worker가 그 결정을 스스로 내렸다(레포 밖 파일 압축·삭제).

- 출처: GitHub issue #69 field-report(gs 0.2.16, pod 레포, 1회 확인). 본문은 이 세션이 다시 확인하지 않았다.
- 제안(issue): worker 보고에 구조화된 "사람 결정 필요" 절을 두고, gs가 그 절을 보면 그 티켓에 걸린 하류 티켓을 시작하지 않고 멈춘 뒤 보고서에 올린다.
- 무인 흐름 구조를 바꾼다. brief의 "사람에게 묻지 않는다"와 맞춰 볼 것. goldstack-v42는 크기 때문에 뺐다.
