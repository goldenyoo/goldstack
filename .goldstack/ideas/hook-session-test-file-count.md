---
date: "2026-11-14"
severity: "medium"
source: "/retro goldstack-v40"
status: "open"
issues: []
feature: ""
---
worker가 grep으로 고른 시험 파일을 상한 아래 묶음으로 나눠 돌리면, 명령 하나만 보는 hook(`max_files`, goldstack-v40 deny)이 넓은 시험 실행을 막지 못한다.

- goldstack-v40 03 `run/03/1/worker.log` L420: grep으로 시험 파일 23개를 고르고, L427·L431·L435에서 8·9·10개 묶음을 백그라운드로 돌렸다. 합쳐 27개 파일, 약 5–7분(retro subagent 보고, 시간은 미확인). 이 실행은 `test_rereview.py` 실패를 미리 잡기도 했다.
- 이번 실행은 설치본 0.2.23으로 돌아서 v40의 brief 상한 규칙이 아직 적용되지 않았다. 0.2.24 실행에서 같은 모양이 다시 나오는지 먼저 본다.
- 고칠 곳 후보: `src/gs/hook.py`가 worker 세션 전체에서 돌린 시험 파일 수를 누적해 센다.
