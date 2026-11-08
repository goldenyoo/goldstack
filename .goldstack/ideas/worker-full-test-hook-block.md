---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v25"
status: "taken"
issues: []
feature: "goldstack-v26"
---
claude worker가 brief의 "전체 검증은 돌리지 않는다"를 어기고 시험을 거의 전부 돌린다. 문구 대신 hook으로 막는다.

- v25 03: brief에 "전체 검증은 gs가 돌린다. 너는 돌리지 않는다"가 있는데 worker.log에 시험 95개 중 16개만 뺀 `ls tests | grep -v … | xargs -P 6` 명령이 3번 있다. 02도 시험 16개를 백그라운드로 돌리며 worker 턴 14번. 02·03은 일렬 경로에서 각 약 27분.
- 반복: v17(전체 시험 4번) → `claude-first-worker-no-verify`(v20 taken)로 brief 문구를 넣었지만 지켜지지 않는다.

고칠 곳: `src/gs/hook.py`의 worker Bash 검사. 시험 러너를 가정하지 않게, 막을 형태(예: 시험 파일 N개 이상, 시험 폴더 전체 순회)는 config로 뺄지 함께 정한다. 관련: [[claude-first-worker-no-verify]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
