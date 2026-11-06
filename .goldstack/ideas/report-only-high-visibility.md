---
date: "2026-11-06"
severity: "high"
source: "/retro goldstack-v12, v13, v14, v15"
status: "open"
issues: []
feature: ""
---
완료 조건을 못 채운 high 지적이 `보고만`으로 병합되어도 `gs go`는 종료 0, `/overnight` 판정은 `verified`라 사람이 보고서를 읽어야 안다.

**근거**: goldstack-v15 03의 목표인 "재발 시 다시 열기"는 지문에 gs 버전이 들어 있어 실제 경로에서 돌지 않는다(`goldstack-v15-03-1`, `feedback._fingerprint`). 첫 리뷰가 high로 냈고 재리뷰도 다시 지적했지만 판단이 "사람이 정할 일"이라 병합됐다. `/overnight` 아침 표에는 `verified`만 보인다.

**덧붙임**: `docs/guide.md`에 "지문에 gs 버전이 들어 있다"가 이미 있었는데 grill과 codex 더블 체크가 모두 놓쳤다. 그러므로 grill 쪽 글을 늘리기보다 끝에서 보이게 한다.

**제안**: `report.py`의 마무리 줄과 `gs go` 끝 출력에 `보고만 high N`을 넣는다. `skills/overnight/SKILL.md` 아침 표에 같은 열을 두고 `/go` 4단계 요약에도 보인다. 이 값이 있어도 `verified`는 바꾸지 않을지, 별도 판정으로 멈출지는 grill에서 정한다.
