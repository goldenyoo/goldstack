---
date: "2026-11-08"
severity: "high"
source: "/retro goldstack-v22"
status: "taken"
issues: []
feature: "goldstack-v25"
---
고칠 곳이 브랜치 밖인 검증 실패를 repair가 진단했는데도, 같은 검증을 계속 반복한다.

- v22 04: 03:20 repair worker가 "integration `.venv`가 낡았고 `uv sync --locked`로 고쳐진다"며 커밋 없이 끝났다. 04/3의 리뷰어와 판단 모델도 같은 원인을 짚었지만, 같은 실패가 8회(497초씩, 약 66분) 반복됐다.
- 반복: goldstack-v18 03도 repair가 브랜치 밖 원인을 진단하고 커밋 없이 끝난 뒤 실패로 처리됐다.

고칠 곳: `src/gs/go.py`의 repair·재시도 흐름. repair가 커밋 없이 끝났거나 판단 모델이 범위 밖 차단 원인을 report로 보면, 다음 시도로 넘어가지 말고 마지막 메시지를 이유에 담아 사람에게 넘긴다. 관련: [[verify-same-head-after-repair]], [[integration-setup-after-merge]]

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
