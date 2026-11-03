---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 05 worker 커밋 메시지"
status: "taken"
feature: "goldstack-v3"
---
worker 안 verify가 push 차단 환경변수(`GIT_CONFIG_*`) 때문에 시험 79개가 setUp에서 오류(gs의 밖 재검증은 통과). worker가 자기 검증을 믿지 못하게 된다

출처: goldstack-v2 05 worker 커밋 메시지
