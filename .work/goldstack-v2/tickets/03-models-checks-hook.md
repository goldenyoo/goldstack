---
id: "03"
title: "모델·시간 제한 config화, CLI 사전 확인, GitHub 경고, hook 정리"
blocked_by: ["02"]
model: codex
reviewer: claude
---
## 목표
남은 하드코딩(모델 이름, 리뷰·판단 시간 제한)을 config로 옮기고, 실행 전에 필요한 CLI와 원격을 확인하며, worker 차단 hook을 다른 레포 환경에 맞게 다듬는다.

## 완료 조건
- 판단 모델(실패 요약·리뷰 분류·보고서), claude reviewer, agy worker·reviewer 모델, codex 모델(비면 `--model`을 넣지 않음)이 config `models.*`에서 온다. 코드에 `"opus"`, `gemini-4-argon-high` 문자열이 남지 않는다(시험: config 값을 바꾸면 만들어지는 명령 인자가 바뀐다).
- 리뷰·판단·실패 요약 시간 제한이 config `timeouts.*`에서 온다(시험).
- `gs check`가 범위 안 티켓의 `model`·`reviewer`에 쓰인 CLI(`claude`, `codex`, `agy`)와 `gh`, `git`이 PATH에 있는지 확인하고, 없으면 오류로 그 이름을 보인다. 시험은 PATH를 바꿔 확인한다.
- `git.remote`의 URL이 GitHub(`github.com`)가 아니면 `gs check`가 경고한다: `경고: 원격 <url>은 GitHub가 아니다. PR·병합은 gh로만 한다`(시험).
- worker 차단 hook이 `.goldstack/local.env` 읽기를 막는다(Read 도구, `cat`, `grep` 등, worktree 안·주 레포 경로 모두. 시험).
- plugin hook 명령이 `gs` CLI가 PATH에 없을 때 오류를 내지 않는다: worker가 아니면(GS_ROLE 없음) 조용히 통과하고, worker인데 `gs`가 없으면 막는다(fail-closed). `hooks/hooks.json`의 `hooks` 항목만 바꾸고 다른 키는 건드리지 않는다(시험: PATH에 gs 없는 환경에서 hook 명령 종료 코드).
- 기존 시험이 모두 통과한다.

## 범위 밖
- GitLab 등 다른 원격 지원(`.out-of-scope/gitlab-support.md`)
- 진행 기록(04), mod(05, `hooks/hooks.json`의 `modules`), 텔레그램(06), README(08)

## 참고
- spec §3(1-6), §4 "config.toml"
- 지금 모델·시간 상수: `src/gs/review.py`, `src/gs/failure.py`, `src/gs/report.py`, `src/gs/adapters.py`. hook: `src/gs/hook.py`, `hooks/hooks.json`
