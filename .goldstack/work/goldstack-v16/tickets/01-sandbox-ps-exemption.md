---
id: "01"
title: "sandbox 면제 목록에 `ps` 더하기"
blocked_by: []
touches: ["src/gs/worker.py", "src/gs/review.py", "src/gs/adapters.py", "tests/test_sandbox_brief.py", "tests/test_fix_brief.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
codex sandbox에서 항상 막히는 `ps`를 worker와 리뷰어의 면제 목록에 더한다. 환경 차단을 보고한 worker에게 규칙 위반 지적이 반복되지 않게 한다.

## 완료 조건
- `worker.write_brief`의 sandbox 문장, `review.py`의 리뷰·재리뷰 지시 3곳, `adapters.Codex.NOTE`와 그 docstring이 네트워크, localhost, 홈 디렉터리 쓰기와 함께 `ps` 실행도 면제로 말한다. claude worker brief에도 같은 문장이 나가면 그대로 둔다.
- "그 밖의 실패는 sandbox 탓으로 돌리지 말고 고친다"는 문장은 남는다.
- `tests/test_sandbox_brief.py`와 `tests/test_fix_brief.py`가 worker brief와 리뷰 지시 모두에서 `ps` 면제를 확인한다.
- 전체 검증이 통과한다.

## 범위 밖
- `tests/support.py`의 `alive`를 `ps` 없이 쓰기: `out-of-scope/alive-without-ps.md`.
- codex worker의 전체 시험 줄이기: `.goldstack/ideas/codex-worker-no-full-test.md`.

## 참고
- `.goldstack/ideas/sandbox-ps-exemption.md`
- spec §6
