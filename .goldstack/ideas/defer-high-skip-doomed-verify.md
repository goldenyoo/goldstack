---
date: "2026-11-14"
severity: "high"
source: "/retro goldstack-v40"
status: "taken"
issues: []
feature: "goldstack-v41"
---
리뷰 판정이 touches 밖 high를 `defer`(전체 검증이 반드시 실패)로 정했는데도 10분짜리 티켓 검증을 그대로 돌리고, 실패한 뒤에야 수리로 간다.

- goldstack-v40 01 `run/01/1/review/judge.txt`: high 1건(`tests/test_config.py`의 deny 개수 3 단언), action `defer`, 이유 "전체 검증이 반드시 실패한다"(이 세션이 `defer`를 확인했다). 검증 634.6초 동안 실패했고 수리는 35초에 끝났다. 그동안 일렬 경로의 머리인 02가 병합 대기로 약 10분 섰다(retro subagent 보고).
- [반복] goldstack-v35·v36에도 touches 밖 충돌 시험 때문에 같은 실패가 났다(taken `touches-missing-conflicting-tests`). 범위 밖 `touches-conflict-repair-route`의 다시 볼 조건에 닿았다.
- 고칠 곳 두 가지:
  - `src/gs/go.py`: 재현된 `defer` high가 있으면 검증 전에 바로 수리로 보낸다.
  - grill `templates/spec.md` touches 주석: grep 대상에 바뀌는 설정 키(예: `worker_tests`)를 더한다. 그러면 `test_config.py`가 grep에 걸린다.
