---
date: "2026-11-06"
severity: "low"
source: "/retro goldstack-v12, v13, v14, v15"
status: "taken"
issues: []
feature: "goldstack-v16"
---
codex sandbox 면제 목록에 `ps`가 없어, 환경 차단을 보고한 worker에게 리뷰어가 규칙 위반 low 지적을 반복한다.

**근거**: `adapters.Codex.NOTE`는 네트워크, localhost, 홈 디렉터리 쓰기만 면제한다. `tests/support.py`의 `alive`와 일부 시험이 쓰는 `ps`는 sandbox에서 항상 `Operation not permitted`다. 같은 지적이 v14 02·03·05, v15 03·06에 나왔다. 코드 결함이 아니고 보고만 지적 수만 늘린다.

**제안**: `NOTE`와 리뷰 지시의 면제 목록에 `ps`를 더한다. [[codex-worker-no-full-test]]와 같은 문장을 고치므로 한 티켓으로 묶는다. `alive`를 `ps` 없이 쓸지는 좀비 판별(`stat=`) 때문에 따로 판단한다.
