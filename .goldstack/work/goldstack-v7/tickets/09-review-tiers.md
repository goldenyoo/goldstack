---
id: "09"
title: "리뷰어 등급(첫 리뷰 large, 재리뷰 medium)과 실패 요약 모델"
blocked_by: ["07", "08"]
touches: ["src/gs/review.py", "src/gs/failure.py", "tests/test_review_tiers.py"]
model: codex
reviewer: claude
---
## 목표
리뷰와 판단 호출에도 등급표를 적용한다. 지적을 놓칠 위험이 작은 것부터 내린다.

## 완료 조건
- 첫 리뷰는 `[tiers] review`, 재리뷰는 `[tiers] rereview` 등급의 모델·effort로 돈다. 계열별 인자는 08과 같다(claude `--model --effort`, codex `--model -c model_reasoning_effort=`, agy `--model`, effort가 있으면 `--effort`). 시험이 세 계열의 argv를 본다.
- 읽기 전용 장치(`--tools Read,Grep,Glob`, `-s read-only`, `--sandbox`)는 그대로다. 시험이 있다.
- 표가 없으면 지금처럼 `models.claude_review`, `models.codex`, `models.agy`를 쓴다. 시험이 있다.
- `failure.summarize`는 `models.failure_summary`를 쓴다. 지적 분류(`review.classify`)와 보고서 Summary는 `models.judge`를 그대로 쓴다. 시험이 있다.
- 쓴 모델·effort를 리뷰 기록에 남긴다(보고서 표시는 10).

## 범위 밖
- 등급표 스키마(08), 분류를 작은 모델로(`judge-lower-tier`), 티켓 등급을 따르는 리뷰(2-18에서 뺐다).

## 참고
- 이번 실행 규칙: 개발 중에는 관련 시험만 돌리고, 전체 검증은 커밋 직전에 한 번만 돌린다(수정 worker도). gs가 병합 전에 다시 돌린다.
- spec §3 2-18, 2-20. §4 등급표.
- 아이디어 `.goldstack/ideas/model-tiering.md` "위험".
