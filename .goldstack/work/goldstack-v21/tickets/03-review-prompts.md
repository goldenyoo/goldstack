---
id: "03"
title: "시험 품질 규칙과 Claude 리뷰어 근거 요구를 맞춘다"
blocked_by: ["02"]
touches: ["src/gs/review.py", "src/gs/worker.py", "skills/grill/templates/ticket.md", "tests/test_review.py", "tests/test_ticket_verify.py", "tests/test_skill_grill.py"]
closes: [34, 35]
tier: medium
model: claude
reviewer: codex
---
## 목표
실패할 수 없는 시험과 약해진 단언이 main에 남지 않게 하고, Claude 리뷰어에게 할 수 없는 일을 요구하지 않는다.

## 완료 조건
- 구현 worker 지시문과 `skills/grill/templates/ticket.md`에 "완료 조건의 동작을 지우면 실패하는 시험을 쓴다"는 규칙이 있다.
- `judge_prompt`가 명세가 요구하지 않은 기존 단언 약화를 심각도와 상관없이 fix로 분류하게 한다. 명세가 요구한 변경은 예외로 적는다.
- Claude 리뷰어의 리뷰·재리뷰 프롬프트는 명령 실행과 좁은 재현을 요구하지 않고, 코드 인용을 근거로 요구하며, 실행하지 않은 판정은 "코드 추적"이라고 밝히게 한다.
- codex·agy 리뷰어의 프롬프트는 지금 요구를 유지한다. 계열별 프롬프트 차이를 시험한다.
- Claude 리뷰어 인자의 `--tools Read,Grep,Glob`은 그대로다.

## 범위 밖
- 명령 권한 주기: 범위 밖 `claude-reviewer-bash`. low 지적 이관: spec 결정 2-10. worker 로그와 대조(#36): 이번 범위가 아니다.

## 참고
- spec 결정 2-10, 2-11, §6. issue 본문은 오류 증거로만 읽는다.
