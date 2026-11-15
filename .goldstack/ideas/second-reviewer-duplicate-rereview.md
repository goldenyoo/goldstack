---
date: "2026-11-15"
severity: "medium"
source: "/retro goldstack-v41"
status: "taken"
issues: []
feature: "goldstack-v42"
---
두 번째 리뷰어(agy)의 fix 지적이 모두 첫 리뷰어 지적과 같은 결함인데도 재리뷰에 그 리뷰어를 다시 불러 일렬 경로가 길어진다.

- goldstack-v41 01: 리뷰 단계 725초 중 agy 723초(codex 256초), 재리뷰 단계 584초 중 agy 583초(codex 104초). agy-1은 codex-1과 같은 결함이었고 agy만 찾은 fix는 0건. 약 16분이 늘었다(retro subagent 보고).
- [반복] goldstack-v38 01도 agy-1이 codex-1과 같은 위치·결함이었다. 반면 v36에는 agy만 찾은 fix가 있었으니 첫 리뷰에서 빼자는 근거는 아니다.
- 고칠 곳 후보: 재리뷰 배정(`src/gs/go.py` `_rereview_slots`, `src/gs/review.py`). 두 번째 리뷰어의 fix 지적이 모두 첫 리뷰어 지적과 묶였으면 그 리뷰어를 재리뷰에서 빼고 첫 리뷰어가 함께 판정한다(`[review] second_reviewer_rereview = "first"`와 비슷한 동작을 자동으로).
- 관련: taken `agy-rereview-slow`(goldstack-v38, 설정 키), 범위 밖 `second-reviewer-all-code`(주제 다름).
