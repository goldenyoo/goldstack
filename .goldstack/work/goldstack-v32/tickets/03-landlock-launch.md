---
id: "03"
title: "Landlock 모드에서 codex worker·codex 리뷰·agy 리뷰를 가둬 띄운다"
blocked_by: ["02", "04"]
touches: ["src/gs/adapters.py", "src/gs/review.py", "src/gs/report.py", "src/gs/go.py", "src/gs/worker.py", "tests/test_sandbox_launch.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
`GS_SANDBOX=landlock`인 머신에서, OS 샌드박스에 기대던 세 경로를 `gs jail`(01) 안에서 띄워 그 머신에서도 codex와 agy를 쓸 수 있게 한다. `os` 모드의 명령은 바꾸지 않는다(spec 2-3, 2-4, 2-6, 2-7, 3-1).

## 완료 조건
- 모드 전달: `gs go`가 시작할 때 **주 레포**(`r.repo`)에서 `sandbox.mode`와 CLI별 `sandbox.denies(cli, cfg, repo)`를 한 번 계산해 실행 동안 쓴다. worktree에서 다시 읽지 않는다(`local.env`는 gitignore라 worktree에 없다). 어댑터(`Codex`)와 `review.reviewer_argv`에 이 값을 넘기는 인자를 더한다. 값이 없으면(옛 호출, 시험) `os` 모드다.
- 공통 가두기: 가두는 명령은 `<지금 gs의 python> -m gs.cli jail --write … --deny … -- <CLI 명령>`이다(`adapters.agy_hook_command`처럼 `sys.executable`). 쓰기 목록에는 언제나 `/dev`와 그 CLI의 홈(codex는 `CODEX_HOME` 또는 `~/.codex`, agy는 `~/.gemini`)이 들어간다. landlock 모드에서 가둔 프로세스의 환경에서 `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`, `SSH_AUTH_SOCK`을 지운다(`GH_TOKEN`은 지금처럼 틀린 값). push·gh 차단 env(`worker.guard_exports`, `review._env`)는 그대로다.
- codex worker(`Codex.command`): `-s workspace-write`, `--add-dir`, `sandbox_workspace_write.network_access=false` 대신 `-s danger-full-access`. 쓰기 목록은 worktree, `writable_dirs`(그 git 디렉터리, `objects`, `refs/heads/gs`, `logs/refs/heads/gs`), `/tmp`, `$TMPDIR`다. brief는 지금처럼 stdin, 로그 리다이렉트는 jail 밖 셸이 한다.
- codex 리뷰: `-s danger-full-access`, `-C <scratch>`. `--output-last-message`는 scratch 안의 파일로 주고, 호출이 끝나면 gs가 그 내용을 지금의 `out`(`rdir/review.txt`)으로 옮긴다(실행 디렉터리는 쓰기 목록 밖이다). 쓰기 목록은 scratch, `/tmp`이고 이 호출의 `TMPDIR`을 scratch로 둔다.
- agy 리뷰: `--sandbox`를 빼고 deny 규칙(`--settings adapters.Agy.settings()`)과 나머지 인자는 그대로 둔다. 쓰기 목록은 호출마다 새로 만든 임시 폴더(`TMPDIR`도 그곳, 호출 뒤 지운다)와 `/tmp`다. 리뷰 트리에 hook 파일은 쓰지 않는다(spec 4-2).
- 가둘 수 없으면 리뷰 없이 병합하지 않는다(spec 1-8): 아래 둘은 `transient.SandboxAbort`(04)를 올린다. 리뷰 실패(`ReviewError`)로 적는 길로 가지 않는다.
  - 리뷰 트리가 리뷰어 쓰기 경로 아래에 있다(예: 레포가 `/tmp` 아래). 리뷰어를 띄우지 않고 `리뷰 트리 <경로>가 landlock 쓰기 경로 <경로> 아래라 읽기 전용으로 가둘 수 없다`.
  - 가둔 명령(worker·리뷰)의 stderr나 로그에 줄 처음이 `jail.JAIL_FAILED`인 줄이 있다(01, 명령을 띄우지 못함). 이유는 그 줄이다. worker는 그 시도를 실패로 세지 않는다.
- `report.py`: landlock 모드로 쓴 보고서의 머리(제목 아래 요약 근처 한 줄)에 `샌드박스: landlock(네트워크 열림)`. `os` 모드면 줄이 없다. 값은 실행 시작 때 계산한 모드다.
- `tests/test_sandbox_launch.py`:
  - 어디서나: `os` 모드의 세 명령이 지금과 글자 그대로 같다. landlock 모드의 세 명령이 위 형태다(`danger-full-access`, `--sandbox` 없음, jail 앞부분, 쓰기·거부 목록. 거부 목록에 `~/.ssh`, 주 레포 `local.env`, 다른 CLI 홈이 있고 자기 홈은 없다). 지운 환경 변수. codex 리뷰 답이 scratch에서 `review.txt`로 옮겨진다(가짜 codex가 `--output-last-message`에 실제로 쓴다). 리뷰 트리가 쓰기 경로 아래면, 그리고 `JAIL_FAILED` 줄이 나오면 `SandboxAbort`이고 병합되지 않는다. 모드는 주 레포 `local.env`에서 읽고 worktree에는 없어도 landlock이다. 보고서 머리 줄 있음·없음.
  - `skipUnless(jail.abi() >= 1)`: 가짜 codex 스크립트를 jail 명령으로 띄워, worktree에 커밋할 수 있고, 거부 경로를 읽지 못하고, 리뷰 모양에서는 리뷰 트리에 쓰지 못한다(`open` 쓰기 기준. ABI 1은 경로 `truncate(2)`·`chmod`를 막지 못한다). 시험 레포와 거부 경로는 쓰기 목록 밖에 둔다.
- 맥 worker는 실제 Landlock 시험을 돌리지 못한다. 마지막 메시지에 그 사실을 적는다.

## 범위 밖
- agy worker·claude worker 가두기(범위 밖 `landlock-all-workers`)
- codex hook 두 번째 겹(범위 밖 `codex-hook-second-layer`)
- 네트워크 차단, 경로 `truncate(2)`·`chmod` 차단(범위 밖 `landlock-network`, `landlock-truncate`)

## 참고
- spec §6 pod 측정 3–5와 ABI 1 한계 측정
- 리뷰 트리 위치: `go._review_tree`(실행 디렉터리 아래). 리뷰 실패 기록: `review.py`의 `리뷰 실패(리뷰 없음, verify만으로 병합한다)`
