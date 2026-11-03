---
id: "05"
title: "연속 실행: gs go a b, /go a b"
blocked_by: []
model: codex
reviewer: agy
---
## 목표
feature 여러 개를 차례로 돌리고, 앞 feature가 verified일 때만 다음으로 넘어가게 한다.

## 완료 조건
- `gs go <f1> <f2> …`: 차례로 돌린다. 각 feature 뒤 그 feature의 state.json 마무리 phase를 읽어 `verified`면 `■ <f1>: verified → <f2> 시작`을 출력하고 다음으로, 아니면 `■ <f1>: <phase> → 여기서 멈춤(남은: <f2> …)`을 출력하고 그 종료 코드로 끝낸다(시험: 둘 다 verified, 첫째 not_merged에서 멈춤).
- 시작 전에 모든 feature를 `gs check`한다. 하나라도 오류면 아무것도 띄우지 않는다(시험).
- feature 하나는 지금과 같게 동작한다. 여러 개와 `--only`를 같이 쓰면 오류.
- `go.py`는 고치지 않는다(`cli.py`가 feature마다 `go.go()`를 부른다).
- `skills/go/SKILL.md`: `/go a b …`를 받아 1–2단계(검사, 커밋·push)를 feature마다 하고 `gs go a b …`를 한 번 띄운다. 결과 보이기는 feature마다. 한계 한 줄: 실행 중 gs를 다시 설치하지 않으므로 앞 feature가 gs 자체를 고치면 다음 feature는 옛 gs로 돈다.

## 범위 밖
- 대기열 파일(spec 1-4에서 뺌), 실행 사이 gs 재설치

## 참고
- spec §3 1-4. touches: `src/gs/cli.py` `skills/go/**` `tests/test_chain.py`
