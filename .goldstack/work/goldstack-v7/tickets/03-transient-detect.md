---
id: "03"
title: "일시 오류 판별: claude·codex·agy 출력에서 네트워크·API 오류를 가린다"
blocked_by: ["01"]
touches: ["src/gs/transient.py", "src/gs/adapters.py", "tests/test_transient.py"]
model: codex
reviewer: claude
---
## 목표
worker 종료와 CLI 출력만 보고 "일시 오류인가"를 답하는 판별을 만든다. 대기와 재시작은 06, 리뷰 호출 적용은 07이 한다.

## 완료 조건
- `src/gs/transient.py`가 로그 텍스트를 받아 일시 오류의 이유(없으면 빈 값)를 돌려주는 함수를 낸다. 어댑터에 같은 뜻의 메서드가 있어 `go.py`가 계열을 몰라도 묻게 된다. 기존 `outcome` 동작은 그대로다.
- 시험이 spec §6의 실제 출력 모양으로 다음을 본다.
  - claude: 마지막 result의 `"api_error":"connection_failed"`, `"terminal_reason":"api_error"` → 일시. 5xx·429 상태 → 일시.
  - codex: `Reconnecting... waiting for network`, `stream disconnected before completion`, `error sending request` → 일시.
  - agy: 연결 오류 문구 → 일시. `invalid model selection`은 `agy models`를 돌려 가른다: 실패(`timed out waiting for available models` 등)면 일시, 성공했는데 그 모델이 목록에 없으면 설정 오류(일시 아님), 목록에 있으면 일시. `agy models` 호출은 시간 제한을 두고 시험에서는 `GS_AGY` seam으로 바꾼다.
- 구독 사용량 한도, 인증 실패, 일반 실패(시험 실패, 종료 코드 1만 있는 로그)는 일시 오류가 아니다. 문구를 모르는 오류는 일시 오류로 보지 않는다(보수적으로). 시험이 있다.
- 판별은 worker의 작업 출력 속 우연한 문자열에 넘어가지 않는다. claude는 마지막 result 이벤트, codex는 `{"type":"error",...}` 이벤트처럼 구조를 먼저 본다. 시험: 시험 출력에 `ECONNREFUSED`가 찍힌 claude 로그의 result가 정상이면 일시 오류가 아니다.

## 범위 밖
- 대기·재시작·중단(06), 리뷰·판단 호출(07), 사용량 한도 처리(out-of-scope `usage-adapters`).

## 참고
- 이번 실행 규칙: 개발 중에는 관련 시험만 돌리고, 전체 검증은 커밋 직전에 한 번만 돌린다(수정 worker도). gs가 병합 전에 다시 돌린다.
- spec §3 2-9, §6 네트워크 끊김 때 출력, `agy models`.
- 아이디어 `.goldstack/ideas/transient-api-error-retry.md`의 v6 03 사건.
- 실제 로그 예: `.goldstack/work/goldstack-v6/run/03/1/` (gitignore. 있으면 읽고, 없으면 spec §6을 쓴다).
