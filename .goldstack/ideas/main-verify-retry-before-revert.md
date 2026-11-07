---
date: "2026-11-07"
severity: "high"
source: "/retro goldstack-v21"
status: "open"
issues: []
feature: ""
---
검증을 통과한 트리와 코드가 같아도 main 검증이 한 번 실패하면 다시 돌리지 않고 revert한다.

- v21: `0f89be6`(검증 통과)와 병합 `74d26da`의 차이는 `.goldstack/`뿐인데 `test_revert_landed_through_side_pr` 1건으로 revert `a7aff29`가 나갔고 #32~#35가 다시 열렸다. 같은 시험은 단독 5회, 파일 전체 1회 통과했다. 실패 당시의 6프로세스 부하는 재현하지 않았다.
- 반복: v17 01에서 원인 미상의 검증 실패가 커밋 없이 재검증으로 통과했다.

고칠 곳: `src/gs/finish.py`의 `_postmerge`와 `revert_decision.py`. 검증한 트리와 코드가 같으면 revert 전에 한 번 다시 검증한다. 코드가 다르면 지금처럼 바로 판단한다.
