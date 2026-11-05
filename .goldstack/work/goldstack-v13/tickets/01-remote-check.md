---
id: "01"
title: "`gs remote check <머신>`"
blocked_by: []
touches: ["src/gs/remote.py", "src/gs/cli.py", "tests/test_remote.py", ".goldstack/local.env.example"]
tier: medium
model: codex
reviewer: claude
---
## 목표
맥북이 바쁠 때 원격 머신에서 돌릴 수 있는지 시작 전에 알려 주는 명령을 만든다.

## 완료 조건
- `gs remote check <머신>`이 항목마다 통과/빠짐과 고칠 방법을 한 줄씩 보이고, 빠진 것이 있으면 종료 1이다.
- 항목: `herdr machine status`의 연결, 원격의 `gs`, goldstack 플러그인, `gh auth status`, `claude auth status`, `codex login status`, 디스크 여유, 레포 경로, `.goldstack/local.env` 유무(값은 읽지 않는다), 원격 레포가 이 feature의 grill 커밋을 받을 수 있는지.
- 레포 경로는 `.goldstack/local.env`의 `GS_REMOTE_REPO_<머신>`이다. 없으면 그 키를 쓰라고 안내한다. `.goldstack/local.env.example`에 설명이 있다. 코드에 `mac_mini`를 적지 않는다.
- gs·플러그인 버전이 로컬과 다르면 빠짐이고 원격 `gs self-update`를 안내한다. Claude Code·Codex·agy 버전 차이는 경고다.
- `herdr`가 없거나 저장된 머신이 아니면 오류와 함께 `docs/guide.md`의 tmux 절을 안내한다.
- 머신 연결은 `herdr machine status`의 그 머신 줄로 판단한다. 다른 머신이 실패해도 종료 1이니 종료 코드로 판단하지 않는다. 시험에 이 경우를 넣는다.
- 원격 명령은 `herdr --machine <머신>`의 `workspace create`, `pane run`(또는 `pane send-text`), `pane wait-output`, `pane read`로 돌린다. 끝 표시 줄로 출력을 잘라 읽고, 제한 시간이 있다. 시험은 `HERDR_BIN_PATH`의 가짜 herdr로 한다: 전부 통과, 항목별 빠짐, 연결 실패, 버전 차이, 시간 초과.

## 범위 밖
- 실제 맥미니 실행은 사람이 확인한다(spec 2-14).
- `local.env` 복사: `out-of-scope/remote-env-copy.md`.
- SSH·tmux 직접 지원: `out-of-scope/remote-ssh-tmux.md`.

## 참고
- spec 2-9–2-14
- `.goldstack/ideas/remote-go-run.md`
- `src/gs/herdr.py`
