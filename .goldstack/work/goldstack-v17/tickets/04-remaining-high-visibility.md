---
id: "04"
title: "끝 출력에 남은 high와 건너뛴 리뷰를 보인다"
blocked_by: []
touches: ["src/gs/report.py", "src/gs/go.py", "skills/overnight/SKILL.md", "skills/go/SKILL.md", "tests/test_finding_status.py", "tests/test_overnight_skill.py", "tests/test_skills.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
사람이 보고서를 끝까지 읽지 않아도 남은 high 지적과 빠진 리뷰를 알게 한다. 판정과 종료 코드는 바꾸지 않는다.

## 완료 조건
- `gs go` 끝 출력에 `■ 남은 high 2(보고만 1 · 확인 못 함 1) · 건너뛴 리뷰: 05` 모양의 줄이 나온다. 남은 high는 상태가 보고만·미해결·수정 못 함·확인 못 함인 high 지적이다. 건너뛴 리뷰는 `건너뜀(한도)`로 끝난 리뷰의 티켓이다. 둘 다 없으면 줄이 없다.
- 보고서 마무리 줄에 같은 내용이 있다.
- 줄이 있어도 `gs go` 종료 코드와 `finish.phase`는 그대로라는 시험이 있다. `--only` 요약은 바뀌지 않는다.
- `skills/overnight/SKILL.md` 아침 표에 같은 열이 있고 `skills/go/SKILL.md` 4단계 요약이 그 줄을 보인다. `overnight` 상한 1710, 지금 1548. `go` 상한 530, 지금 477.
- 옛 state에서 심각도나 상태가 없어도 오류가 나지 않는다.

## 범위 밖
- 별도 판정으로 멈추는 일은 하지 않는다(결정 2-2). `docs/guide.md`는 티켓 06이 맡는다.

## 참고
- spec 결정 2-2, 2-3, §6. 아이디어 `report-only-high-visibility`. `report.finding_status`, `go._summary`.
