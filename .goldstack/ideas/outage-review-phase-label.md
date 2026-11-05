---
date: "2026-11-05"
severity: "low"
source: "goldstack-v9 06 agy 리뷰(Claude가 재현)"
status: "open"
feature: ""
---
끊김 중에 리뷰 호출이 끝나고 티켓 head가 움직였으면, 두 번째 리뷰 준비를 끊김 중에 해서 단계가 `network`가 아닌 `review`로 보이고 옛 head를 리뷰한다.

**근거(2026-11-05 재현)**: 끊김 중 들어온 커밋이 두 번째 리뷰에서 빠지고 `병합 전 대조: head …는 리뷰하지 못했다`가 기록된다. worker가 끝난 뒤 브랜치가 움직여야 나는 드문 경우이고, 못 본 사실은 보고서에 남는다.

**제안(S)**: `_review_step`이 끊김 중이면 `_resume_flow`도 미룬다. 끊김의 끝에서 최신 head를 정한다.
