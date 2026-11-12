---
date: "2026-11-12"
severity: "medium"
source: "/retro goldstack-v32"
status: "taken"
issues: []
feature: "goldstack-v33"
---
worker가 바꾼 함수의 호출부를 `src/`에서만 찾아, 그 함수에 닿는 기존 시험을 돌리지 않고 병합 검증에서 실패했다.

- goldstack-v32 03: `go._worker_adapter`가 `r.sandbox`를 읽게 바꿨다. `tests/test_tiers.py`는 `sandbox`가 없는 `SimpleNamespace`를 가짜 `Run`으로 넘긴다. 병합 검증에서 `test_tiers.TiersTest.test_coordinator_selects_table_or_legacy_and_records_each_attempt` 하위 시험 12개가 `AttributeError: 'types.SimpleNamespace' object has no attribute 'sandbox'`로 실패했다(`run/03/1/fix/verify.log`).
- worker가 호출부를 찾은 명령은 `src/gs/*.py`만 본다(`run/03/1/worker.log` L300):
  ```text
  grep -rn "review\.run\b\|review\.run(\|review\.rereview\|review\.repair_review\|_ask_reviewer\|for_model(\|_worker_adapter(" src/gs/*.py | grep -v "^src/gs/review.py" ; ls -la .venv 2>/dev/null | head -3; cat .venv/lib/python3.12/site-packages/*.pth 2>/dev/null | head; grep -n "def review_call\|def reviewed" -A12 src/gs/metrics.py | head -40
  ```
  worker의 Bash 명령 가운데 `unittest`와 `test_tiers`가 함께 든 것은 없다.
- 값: 검증 18분 35초 + 수리 1분 11초 + 수리 재리뷰 1분 26초 + 재검증 9분 17초. 03은 일렬 경로라 그대로 전체 시간에 더해졌다. 수리는 한 줄(`getattr(r, "sandbox", None)`)이었다.
- codex·agy 리뷰도 이 시험을 짚지 않았다. `[hook.worker_tests]`가 전체 시험을 막으니 닿는 시험을 고르는 일은 worker 몫이다.

고칠 곳: worker brief 규칙(`src/gs/worker.py`)에 단계 하나. "서명이나 읽는 속성을 바꾼 함수·클래스는 이름을 `tests/`에서 grep해 닿는 시험 파일을 모두 돌린다." 완료 기준은 grep에 나온 시험 파일이 모두 돈 것이다. 관련: [[ticket-final-observation-test]], [[verify-retry-skip-deterministic]]

근거는 이 세션이 `run/` 로그와 수리 커밋 `a9a6cfb`로 직접 확인했다.
