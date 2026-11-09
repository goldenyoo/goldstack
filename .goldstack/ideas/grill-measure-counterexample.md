---
date: "2026-11-09"
severity: "medium"
source: "/retro 세션(grill goldstack-v26~v28, overnight 2026-11-08)"
status: "taken"
issues: []
feature: "goldstack-v29"
---
grill이 실측으로 선택지를 고를 때 성공 경우만 재고, 그 안이 놓치거나 깨뜨릴 경우는 재지 않는다.

- v28 라운드 1: claude Bash 도구에서 `ZDOTDIR`+`setopt noequals`로 `echo ===; echo after`가 통하는 것만 재고 "`=` 판정 삭제"를 추천·확정했다. 그 안이 놓치는 `zsh -f -c 'echo ==='`(시작 파일을 읽지 않는 자식 셸)는 codex 검토가 찾았고 결정이 "같은 셸 판정만 건너뜀"으로 바뀌었다(v28 spec §3 3-1).
- 잘 된 쪽: v27 02·v28 01은 "실측이 기대와 다르면 코드를 바꾸지 않는다"를 완료 조건에 두었고, v28 실측에서 codex worker가 실패해 그 worker에는 판정이 남았다(`docs/research/worker-noequals.md`).

고칠 곳: `skills/grill/SKILL.md` 1단계 "사실은 직접 찾는다"에 "실측이 선택지를 가르면 그 안이 놓치거나 깨뜨릴 경우도 함께 잰다" 한 줄. 관련: [[grill-cross-family-review]]
