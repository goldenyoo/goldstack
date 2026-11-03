---
id: "06"
title: "gs clean과 verified 뒤 자동 정리"
blocked_by: ["05"]
model: codex
reviewer: claude
---
## 목표
끝난 feature의 작업 폴더와 브랜치가 쌓이지 않게 한다.

## 완료 조건
- 마무리가 `verified`로 끝나면 gs가 그 feature의 integration worktree(`run/wt/integration`), 로컬 `gs/<f>/integration`, 원격 `gs/<f>/integration`을 지운다. 지우기 실패는 경고만(결과 불변). `reverted`·실패면 남긴다(시험).
- `gs clean <feature> [--force]`: `run/wt/*` 전부(git worktree remove, 미커밋 변경이 있어도 지움 — 출력에 그 경로를 보임), `gs/<f>/*` 로컬 브랜치, 원격 `gs/<f>/*` 브랜치를 지운다. `run/state.json`과 `run/NN/*` 기록은 남긴다. 출력 `지움: worktree N, 로컬 브랜치 N, 원격 브랜치 N · 실행 기록은 남김`(시험).
- 같은 feature의 `gs go`가 돌고 있으면(lock) 거부. 마무리 phase가 `verified`·`reverted`가 아니면 `--force` 없이 거부(시험).
- 정리 뒤 같은 feature로 `gs go`를 돌려도 오류 없이 "이미 끝남"(또는 지금과 같은 재개 판단)으로 끝난다(시험).
- 원격 브랜치는 config `git.remote`로 지운다.

## 범위 밖
- 실행 기록(`run/` 로그) 지우기

## 참고
- 자동 정리는 v3가 넣은 병합 뒤 base 보고서 push(`base_report_tried`)가 끝난 다음에 한다(integration worktree를 보고서 커밋에 쓴다).
- spec §3 1-5, 2-2, §6 worktree·브랜치. touches: `src/gs/clean.py` `src/gs/finish.py` `src/gs/cli.py` `tests/test_clean.py`
