---
date: "2026-11-06"
severity: "medium"
source: "/retro goldstack-v12, v13, v14, v15"
status: "open"
issues: []
feature: ""
---
고친 코드를 되돌려도 통과하는 시험이 반복된다. worker가 새 시험의 실패를 직접 보게 한다.

**근거**:
- goldstack-v15 06: 첫 리뷰가 "수정을 지워도 통과한다"(high)고 지적했고, 고치며 더한 시험도 재리뷰에서 같은 지적(medium, `goldstack-v15-06-6`)을 받았다.
- goldstack-v15 04: 가짜 리뷰어 답이 없어 `not json`으로 우연히 통과하며 2차 수정 결함을 가렸다(agy 지적).
- goldstack-v15 03: mock 버전이 지문 결함을 가렸다.
- goldstack-v14 보고서에도 같은 지적이 있다.
- 반대 사례: opus worker는 스스로 변조 시험을 만들었다. v15 02는 14개 중 3개가 안 잡히는 것을 보고 `TestCase.fail`을 덮어쓴 자기 실수를 찾았다. 하기도 하고 안 하기도 하는 일이다.

**제안**: `worker.write_brief`의 지시에 "버그를 고치면 고친 곳을 잠깐 되돌려 새 시험의 실패를 본다"를 넣는다. 재리뷰 지시에도 같은 기준을 넣을지 grill에서 정한다. 시간을 얼마나 더 쓰는지는 재지 않았다.
