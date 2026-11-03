---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 리뷰 지적(03)"
status: "taken"
feature: "goldstack-v3"
---
[medium] worker hook의 `local.env` 차단이 정확한 경로만 잡는다(`grep -r …/.goldstack`, `local.e*` glob, Grep 도구 디렉터리 검색은 통과). 경로 검사 말고 다른 방법(예: worker 환경에서 파일 권한, 토큰을 worker가 닿지 않는 곳에) 검토

출처: goldstack-v2 리뷰 지적(03)
