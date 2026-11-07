---
date: "2026-11-07"
severity: "high"
source: "/retro goldstack-v21"
status: "open"
issues: []
feature: ""
---
보고서에 실패한 시험 이름이 없다. 병렬 출력에 실패가 묻혀 끝부분만 실으면 전부 `OK`로 보인다.

- v21 `report.md`에서 `test_revert_landed`는 0건이다. `run/finish/main-verify.log`의 실패는 521줄 중 262줄에 있고, 끝부분은 모두 `OK`에 `종료 코드: 1`이다.
- 반복: v17의 "실패한 시험 줄이 기록에 없다".

고칠 곳: 보고서의 verify 발췌. 끝부분과 별도로 `^(ERROR|FAIL):` 블록을 뽑아 싣는다. 시험 러너를 가정하지 않게 패턴을 config로 뺄지 함께 정한다.
