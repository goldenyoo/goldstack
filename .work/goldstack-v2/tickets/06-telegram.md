---
id: "06"
title: "텔레그램 알림"
blocked_by: ["04"]
model: claude
reviewer: codex
---
## 목표
`gs go`가 끝나면 config에서 켠 경우 텔레그램으로 결과 한 통을 보낸다. 토큰은 대상 레포의 `.goldstack/local.env`에서만 읽는다.

## 완료 조건
- 새 `src/gs/notify.py`가 Bot API `sendMessage`를 표준 라이브러리 urllib로 보낸다: 3회 재시도, 3900자 넘으면 자르고 `… (잘림)` 표시, 예외를 밖으로 내지 않고 성공 여부를 돌려줌, 오류 문자열에서도 토큰을 가림. API 주소는 `GS_TELEGRAM_API`(기본 `https://api.telegram.org`)로 바꿀 수 있다(시험: localhost 가짜 HTTP 서버로 성공·재시도·잘림·토큰 가림).
- `gs go`가 끝날 때(요약 출력 직후, 성공·실패·revert 모두) `notify.telegram = true`면 spec §4 형식으로 한 통 보낸다. 끄면 보내지 않는다. 전송 실패·토큰 없음은 경고 한 줄만 내고 종료 코드와 보고서는 바뀌지 않는다(시험: 가짜 worker `gs go` + 가짜 서버로 받은 본문 확인).
- `notify.telegram = true`인데 `local.env`에 `TG_TOKEN`이나 `TG_CHAT_ID`가 없으면 `gs check`가 경고한다: `경고: notify.telegram이 켜져 있지만 .goldstack/local.env에 TG_TOKEN이 없다(예시: .goldstack/local.env.example)`(시험).
- worker는 보내지 않는다(전송 코드는 코디네이터 쪽에만). 기존 시험이 모두 통과한다.

## 범위 밖
- 티켓 실패마다 알림(`.out-of-scope/notify-per-ticket.md`)
- 다른 채널(Slack 등), 진행 바(05), README(08)

## 참고
- spec §3(1-3), §4 "텔레그램", §2(레퍼런스 설계: 시험 러너에서 전송 안 함 대신 seam, 예외 안 냄, 재시도, 자름, 토큰 가림)
- 설정·local.env 읽기: `src/gs/config.py`
