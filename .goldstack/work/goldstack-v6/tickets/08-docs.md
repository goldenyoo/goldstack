---
id: "08"
title: "문서: 재리뷰와 지적 상태, setup 경고, 원격 설치 반영"
blocked_by: ["01", "02", "03", "04", "05", "06", "07"]
touches: ["README.md", "docs/guide.md", "docs/internals.md"]
model: claude
reviewer: codex
---
## 목표
v6에서 바뀐 리뷰 흐름·보고서·설정을 문서에 반영한다.

## 완료 조건
- `docs/guide.md`: 리뷰 → 수정 → 재리뷰 → 2차 수정 흐름과 보고서 지적 상태 5가지(뜻, 사람이 볼 것), `timeouts.rereview_minutes`, `timeouts.checks_grace_seconds`, setup 추적 파일 경고와 lock을 바꾸지 않는 명령 권고, 재개가 verified로 끝나면 그 실행이 멈추고 남은 티켓은 다음 `gs go`라는 점. config 키 표 갱신.
- `docs/internals.md`: 재리뷰 state 필드, agy 호출 세기(재리뷰 포함), 마무리 순서(base 보고서 → base 합치기 → 멈춤), squash 되살림 식별, CI grace.
- README의 "고쳤지만 재리뷰 없음" 같은 옛 설명이 남지 않는다(`grep -rn "재리뷰 없" README.md docs/`가 의도한 곳만). 07이 쓴 설치 절은 그대로.
- 문서 속 명령·키가 실제와 맞다.

## 범위 밖
- 코드 변경 없음

## 참고
- spec §3 전체
