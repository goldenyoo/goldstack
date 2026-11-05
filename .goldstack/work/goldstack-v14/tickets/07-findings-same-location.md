---
id: "07"
title: "같은 위치 지적은 파일 하나로"
blocked_by: []
touches: ["src/gs/findings.py", "tests/test_findings_ideas.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
재시도에서 리뷰어 문장이 달라도 같은 지적이 아이디어 파일 하나로 남게 한다.

## 완료 조건
- 같은 티켓에서 파일이 같고 줄이 가까운 지적은 문장이 달라도 기존 파일과 같은 번호다. `goldstack-v11-09-1`과 `-09-3` 사례(`src/gs/check.py:24`)를 시험으로 재현한다.
- 위치가 없는 지적은 지금처럼 첫 줄로 찾는다. 다른 파일이나 먼 줄의 지적은 합치지 않는다. 사람이 첫 줄을 고친 파일도 위치로 찾는다.
- "가까운"의 줄 수는 상수 하나다.

## 범위 밖
- 판단 모델로 동일성 가리기.

## 참고
- spec 2-17
- `findings._assign`
- `.goldstack/ideas/findings-dup-after-edit.md`
