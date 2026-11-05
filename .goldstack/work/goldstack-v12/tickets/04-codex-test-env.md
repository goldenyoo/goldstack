---
id: "04"
title: "codex worker 시험 환경"
blocked_by: []
touches: [".goldstack/config.toml", ".goldstack/profile.md", "src/gs/adapters.py", "tests/test_sandbox_brief.py", ".goldstack/out-of-scope/verify-worker-key.md"]
tier: medium
model: claude
reviewer: codex
---
## 목표
codex worker가 sandbox에서 좁은 시험을 돌릴 수 있게 한다. 지금은 시도마다 우회법을 새로 찾거나 돌려 보지 않고 커밋한다.

## 완료 조건
- `.goldstack/config.toml`에 `[worktree] setup = "uv sync --locked"`가 있다.
- `.goldstack/profile.md`의 빌드·시험 절에 sandbox에서 쓸 명령이 있다: `.venv/bin/python -m unittest discover -s tests -p test_x.py`. `uv run`은 `~/.cache/uv` 차단으로 sandbox에서 실패한다고 적는다.
- codex brief의 sandbox 안내(`adapters.Codex.NOTE`)가 레포 profile에 sandbox용 시험 명령이 있으면 그것을 쓰라고 말한다. 코드에 `uv`나 `.venv`를 적지 않는다(환경을 가정하지 않는다).
- `tests/test_sandbox_brief.py`가 새 문장을 본다.
- `out-of-scope/verify-worker-key.md`의 다시 볼 조건을 "setup과 profile 안내를 넣은 뒤에도 sandbox 실패가 재작업으로 계속 나오면"으로 고친다.

## 범위 밖
- spec `verify_worker` 키: `out-of-scope/verify-worker-key.md`.
- 다른 레포의 setup 값은 `/adopt`의 일이다.

## 참고
- spec 2-3과 §6의 측정
- `.goldstack/ideas/codex-worker-test-env.md`
- 이번 run의 worker는 옛 설정으로 돈다. 효과는 goldstack-v13부터 보고서에서 본다
