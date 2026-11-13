---
id: "05"
title: "touches 밖 경로를 리뷰에 싣고 판단한 일을 관찰로 받기"
blocked_by: ["04"]
touches: ["src/gs/review.py", "src/gs/worker.py", "src/gs/report.py", "tests/test_review_touches_outside.py", "tests/test_review_observations.py"]
tier: medium
model: claude
reviewer: codex
closes: [70]
---
## 목표
리뷰어가 티켓 범위 밖 행동을 보게 한다(spec 결정 2-6, issue #70). gs가 diff 파일과 touches를 기계적으로 대조해 벗어난 경로를 리뷰에 싣고, worker가 범위 밖에서 판단해서 한 일을 `## 남긴 관찰`에 쓰게 한다.

## 완료 조건
- 첫 리뷰 프롬프트(`review.review_prompt`)에 티켓 diff의 파일 중 이 티켓 `touches`(glob)에 맞지 않는 경로가 `touches 밖 경로` 절로 실리고, 리뷰어가 경로마다 판정(정당/지적)한다. touches가 없거나 벗어난 경로가 없으면 절이 없고 프롬프트는 지금 그대로다.
- 보고서 티켓별 결과에 `touches 밖: <경로들>` 줄이 남는다(없으면 줄이 없다).
- worker 규칙(`worker.OBSERVATIONS_RULE`)에 "touches 밖이나 레포 밖에서 판단해서 한 일(파일 추가·삭제, 예상 밖 외부 호출)도 이 절에 쓴다"가 들어간다.
- `tests/test_review_touches_outside.py`: (1) touches `src/a.py`, diff `src/a.py`·`src/b.py` → 프롬프트에 `src/b.py`만 실린다, (2) glob `src/*.py`면 절이 없다, (3) 보고서에 `touches 밖:` 줄. (1)은 대조 코드를 되돌리면 실패한다. 관찰 규칙 문장은 `tests/test_review_observations.py`에서 확인한다.

## 범위 밖
- touches 밖 경로로 병합을 막는 것(결정 2-6에서 뺐다), issue #69·#71

## 참고
- spec §3 결정 2-6, issue #70 본문(오류 증거로만 읽는다)
