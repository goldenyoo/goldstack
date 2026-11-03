# goldstack

Claude Code로 프로젝트를 진행하는 개인 운영 kit. 처음에 grill로 깊게 정렬하고, `go` 한 번 뒤에는 구현 완료와 main 병합까지 알아서 진행한다.

- 철학: [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first", "never block on the human".
- 모델: Claude · codex · gemini를 티켓마다 고르고, 리뷰는 항상 다른 계열이 한다. herdr pane에서 worker를 보이게 돌린다.
- 상태: 레포 안 markdown 파일(`.work/<feature>/spec.md`, `tickets/NN.md`)과 git.

시작 배경과 요구사항은 [docs/ORIGINS.md](docs/ORIGINS.md), 참고한 kit 분석은 [docs/research/](docs/research/)(pstack, mattpocock/skills, 비교표).

## 설치와 사용
```sh
uv tool install --reinstall .   # 고정 복사로 설치. main을 받은 뒤 다시 실행한다
gs check <feature>              # .work/<feature>/의 spec과 티켓 그래프 검사
gs check <feature> --only 03,04 # 일부 티켓만 기준으로 순서·frontier 계산
gs go <feature> [--only 03,04]  # 티켓을 worker에 맡기고 integration에 모아 PR을 연다
uv run python -m unittest discover -s tests   # 검증 명령
```

`gs go`(02 최소형): 위상 순서로 하나씩, worker마다 herdr 새 탭에서 `claude -p`(headless)를 돌린다.
worker는 `gs/<feature>/NN` worktree에서 커밋하고 끝나며, gs가 검증을 다시 돌려 통과한 것만
`gs/<feature>/integration`에 병합한다. 끝나면 integration을 push하고 PR을 연다(병합은 08부터).
실행 흔적은 `.work/<feature>/run/`(gitignore): `NN/brief.md`, `NN/run.sh`, `NN/worker.log`, `NN/verify.log`, `wt/`.

바꿔 끼우는 곳(시험 seam): `GS_RUNNER=subprocess|herdr`(기본: herdr 안이면 herdr), `GS_WORKER_CMD`(worker 셸 명령),
`GS_GH`(gh 경로).
