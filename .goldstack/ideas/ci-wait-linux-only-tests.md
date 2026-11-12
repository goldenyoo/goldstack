---
date: "2026-11-12"
severity: "high"
source: "/retro goldstack-v32"
status: "open"
issues: []
feature: ""
---
리눅스에서만 도는 시험이 한 번도 돌지 않은 채 PR이 병합됐다. 범위 밖 `linux-ci-blocking`(`git.wait_checks = true`)을 다시 본다.

- goldstack-v32 PR #56: 생성 2026-11-12T06:50:44Z, 병합 06:50:49Z(5초 뒤). 그때 CI `tests`(ubuntu)는 `IN_PROGRESS`였다(`gh pr view 56 --json mergedAt,createdAt,statusCheckRollup`).
- 티켓·integration 검증은 모두 macOS에서 돌았다. 실제 Landlock 시험 9개는 매번 skip이다(`run/finish/integration-verify.log`의 `OK (skipped=7)`·`OK (skipped=2)`, `test_jail`과 `test_sandbox_launch`).
- spec 결정 3-3은 시험을 두 층(어디서나 + CI 리눅스 실제 Landlock)으로 정했다. 두 번째 층은 병합 뒤에야 돌았으니 병합 관문이 아니었다.
- 이 파일을 쓸 때 그 CI 실행(43170999523)은 아직 진행 중이라 결과는 확인하지 못했다.
- `linux-ci-blocking`의 다시 볼 조건은 "리눅스 시험이 안정적으로 초록이 되면"이다. `profile.md`는 CI가 PR #16(2026-11-05) 이후 통과 중이라고 적는다.

고칠 곳: 이 레포 `.goldstack/config.toml`의 `git.wait_checks`(지금 `false`, `timeouts.checks_minutes` 기본 60). CI 한 번이 약 20분이라 실행마다 그만큼 늘어난다. 맥 worker는 리눅스 실패를 재현하지 못하니 CI가 빨갛게 끝났을 때 멈추는 길(범위 밖 `ci-fix-tickets`)도 함께 정한다.

근거는 이 세션이 `gh`와 `run/` 로그로 직접 확인했다.
