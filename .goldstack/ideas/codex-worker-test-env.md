---
date: "2026-11-05"
severity: "high"
source: "/retro goldstack-v11"
status: "taken"
feature: "goldstack-v12"
---
codex worker가 sandbox에서 시험을 돌리지 못해, 돌려 보지 않은 코드를 커밋하고 gs 검증에서야 실패한다.

**근거(goldstack-v11 worker.log)**:
- codex 시도 7번 전부(01 1·2차, 05, 09 1–4차) `uv`가 막혔다. 기본은 `~/.cache/uv` 쓰기 차단이고, `UV_CACHE_DIR=/tmp/...`로 돌리면 `hatchling` 다운로드가 DNS에서 막힌다.
- 시도마다 우회법을 새로 찾았다: 캐시에서 `hatchling` 복사, `PYTHONPATH=src`(45건 안팎 오류), `.venv/bin/python`, `UV_NO_BUILD_ISOLATION=1`, uv가 설치한 python 절대 경로.
- 우회해도 전체 검증은 localhost bind와 `ps` 권한 오류로 한 번도 완주하지 못했다.
- 비용: 01 1차 수정 worker가 커밋한 시험이 `FileNotFoundError`로 떨어져 검증 17분과 재시도를 썼다. 09 3차 `fix2`는 시험을 못 돌렸고 `grill` 글 451단어(상한 450)로 떨어졌다.
- 반복: goldstack-v7 보고서("hatchling 다운로드 중 sandbox의 DNS 차단"), goldstack-v9 보고서("Failed to initialize cache", "전체 verify는 hatchling 다운로드에서 중단"). v10 sandbox 안내는 worker가 따랐지만 이 비용을 줄이지 못했다.

**제안**:
- `.goldstack/config.toml`의 `[worktree] setup = "uv sync --locked"`로 sandbox 전에 `.venv`를 만든다.
- `.goldstack/profile.md`에 sandbox에서 돌릴 수 있는 좁은 시험 명령 한 줄을 적는다.
- 범위 밖 `verify-worker-key`의 다시 볼 조건("sandbox 네트워크 실패가 재작업으로 계속 나오면")이 충족됐으니 함께 본다.

**먼저 잴 것**: setup만으로 sandbox 안의 `uv run`이 풀리는지는 재지 않았다. 01 2차에서 `UV_NO_SYNC=1`과 `PYTHONPATH`를 함께 줘 통과한 기록만 있다. codex sandbox에서 직접 재고 정한다. 다른 레포에 맞는 값은 `/adopt`가 정할 일이다.

관련: [[e2e-time-reduction-2]]의 "worker의 전체 시험 제거"
