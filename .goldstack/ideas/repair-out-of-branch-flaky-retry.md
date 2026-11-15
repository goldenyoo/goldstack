---
date: "2026-11-15"
severity: "high"
source: "/retro goldstack-v42"
status: "taken"
issues: []
feature: "goldstack-v43"
---
판별이 이미 "실패 시험을 따로 돌리면 통과"를 보였고 그 시험이 diff 밖인데도, 수리 worker의 `브랜치 밖 원인:` 한 줄로 티켓이 재시도 없이 실패가 된다. flaky가 사람이 고칠 실패로 바뀐다.

- goldstack-v42 01: `state.json` `tickets.01.repairs[0].result="failed"`, reason "(재시도하지 않는다…)". verify.log L1893–1900에 판별 OK. 01은 brief 문장 한 줄 티켓이었고, 이 실패로 03·04가 건너뛰어졌다(retro subagent 보고).
- 수리 worker는 21초 만에 `tail -60`·시험 한 번·grep 한 번으로 "sandbox가 ps를 막았다"고 틀리게 결론 냈다. 수리 brief는 92KB 로그 경로만 받는다.
- `docs/guide.md`의 `브랜치 밖 원인:` 규칙(goldstack-v25 `repair-out-of-branch-stop`)대로의 동작이다. 그 규칙은 진짜 브랜치 밖 결함의 반복을 막으려던 것이다.
- 고칠 곳 후보: `src/gs/go.py` 수리·검증 경로. 앞 시도에서 판별이 통과한 파일이고 실패 시험이 diff 밖이면 flaky로 분류해 한 번 더 검증하거나 flaky 표시로 넘긴다(integration flaky 재시도, goldstack-v31과 같은 생각). 수리 brief에 시도별 실패 시험과 판별 결과 요약을 넣는 것도 함께 본다.
