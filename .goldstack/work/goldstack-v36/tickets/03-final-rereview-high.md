---
id: "03"
title: "마지막 재리뷰에 high가 남으면 병합하지 않고 티켓 실패로"
blocked_by: ["02"]
touches: ["src/gs/go.py", "src/gs/review.py", "tests/test_final_high.py", "tests/test_rereview.py", "tests/test_verify_repair.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
수정 한도를 다 쓴 뒤 마지막 재리뷰가 낸 high가 "보고만"으로 병합되지 않게 한다(spec 1-6·1-7, 아이디어 `final-rereview-high-not-merged`).

## 완료 조건
- 2차 재리뷰(`review.py`의 `nth == 2` 새 지적)나 수리 재리뷰(`repair_review`)에서 리뷰어 하나라도 severity `high` 지적을 내면, 또는 2차 재리뷰가 기존 high 지적을 `unresolved`(미해결)로 판정하면(spec 3-2. `unchecked`는 세지 않는다), 그 티켓을 병합하지 않고 `go._fail`로 티켓 실패를 적는다. 이유는 `남은 high: <파일:줄> <지적 요약>`(여럿이면 첫 것과 `외 n개`, 미해결이면 끝에 ` (미해결)`).
- 첫 실패면 지금 실패처럼 같은 실행에서 등급을 올려 재시도하고, 실패 요약 입력(`failure.log`)에 그 high 지적 전문이 들어간다. 두 번째면 실패다. 뒤 티켓의 `blocked_by`는 지금 실패 처리와 같다.
- 판단 모델 호출은 더하지 않는다. 첫 리뷰에서 판단 모델이 report·defer로 분류한 high와 medium·low는 지금처럼 보고만이다.
- 실패를 적으면 그 티켓의 리뷰 흐름이 끝난다: `_fail`만 부르고 `_leave_review`·`_merge_stage`로 이어 가지 않는다. 예외로 끊는다면 `_rereview`·`_repair_review`의 포괄 예외 처리에 삼켜지지 않게 한다.
- 재개: 2차 재리뷰·수리 재리뷰 결과를 저장한 직후 gs가 죽어도, 다음 `gs go`가 그 티켓을 병합하지 않고(`reviewed`·`REPAIR_VERIFY` 재개 경로 포함) 실패 수는 한 번만 는다. 옛 state는 지금처럼 읽힌다.
- `tests/test_final_high.py`(`tests/support.GoTest`의 가짜 리뷰어): 2차 재리뷰가 high를 내면 병합되지 않고 재시도된다; 재시도도 2차 재리뷰 high면 `failed`; 2차 재리뷰가 기존 high를 unresolved로 판정해도 같다; unchecked high는 병합된다; 2차 재리뷰가 medium만 내면 지금처럼 병합된다; 수리 재리뷰 high도 같다; 2차·수리 재리뷰 결과 저장 직후 중단 → 재개해도 병합되지 않고 `failures`가 1 늘어난다.
- 바뀌는 기존 시험: `tests/test_rereview.py`의 2차 재리뷰 `UNRESOLVED` high가 병합되고 `남은 리뷰 지적 1`을 단언하는 시험 — 실패 기대로; `tests/test_rereview.py` `test_new_fix_finding_of_first_rereview_goes_to_second_fix`(2차 재리뷰 새 지적이 기본 high라 지금은 병합) — 새 지적을 low로 바꾸거나 실패 기대로; `tests/test_verify_repair.py` `test_findings_of_the_repair_review_are_report_only`(수리 재리뷰 high로 merged) — 같은 방식.
- 바뀐 동작을 `go.py`·`review.py` docstring에 적는다.

## 범위 밖
- 첫 리뷰의 판단 모델 분류
- 실행 전체를 멈추는 판정(범위 밖 `high-stop-verdict`)

## 참고
- `src/gs/review.py` 1206–1208행·1239–1240행, `src/gs/go.py` `_apply_rereviews`(2792행)·`_apply_repair_reviews`(2621행)·`_fail`(2852행)
- `.goldstack/ideas/final-rereview-high-not-merged.md`
