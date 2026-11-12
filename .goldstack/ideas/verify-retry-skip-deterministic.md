---
date: "2026-11-12"
severity: "medium"
source: "/retro goldstack-v32"
status: "taken"
issues: []
feature: "goldstack-v33"
---
[반복] 판별(`[verify]`)이 결정적 실패라고 가린 뒤에도 `verify_retries`가 전체 검증을 한 번 더 돌린다.

- goldstack-v32 03: 첫 검증이 15:08:18–15:26:53, 18분 35초 걸렸다. 같은 실행의 다른 전체 검증은 9분 15초–9분 44초다(`run/state.json` phases).
- `run/03/1/fix/verify.log` 886–892행:
  ```text
  FAILED (errors=12)

  판별 종료 코드: 1

  판별 실패: test_tiers. 전체 검증은 다시 돌리지 않는다

  검증 재시도 1
  ```
  "다시 돌리지 않는다" 바로 뒤에 전체 검증이 다시 돌았고 같은 `AttributeError` 12건으로 끝났다. 실패한 파일을 혼자 돌려도 실패했으니 두 번째 전체 실행은 결과가 정해져 있었다.
- 반복: goldstack-v22(`verify-same-head-after-repair`)에도 "`verify_retries: 1` 때문에 실패할 때마다 두 배로 돌았다"가 있다. `docs/guide.md`는 둘을 함께 쓰면 판별 뒤에도 `verify_retries`만큼 더 시도한다고 적는다. 지금 동작은 문서대로다.

고칠 곳: `src/gs/go.py`의 검증 재시도. 판별이 실패로 끝난 시도는 `verify_retries`를 쓰지 않고 바로 수리로 넘긴다. 판별을 돌리지 못한 경우(실패 파일을 못 찾음, `max_files` 초과)는 지금처럼 재시도한다. `docs/guide.md`의 "`verify_retries`와의 관계"와 로그 문구도 맞춘다.

근거는 이 세션이 `run/` 로그로 직접 확인했다.
