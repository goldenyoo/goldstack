---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v22"
status: "taken"
issues: []
feature: "goldstack-v25"
---
실패한 티켓을 다시 돌리면 앞 시도의 리뷰 지적이 보고서에서 사라진다.

- v22 04: state.json은 `attempts: 3`, `findings: []`인데 run/04에는 시도 폴더가 4개 있다. 04/3/review/findings.json의 2건(medium 1, low 1)이 최종 보고서에 없다.

고칠 곳: 재실행할 때 앞 시도의 지적을 state에 보존하고 `src/gs/report.py`에서 합친다.

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
