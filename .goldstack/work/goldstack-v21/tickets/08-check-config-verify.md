---
id: "08"
title: "설정 파일을 고치는 티켓의 좁은 검증에 경고한다"
blocked_by: ["03"]
touches: ["src/gs/check.py", "skills/grill/templates/spec.md", "tests/test_check.py", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
설정을 고친 좁은 검증 티켓이 전체 시험을 깬 채 병합되어 뒤 티켓이 연쇄 실패하는 일을 grill에서 막는다.

## 완료 조건
- 티켓 `touches`가 `.goldstack/config.toml`에 닿고(glob 포함) 그 티켓의 검증이 spec `verify`와 다르면 `gs check`가 경고한다. `verify_ticket`을 물려받는 경우도 같다.
- 티켓 검증이 spec `verify`와 같거나 `touches`가 닿지 않으면 경고하지 않는다.
- `skills/grill/templates/spec.md`의 `verify` 규칙에 `.goldstack/config.toml`을 고치는 티켓은 `전체`를 쓴다고 적는다.
- 시험이 위 경우를 확인한다. v18 04의 frontmatter 모양을 시험에 쓴다.

## 범위 밖
- 다른 설정 형식 경고: spec 결정 2-2.

## 참고
- spec 결정 2-2, §6. 아이디어 `narrow-verify-config-ticket`. 범위 밖 `ticket-verify-narrow`.
