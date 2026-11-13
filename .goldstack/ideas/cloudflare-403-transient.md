---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v38"
status: "taken"
issues: []
feature: "goldstack-v39"
---
Cloudflare 엣지 차단 403(`Attention Required! | Cloudflare`)이 영구 오류로 분류되어 재시도되지 않는다.

- `src/gs/transient.py`의 `_PERMANENT`가 `\b(?:401|403)\b`를 잡는다(이 세션이 확인). goldstack-v38 01 worker 턴이 이 403으로 죽었는데 보고서에는 "일시 오류 0회"로 남았다.
- 고칠 곳: `transient.py`의 `_PERMANENT`·`_error_reason`. Cloudflare 챌린지 문구가 있는 403은 일시 오류로 본다. 인증 403은 그대로 영구 오류다.
- `worker-disallow-schedule-wakeup`과 함께 고친다.
- 관련: 닫힌 `transient-api-error-retry`의 후속
- 근거 출처: retro subagent 보고. 패턴은 이 세션이 확인했다.
