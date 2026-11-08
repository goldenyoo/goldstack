---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v22"
status: "taken"
issues: []
feature: "goldstack-v25"
---
티켓 병합 뒤 integration `.venv`를 다시 준비하지 않아, 버전·의존성을 바꾼 티켓의 검증이 옛 환경에서 돈다.

- v22: integration/1·2의 setup.log에는 `+ goldstack==0.2.5`만 있다. setup은 marker가 없을 때 한 번만 돈다(`src/gs/go.py`). 버전을 올린 티켓의 검증 로그 5개에서 `'0.2.5' != '0.2.6'`이 나왔다.
- 이 레포는 `verify` 앞에 `uv sync --locked -q`를 붙여 우회했다(2026-11-08 밤샘). 다른 레포는 같은 문제를 겪는다.

고칠 곳: `src/gs/go.py`. 병합 diff가 setup에 영향을 주는 파일(lockfile 등)을 건드리면 `worktree.setup`을 다시 돌린다. 어떤 파일인지는 환경을 가정하지 않게 config로 뺄지 함께 정한다. 관련: [[repair-out-of-branch-stop]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
