---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v22"
status: "taken"
issues: []
feature: "goldstack-v25"
---
커밋 없는 repair 뒤에 같은 head를 다시 검증한다.

- v22 report.md 92–99행: ticket-04-repair 검증이 바로 앞 ticket-04 검증과 integration head, ticket head가 같다. 결과가 뻔한 재검증 4회에 약 33분이 들었고, `verify_retries: 1` 때문에 실패할 때마다 두 배로 돌았다.

고칠 곳: `src/gs/go.py`의 repair 뒤 검증. head가 같으면 다시 돌리지 않고 바로 실패로 처리한다. 관련: [[repair-out-of-branch-stop]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
