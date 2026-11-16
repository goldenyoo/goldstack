---
id: "04"
title: "이 레포 config: 두 번째 리뷰어(agy)를 재리뷰에 부르지 않는다"
blocked_by: []
touches: [".goldstack/config.toml", "tests/test_config.py", "tests/test_agy_config.py", "tests/test_second_reviewer_rereview.py", "tests/test_second_reviewer_overlap.py", "tests/test_rereview_report_findings.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
이 레포의 `[review] second_reviewer_rereview`를 `"first"`에서 `"none"`으로 바꾼다. agy 1차 재리뷰는 goldstack-v43에서 355초·454초를 쓰고 새 지적이 0건이었다(goldstack-v41 01도 583초, 0건). agy가 첫 리뷰에서 낸 지적의 해소는 첫 리뷰어의 재리뷰가 판정한다. 지금 2차·수리 재리뷰가 가는 길과 같다.

## 완료 조건
- `.goldstack/config.toml`에 `second_reviewer_rereview = "none"`이 있고, 그 위 주석이 새 값의 뜻과 이유(goldstack-v44)를 한 줄로 말한다.
- 리뷰어가 다시 돌린다: 레포 루트에서 `gs config review.second_reviewer_rereview`가 `none`을 낸다.
- touches의 시험 파일 다섯은 이 키 이름을 쓰는 시험이다. 이 레포의 값을 단언하는 시험은 없으니(grill이 확인) 고치지 않고, 돌려서 통과를 본다.
- 전체 검증이 통과한다.

## 범위 밖
- `second_reviewer_rereview`의 코드와 기본값(`all`). 다른 레포의 동작은 그대로다.
- 첫 리뷰의 두 번째 리뷰어. 그대로 부른다.

## 참고
- spec §3 결정 1-1.
- `.goldstack/ideas/agy-first-rereview-idle.md`: 측정.
