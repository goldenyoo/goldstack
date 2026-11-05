---
date: "2026-11-05"
severity: "medium"
source: "/retro goldstack-v10"
status: "taken"
feature: "goldstack-v11"
---
worker가 가장 먼저 읽는 `.goldstack/profile.md`가 실제 코드와 어긋난다.

**근거(2026-11-05 확인)**:
- `go.py`는 1,168줄이라고 적었지만 2,160줄이다. `finish.py`는 877줄이라고 적었지만 1,051줄이다.
- 시험 파일은 44개라고 적었지만 78개이고, 시험 수 573개도 옛 값이다. goldstack-v10 01 worker 기준 1,298개다.
- fixture가 `tests/test_go.py`에 있다고 적었지만 그 파일은 없다.
- "보고서에 재시도로 통과한 기록은 없다"는 v9·v10의 불안정한 시험과 맞지 않는다.
- 03·05 worker는 `go.py`와 `tests/support.py`를 여러 번 쪼개 읽었다. 낡은 profile이 원인이라고 확인하지는 않았다.

**제안**: 줄 수, 시험 수처럼 환경에서 찾을 수 있는 값은 지우고 함정과 관례만 남긴다(`skills/writing-for-agents`의 쳐내기). `/adopt`의 안내에도 같은 기준을 적을지 본다.
