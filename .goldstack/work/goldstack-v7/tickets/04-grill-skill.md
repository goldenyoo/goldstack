---
id: "04"
title: "/grill 정비: 표에 일렬 경로·등급, 순서 이유 구분, 묶기·리뷰어·검사 기준"
blocked_by: ["01"]
touches: ["skills/grill/**", "tests/test_skills.py"]
model: claude
reviewer: codex
---
## 목표
grill이 티켓을 나눌 때 전체 시간과 등급을 함께 보게 한다.

## 완료 조건
- `skills/grill/SKILL.md`의 티켓 분해 단계가 다음을 요구한다.
  - 표에 가중 일렬 경로와 평균 동시 실행 수를 함께 보인다. 예: `일렬 경로 01→03→04 예상 110분 · 평균 동시 2.1`.
  - 티켓마다 등급(`tier`)과 이유 한 줄. 예: 문서 small, 재개 흐름 large.
  - `blocked_by`마다 이유를 "같은 파일"과 "앞 결과 필요"로 구분한다.
  - 강하게 엮인 작은 직렬 티켓은 한 장으로 묶는다.
  - 두 번째 리뷰어는 상태 전이·재개·revert 티켓에만 붙인다.
  - 티켓 `verify`는 문서·설정 티켓에만 좁게 쓰고, 코드 티켓은 전체 검증을 쓴다.
- `templates/spec.md` §5 표와 `templates/ticket.md` frontmatter가 위 항목을 담는다(티켓 `tier`, 선택 키 `verify`).
- `tests/test_skills.py`가 위 지침과 템플릿 키가 있는지 확인한다.

## 범위 밖
- `tier`·`verify`의 엔진 구현(02, 08). 이 티켓은 지침과 템플릿만 고친다.
- `/go`(06), `/adopt`.

## 참고
- spec §3 2-3, 2-6 a, 2-7, 2-16.
- 아이디어 `.goldstack/ideas/e2e-time-reduction.md` "grill 정비". 글쓰기는 `skills/writing-for-agents/SKILL.md`를 따른다.
