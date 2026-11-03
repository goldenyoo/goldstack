---
date: "2026-11-03"
severity: "high"
source: "goldstack-v2 리뷰 지적(02)"
status: "taken"
feature: "goldstack-v3"
---
[high] PR 조회·생성·병합(`gh pr …`)이 `git.remote`를 따르지 않고 gh 기본 저장소를 쓴다. 원격이 여럿이면 다른 저장소 PR을 병합할 수 있다. 원격 URL을 owner/repo로 풀어 `--repo`를 붙이기

출처: goldstack-v2 리뷰 지적(02)
