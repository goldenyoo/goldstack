---
date: "2026-11-15"
severity: "low"
source: "issue #75 (goldstack-v42 grill 라운드 1-4)"
status: "open"
issues: [75]
feature: ""
---
리뷰어 샌드박스 안에서 `gs jail`(Landlock)이 돌지 않아(`landlock 실패: … /usr/bin/python3: Permission denied`) jail 관련 회귀를 재검증하지 못한다. 그 사실이 보고서 "남은 위험"에 오르지 않았다.

- 출처: GitHub issue #75 field-report(gs 0.2.16, pod 레포, 1회 확인). 본문은 이 세션이 다시 확인하지 않았다.
- 제안(issue): 리뷰어 샌드박스 안 중첩 landlock에 필요한 읽기·실행 루트를 허용한다. 안 되면 리뷰 결과에 "시험 미실행(이유)" 필드를 두고 보고서 "남은 위험"에 올린다.
- 리눅스 전용이라 맥미니에서 재현하지 못한다. 뒤 절반(남은 위험에 올리기)은 플랫폼과 무관하다.
