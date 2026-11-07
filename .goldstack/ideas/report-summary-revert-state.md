---
date: "2026-11-07"
severity: "medium"
source: "/retro goldstack-v21"
status: "taken"
issues: []
feature: "goldstack-v22"
---
보고서 Summary가 병합 전에 쓰여 revert와 다시 넣는 방법을 싣지 않는다.

- v21: `summary.md` 12:31, revert 12:40. 본문은 v21을 들어간 것처럼 설명하고 후속은 04 high뿐이다. 마무리 한 줄만 `reverted`다.
- 반복: `main-report-state`(goldstack-v3에서 다뤘다). 그때는 병합 뒤 상태 줄을 고쳤고 revert의 다음 행동은 다루지 않았다.

고칠 곳: `src/gs/finish.py`. revert면 Summary 맨 위에 상태와 다음 명령(`gs go <feature>`)을 코드로 넣는다.
