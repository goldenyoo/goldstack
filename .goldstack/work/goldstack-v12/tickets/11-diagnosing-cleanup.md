---
id: "11"
title: "diagnosing-bugs 독려·중복 줄이기"
blocked_by: []
touches: ["skills/diagnosing-bugs/**"]
tier: small
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
`diagnosing-bugs`의 독려와 중복 확인을 줄인다. 규율은 그대로 둔다.

## 완료 조건
- 본문이 950단어 이하다. "이것이 이 skill의 전부다", "90% 잡혔다", "초능력", "50%로 나는 버그는 디버깅할 수 있고 1%는 못 한다"가 없다.
- 1·2단계에 흩어진 확인을 한 관문으로 합친다: 실제 증상을 잡는 명령을 돌려 red를 보고, 재현율을 확인하고, 최소화한다. 정확한 증상 확인, 최소화, 원래 시나리오 재검증은 그대로 남는다.
- 5단계의 "다음 단계를 위해 표시한다"가 받는 곳이 있도록 6단계나 그 문장을 고친다.
- `scripts/hitl-loop.template.sh`의 `ERRORED` 등 관찰값을 agent가 판정값으로 읽는다고 적어, red의 뜻이 정해진다. 로그인과 관찰을 나눈 예시는 남는다.
- 출처 줄이 남는다.

## 범위 밖
- 상한 숫자: 티켓 12.

## 참고
- spec §7 라운드 1 검토
