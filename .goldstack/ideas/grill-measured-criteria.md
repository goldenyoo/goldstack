---
date: "2026-11-14"
severity: "medium"
source: "/retro goldstack-v39"
status: "taken"
issues: []
feature: "goldstack-v40"
---
grill이 정한 수치 완료 기준이 두 가지로 샌다: 정확성 조건과 부딪힐 때 우선순위가 없어 수정을 더 돌고, 측정형 기준을 worker 혼자 재서 아무도 다시 확인하지 않는다.

- goldstack-v39 04: 완료 조건 "`_tree_state`는 git 2회 이하"와 "옛 구현과 같은 값"이 reftable 레포에서 부딪혔다. 1차 수정 worker는 "reftable에서 기존 반환값과 git 2회 제한을 함께 만족하는 수정안을 확보하지 못했습니다"(`run/04/1/rereview1-claude/worker-last.txt`)라고 쓰고 부분 커밋했다. 2차 수정에서 3회를 허용해 풀었다. 수정 두 번 514초·553초, 약 18분(retro subagent 보고).
- goldstack-v39 04: 완료 기준 "git 호출 9872 → 8700 이하"의 근거가 worker가 잰 8630회뿐이었고, gs·리뷰어가 다시 재지 않았다(보고서 남은 위험). grill 세션이 병합 뒤 main(b8c0d76)에서 spec §4 shim으로 다시 재 8630회를 확인했다(2026-11-14).
- 고칠 곳: `skills/grill/templates/spec.md`·`ticket.md` 안내.
  - 수치 상한을 적을 때 정확성 같은 다른 조건과 부딪히면 어느 쪽이 우선인지 함께 적는다.
  - 측정형 기준은 시험이나 티켓 `verify`에 넣어 기계로 확인하게 하고, 넣을 수 없으면 리뷰 지시에 재측정을 넣는다.
