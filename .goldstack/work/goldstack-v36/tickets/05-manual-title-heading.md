---
id: "05"
title: "수동 피드백 제목: 소제목·코드 블록 줄을 건너뛴다"
blocked_by: []
touches: ["src/gs/feedback.py", "tests/test_feedback_manual_title.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
수동 피드백 본문이 `## 증상`처럼 시작해도 issue 제목이 본문 내용을 담게 한다(spec 1-11, 아이디어 `manual-feedback-title-heading`).

## 완료 조건
- `feedback._manual_title`: 코드 블록(```` ``` ```` 또는 `~~~` 울타리) 안의 줄은 보지 않는다. 첫 `# ` 줄이 있으면 그것. 없으면 `#`로 시작하는 줄(`##` 이상 소제목)과 빈 줄을 건너뛴 첫 줄. 그것도 없으면(소제목만, 코드 블록만, 빈 `# `) `수동 피드백`.
- 80자 자르기와 `[field] <제목> (gs <ver>)` 형식은 그대로.
- `tests/test_feedback_manual_title.py`: `## 증상\n\nworker가 멈춘다` → `worker가 멈춘다`; 코드 블록 안의 `# 주석`을 뽑지 않음; `# 제목`이 있으면 그것; 소제목만·코드 블록만·빈 `# ` 본문은 `수동 피드백`; 지금 단언 유지.

## 범위 밖
- 중복 판정(본문 줄)

## 참고
- `src/gs/feedback.py` `_manual_title`(606행)
