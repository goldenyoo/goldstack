---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v22"
status: "taken"
issues: []
feature: "goldstack-v25"
---
실패 요약 모델이 worker의 맞는 진단을 깎아내리고, 환경 차이를 원인 후보에서 뺐다.

- v22 04/2/repair/failure-summary.md: worker의 `.venv` 진단을 `[전언]`으로 낮췄다. 또 "integration 트리에서 검증이 도는 것은 정상… 그 위치를 원인으로 보지 말 것"이라고 적어, 실제 원인에서 시선을 돌렸다.

고칠 곳: 실패 요약 프롬프트. integration·worktree 환경 차이(setup 시각, 설치 메타데이터)도 원인 후보로 확인하게 한다.

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
