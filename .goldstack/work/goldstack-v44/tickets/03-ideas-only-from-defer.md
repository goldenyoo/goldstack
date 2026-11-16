---
id: "03"
title: "리뷰 지적의 아이디어 파일은 재현된 미수리 결함만 만든다"
blocked_by: []
after: ["02"]
touches: ["src/gs/findings.py", "src/gs/state.py", "src/gs/finish.py", "tests/test_findings_ideas.py", "tests/test_judge_scope.py", "tests/test_go_review_retry.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
마무리가 리뷰 지적을 `.goldstack/ideas/` 파일로 자동 등록하는 범위를 줄인다. 지금은 "보고만" high·medium 지적(2차 재리뷰의 새 지적 포함)과 재현된 미수리 결함이 파일이 된다. 재현된 미수리 결함만 남긴다. "보고만" 지적은 보고서에 그대로 남아 사람이 회고에서 고른다(spec §6, 결정 1-3).

## 완료 조건
- `findings._target`이 상태가 `재현된 미수리`(`report.DEFERRED`)인 지적만 고른다. 그 뒤로 쓰이지 않는 상수(`findings.SEVERITIES`, `REPORT_ONLY`)는 지운다. `findings.py` 머리말·docstring, `state.py`의 `idea_number` 설명, `finish.py` 머리말의 "보고서 커밋에는 보고만 high·medium 지적의 아이디어 파일이 함께 들어간다" 문장을 새 범위로 고친다. `finish.py`에서 고치는 것은 이 문장뿐이다.
- 시험으로: 한 실행에 "보고만" high 지적 하나와 재현된 미수리 지적 하나가 있으면 아이디어 파일은 재현된 미수리 것 하나만 생긴다(`severity: high`, 본문에 원래 심각도). 최종 관측 지점은 보고서 커밋에 든 `.goldstack/ideas/` 파일 목록이다. 이 시험은 `_target`을 옛 조건으로 되돌리면 실패해야 한다.
- "보고만" 지적에서 아이디어 파일이 생기기를 기대하던 시험은 지우거나 "파일이 생기지 않는다"로 고친다.
- 그대로인 동작: 재시도로 버려진 시도의 지적 파일 닫기(`_close_stale`), 파일 번호 고정(`idea_number`), base로 옮기기(`copy_to_base`), base 검증 건너뜀이 아이디어 파일을 허용하는 것(`findings.paths`). 이 동작들을 보는 기존 시험은 단언을 그대로 두고, 파일을 만드는 지적 fixture만 재현된 미수리(`action=review.DEFER`)로 바꾼다(`tests/test_findings_ideas.py`의 `finding()` 기본값은 `review.REPORT`다).
- 레포에 이미 있는 아이디어 파일은 그대로 둔다.

## 범위 밖
- 보고서의 지적 상태와 표시(`report.finding_status`). 그대로다.
- `gs backlog`, `/retro`, `/idea`.
- 문서와 CHANGELOG(05).

## 참고
- spec §3 결정 1-3, §6.
- `docs/guide.md`의 "보고만 지적은 아이디어 파일로 남는다" 문단이 지금 동작의 설명이다.
