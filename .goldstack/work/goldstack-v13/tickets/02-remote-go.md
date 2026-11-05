---
id: "02"
title: "`gs remote go <머신> <feature>`"
blocked_by: ["01"]
touches: ["src/gs/remote.py", "src/gs/herdr.py", "src/gs/cli.py", "tests/test_remote.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
`/go`를 원격 머신의 Claude 세션에서 끝까지 돌린다. worktree, 시험, 실행 기록은 모두 원격에 있다.

## 완료 조건
- `gs remote go <머신> <feature>`가 먼저 `gs remote check`와 같은 검사를 돌리고, 빠진 것이 있으면 아무것도 띄우지 않고 종료 1이다.
- grill 커밋이 원격 base에 push되어 있지 않으면 거부한다(`/go` 2단계와 같은 조건).
- 원격 레포에서 `git pull --ff-only`를 하고, 원격 pane에 `claude`를 띄워 `/go <feature>`를 보낸다. 이미 그 feature의 `gs go`가 원격에서 돌고 있으면 띄우지 않고 그 사실을 말한다.
- 로컬 터미널이 끊겨도 원격 세션이 살도록 pane을 띄우고 바로 돌아온다. workspace·pane id와 상태 보는 명령을 출력한다.
- `gs remote status <머신> <feature>`가 원격의 `gs status`를 보여 준다.
- 가짜 herdr로 시험한다: 정상, 검사 실패, push 안 됨, 이미 실행 중, pane 생성 실패. 비밀 값을 pane에 보내지 않는다.

## 범위 밖
- worker만 다른 머신에서 돌리기: `out-of-scope/remote-machines.md`.
- 원격 feature 잇기: `.goldstack/ideas/overnight-queue.md`.
- goldHUD에서 원격 상태 보기.

## 참고
- spec 2-9
- `skills/go/SKILL.md` 2단계, `go._require_committed`
- `.goldstack/ideas/remote-go-run.md`의 아직 모르는 것은 보고서에 사람 확인으로 남긴다
