---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 Codex 리뷰(Claude가 재현)"
status: "taken"
feature: "goldstack-v8"
---
`gs-ticket:` 표시를 부분 문자열로 찾아, 재개할 때 실행하지 않은 티켓이 merged가 될 수 있다.

**재현(2026-11-04, 임시 레포에서 같은 git 명령)**: `go._already_merged`의 `git log --fixed-strings --grep="gs-ticket: f/01"`이 `gs-ticket: f/010` 커밋에 걸린다. 본문에 `gs-ticket: f/02`라고 적은 일반 커밋에도 걸린다.

**결과(코드 추적)**: `_resume_merged`가 그 티켓을 구현·리뷰·검증 없이 merged로 되돌린다. `feature.py`는 id와 파일 이름 접두어만 맞춰 보므로 `01`·`010` 조합을 막지 않는다. 두 자리 id만 쓰면 첫 경우는 드물지만, 둘째 경우는 worker가 커밋 메시지에 그 문구를 쓰면 생긴다.

**제안(S)**: 병합 커밋의 트레일러 줄을 정확히 파싱해 feature·id 전체를 비교한다. 접두어가 겹치는 id와 본문에만 문구가 있는 커밋의 재개 시험을 더한다. Codex는 high로 냈지만 조건이 드물어 medium으로 낮췄다.
