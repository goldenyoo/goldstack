---
date: "2026-11-10"
severity: "medium"
source: "/retro goldstack-v31"
status: "open"
issues: []
feature: ""
---
코드 티켓 4개 중 3개가 안쪽 함수만 고치고 최종 관측점을 시험하지 않아 같은 유형의 리뷰 지적을 받았다.

- goldstack-v31 02: 트리가 바뀐 뒤에도 재시도. 03: `finish._run`이 `_update`를 건너뜀. 04: `compose`가 시간 초과 표식을 지움. 셋 다 리뷰가 잡아 수정 1회씩.
- 02 worker는 "모든 분기 제거가 시험을 실패시킨다"를 [확인]으로 적었지만, 변이 대상에서 replay 호출부와 config 분기 4개가 빠졌다(`run/retro-log.md` L176–177). agy가 잡았다.

고칠 곳: 티켓 완료 조건에 최종 관측 지점과 그곳의 시험 하나를 적게 한다. brief는 변이 대상이 diff의 새 분기와 호출 지점을 모두 덮게 요구한다.
