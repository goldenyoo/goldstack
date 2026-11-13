---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
수동 피드백 본문이 `## 증상`처럼 `##`로 시작하면 issue 제목이 모두 `[field] ## 증상 (gs …)` 같은 꼴로 같아질 수 있다.

- goldstack-v35 01 리뷰(claude, low, 보고만): 티켓 규칙(첫 `# ` 줄, 없으면 비어 있지 않은 첫 줄)은 지켰고 spec 2-1의 빈틈이다. 코드 블록 안의 `# ` 주석이 뽑힐 수도 있다(`run/retro-log.md` L44).
- 제안: 제목 후보에서 `#` 여러 개 제목과 코드 블록 안 줄을 건너뛰고, 그래도 없으면 첫 문단 문장을 쓴다.
