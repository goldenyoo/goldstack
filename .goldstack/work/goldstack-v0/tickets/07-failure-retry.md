---
id: "07"
title: "실패·멈춤 처리와 재시도"
blocked_by: ["04"]
model: codex
reviewer: claude
---
## 목표
멈추거나 실패한 worker 때문에 전체가 서지 않는다.

## 완료 조건
- 로그 출력도 새 커밋도 없이 정해진 시간(spec frontmatter `idle_minutes`, 기본 20)이 지나면 worker 프로세스와 pane을 끝낸다.
- 실패(종료 코드, 커밋 없음, 시간 초과, `verify` 실패, 병합 충돌)하면 한 번 재시도한다: 같은 모델, 최신 integration에서 새 브랜치·worktree, 판단 모델이 요약한 실패 로그를 brief에 붙인다.
- 두 번째 실패면 그 티켓은 failed, 그 티켓에 (간접적으로라도) 막힌 티켓은 skipped로 두고 나머지는 계속한다.
- 실패한 worktree는 지우지 않고 경로를 state에 남긴다(보고서에서 볼 수 있게).
- 시험: 가짜 worker로 "멈춤 → 시간 초과 → 재시도 성공", "두 번 실패 → 막힌 티켓 skipped, 무관한 티켓 merged", "충돌 → 최신 integration에서 재실행" 시나리오를 확인한다(시간은 시험에서 짧게 바꿀 수 있게).

## 범위 밖
- 다른 모델로 재시도(spec 4-4), 사람 호출.

## 참고
- spec §3(2-5, 3-4, 4-4)
- docs/research/pstack.md §4("by its pushes and PR activity, not its status text")
- docs/ORIGINS.md 실패 9(반응 없는 worker)
