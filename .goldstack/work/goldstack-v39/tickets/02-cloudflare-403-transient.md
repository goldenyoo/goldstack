---
id: "02"
title: "Cloudflare 차단 403은 일시 오류로 보고 기다렸다 다시 한다"
blocked_by: []
touches: ["src/gs/transient.py", "tests/test_transient.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
Cloudflare 엣지 차단 403(`API Error: 403 … Attention Required! | Cloudflare`)으로 죽은 worker·리뷰 호출을 영구 오류가 아니라 일시 오류로 분류해 네트워크 대기 뒤 다시 하게 한다(spec 결정 2-2, 아이디어 cloudflare-403-transient).

## 완료 조건
- 403(본문 텍스트의 `403`이나 상태 필드 값 403)과 Cloudflare 표지(`Attention Required`이나 `cloudflare`, 대소문자 무시)가 함께 있는 오류를 일시 오류로 보고 이유 `HTTP 403 (Cloudflare)`를 돌려준다. 대기 일정은 429·5xx와 같다(`WAIT_MINUTES`). 영구 판정을 하는 모든 진입 경로가 이 판정을 먼저 본다: `_error_reason`, agy 텍스트 경로의 `_PERMANENT` 검사, `agy_permanent`(Cloudflare 403이면 영구가 아니다).
- Cloudflare 표지가 있어도 403 밖의 영구 오류 문구(인증, 사용량 한도 등 지금 `_PERMANENT`의 다른 낱말)가 함께 있으면 지금처럼 영구 오류다.
- 표지 없는 403·401은 지금처럼 영구 오류다.
- `tests/test_transient.py`에 시험. 모두 공개 함수 `transient.reason(<계열>, <로그 텍스트>)`로 부르고 claude·codex·agy 계열마다 확인한다: (1) v38 01 worker 로그 형태의 Cloudflare 403 줄 → `HTTP 403 (Cloudflare)`, (2) `403 Forbidden`과 permission 문구 → 영구(빈 문자열), (3) Cloudflare 403과 usage limit 문구가 함께 → 영구, (4) 숫자 상태 필드(`"status": 403`)와 본문 `Attention Required! | Cloudflare`(본문에 숫자 403 없음)를 가진 JSON 오류 → 일시, (5) 상태 필드 401과 Cloudflare 본문 → 영구. 그리고 `agy_permanent`가 (1)의 agy 형태에 False. (1)·(4)는 새 분기를 지우면 실패한다.
- `transient.py` 모듈·함수 docstring의 영구 오류 설명을 고친다.
- 시험은 실제 시간에 기대지 않는다.

## 범위 밖
- 대기 일정·회복 판정 변경
- worker 도구 차단(01)

## 참고
- spec §3 결정 2-2, §6 환경 사실
