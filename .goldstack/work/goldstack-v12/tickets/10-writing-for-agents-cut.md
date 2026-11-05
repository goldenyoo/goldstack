---
id: "10"
title: "writing-for-agents 재설명 합치기"
blocked_by: []
touches: ["skills/writing-for-agents/**"]
tier: medium
model: claude
reviewer: codex
verify: "uv run python -m unittest discover -s tests -p test_skills.py && claude plugin validate ."
---
## 목표
`writing-for-agents`의 같은 원리 재설명을 합친다. `retro`가 읽고 사람이 부르는 글이다.

## 완료 조건
- `SKILL.md` 본문이 900단어 이하다. 정보 위계·점진적 공개·뻗침을 한 묶음으로, 완료 기준·순서로 나누기를 한 묶음으로 합친다. "두 번 이긴다"처럼 효과만 말하는 문장을 지운다. 각 용어의 정의와 언제 쓰는지는 남는다.
- `SKILL-MECHANICS.md`의 모순을 고친다: Skill 도구 호출과 파일로 읽기를 구분해, 공유 참고를 파일로 읽을 수 있다고 적는다. router skill 절을 지운다.
- 출처 줄(원본 링크, MIT 고지)이 남아 `PortedSkillTest`가 통과한다.

## 범위 밖
- 상한 숫자: 티켓 12.

## 참고
- spec §7 라운드 1 검토
- `docs/guide.md`의 `/writing-for-agents` 절이 가리키는 목록과 맞춘다(문서 수정은 티켓 12)
