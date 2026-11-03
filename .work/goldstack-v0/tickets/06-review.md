---
id: "06"
title: "다른 계열 리뷰와 수정 1회"
blocked_by: ["04", "05"]
model: claude
reviewer: codex
---
## 목표
티켓이 integration에 들어가기 전에 다른 계열이 그 티켓 diff를 리뷰하고, 수정은 한 번만 한다.

## 완료 조건
- worker가 성공하면 `reviewer` 모델에 그 티켓 diff(merge-base 기준), 티켓, spec 경로를 주고 리뷰를 받는다. 출력은 고정된 JSON 형식(지적마다 심각도, 위치, 주장, 근거)이다.
- `reviewer`가 `model`과 같은 계열이면 실행을 거부한다.
- 판단 모델(매번 새 `claude -p`)이 지적을 fix(고칠 것)와 report(보고만)로 나눈다. 근거 없이 취향인 지적은 report로 간다.
- fix가 있으면 같은 구현 모델로 새 worker를 한 번 띄운다(지적 첨부). 그 뒤 재리뷰는 없고 `verify`만 돈다.
- 남은 지적은 state에 남아 08 보고서에 들어간다.
- 시험: 가짜 reviewer와 가짜 판단 모델로 "fix 지적 → 수정 1회 → 병합", "report만 → 바로 병합", "같은 계열 → 거부"를 확인한다.

## 범위 밖
- feature 끝 전체 리뷰, 리뷰 반복.

## 참고
- spec §3(2-3, 2-4, 3-5)
- docs/research/mattpocock-skills.md §5(code-review: "Do not run it in a loop until it comes back clean")
- docs/research/pstack.md §5(작성자 ≠ 검증자, 증명된 지적만)
- docs/ORIGINS.md 실패 6(리뷰가 끝나지 않음)
