---
id: "08"
title: "`gs notify <파일>` 명령"
blocked_by: []
touches: ["src/gs/cli.py", "src/gs/notify.py", "tests/test_notify.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
`overnight`의 텔레그램 `curl` 체인을 없애도록, 있는 `notify.py`에 명령 입구를 만든다.

## 완료 조건
- `gs notify <파일>`이 파일 내용을 보낸다. 토큰과 채팅 ID는 `.goldstack/local.env`에서 읽고 출력하지 않는다. 길이는 `notify.truncate`를 따른다.
- `gs notify --check`가 메시지를 보내지 않고 토큰을 확인한다. 성공이면 종료 0, 값이 없거나 실패면 이유를 한 줄 내고 종료 1이다. 오류에 토큰이 보이지 않는다.
- `notify.telegram`이 꺼져 있어도 명령은 사람이 친 것이니 보낸다.
- `GS_TELEGRAM_API` seam으로 시험한다: 성공, 값 없음, API 오류, 토큰 가림.

## 범위 밖
- `overnight` 글 바꾸기: 티켓 09.

## 참고
- spec 2-8
- `src/gs/notify.py`
- `test_notify.py`
