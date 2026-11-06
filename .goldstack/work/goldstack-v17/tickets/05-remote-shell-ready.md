---
id: "05"
title: "gs remote가 셸 준비를 재시도로 확인한다"
blocked_by: []
touches: ["src/gs/remote.py", "tests/test_remote.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
셸 시작 질문이 첫 글자를 먹어도 원격 검사와 `gs remote go`가 깨지지 않게 한다.

## 완료 조건
- `_script_in_pane`이 첫 조각을 보내기 전에 표시 줄을 보내 나올 때까지 기다린다. 표시 줄이 먹히면 다시 보낸다. 첫 글자가 질문의 `Y`로 읽히지 않는 명령을 보낸다.
- `launch`의 `GS_REMOTE_READY_` 확인도 같은 도우미를 쓴다. 전체 대기는 `SHELL_READY_MS` 안이고 새 설정 키는 없다.
- 시험은 첫 입력 한 글자를 버리는 가짜 herdr로 두 경로가 모두 성공하는 것을 본다. 영원히 응답하지 않는 pane이면 제한 시간 안에 실패한다. 시험은 실제 시간에 기대지 않는다.
- 준비 실패 안내가 셸 시작 질문(예: oh-my-zsh 업데이트 질문)을 의심하라고 말한다.

## 범위 밖
- `PREPARE` 경합(`goldstack-v13-02-2`)은 v19가 맡는다. 문서는 티켓 06이 맡는다.

## 참고
- spec 결정 2-7, §6. 아이디어 `remote-shell-ready-race`. 맥미니 전용 값을 넣지 않는다.
