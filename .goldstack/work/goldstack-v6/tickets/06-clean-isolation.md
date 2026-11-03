---
id: "06"
title: "gs clean이 state의 남긴 worktree도 비움, 격리 실패를 보고서에"
blocked_by: ["02"]
touches: ["src/gs/clean.py", "src/gs/adapters.py", "src/gs/report.py", "tests/test_clean_state.py"]
model: codex
reviewer: agy
---
## 목표
`gs clean` 뒤 같은 feature의 `gs go`가 브랜치를 다시 만들지 않게 하고, worker 플러그인 격리가 안 된 실행을 보고서에서 알 수 있게 한다.

## 완료 조건
- `gs clean`이 지운 worktree를 state의 `kept_worktrees`(와 `failed_worktrees` 등 worktree 경로 목록)에서도 뺀다. 정리 뒤 같은 feature `gs go`가 "이미 끝남"으로 끝나고 원격 `gs/<f>/integration`을 다시 만들지 않는다(시험: kept worktree가 있는 verified feature, reverted feature).
- claude worker의 플러그인 격리를 못 했을 때(`claude plugin list` 실패 등) worker는 지금처럼 뜨되(fail-open), 그 티켓 결과와 보고서 남은 위험에 `플러그인 격리 못 함: <이유>`가 나온다(시험).

## 범위 밖
- 격리 실패 시 worker를 띄우지 않기(spec 1-7 d에서 뺌)

## 참고
- spec §3 1-7 c·d, §6 아직 남음 (c)(d)
