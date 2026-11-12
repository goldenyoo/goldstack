---
date: "2026-11-10"
severity: "low"
source: "/retro goldstack-v31"
status: "open"
issues: []
feature: ""
---
보고서의 대부분이 통과한 검증의 출력이라 회고·grill·요약 단계가 읽을 때마다 토큰을 낭비한다.

- goldstack-v31 report 921줄 중 검증 출력(L220–895)이 약 675줄이고, 대부분 `claude plugin validate` 문구가 7번 반복된 것이다.
- goldstack-v30: 614줄 중 355줄.

고칠 곳: `src/gs/report.py`. 통과한 검증은 종료 코드와 unittest 합계만 남기고 전체 로그는 실패에만 붙인다.
