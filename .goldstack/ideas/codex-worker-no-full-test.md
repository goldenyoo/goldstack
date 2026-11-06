---
date: "2026-11-06"
severity: "medium"
source: "/retro goldstack-v12, v13, v14, v15"
status: "taken"
issues: []
feature: "goldstack-v18"
---
codex 첫 worker가 sandbox에서 통과할 수 없는 전체 시험에 9–19분을 쓴다. 좁은 시험까지만 돌리게 한다.

**근거(첫 worker 시간, state.json)**: v13 01 12.5분, v14 02 18.3분, 03 11.8분, 05 15.1분, 08 1.4분, v15 01 9.1분, 03 14.0분, 06 19.0분. 8번 중 7번이 전체 시험을 돌렸고 localhost 21건, `ps` 31건 안팎이 언제나 실패했다(v13 01, v14 05, v15 01). `uv run`과 `uv build`도 막혀 임시 캐시까지 시도한다. 전체 시험을 건너뛴 v14 08만 1.4분이었고, 뒤에 수정 worker가 낸 회귀는 gs 검증과 수리 worker가 잡았다(수리 53초, 재검증 약 7분).

**반복**: goldstack-v7·v9·v11 보고서와 [[codex-worker-test-env]]. goldstack-v12의 setup과 profile 안내로 `.venv/bin/python` 좁은 시험은 돌게 됐지만 전체 시험 시도는 그대로다.

**제안**: `adapters.Codex.NOTE`에 sandbox에서는 좁은 시험까지만 돌리고 전체 검증은 gs에 맡기라고 적는다. `worker.write_brief`의 "커밋 전에 이 명령을 한 번 돌린다"와 부딪치지 않게 함께 고친다.

**이어서 볼 것**: 범위 밖 `first-worker-no-verify`의 다시 볼 조건("수정·수리 worker의 검증 실패가 늘지 않았으면")이 이번 밤에 충족됐다(30장 중 검증 실패 1건). Claude 첫 worker(예: v14 01 전체 시험 2번에 약 25분)까지 넓힐지는 grill에서 정한다. 표본은 하룻밤이다.
