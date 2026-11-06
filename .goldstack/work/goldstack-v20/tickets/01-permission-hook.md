---
id: "01"
title: "무인 세션의 승인 창을 거부하는 hook"
blocked_by: []
touches: ["hooks/hooks.json", "src/gs/hook.py", "src/gs/overnight.py", "src/gs/cli.py", "tests/test_overnight_cmd.py", "tests/test_hook.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
창이 뜨면 아침까지 서는 일을 없앤다. 무인으로 켠 세션에서만 창을 거부로 바꾸고, 낮 세션은 건드리지 않는다.

## 완료 조건
- `hooks/hooks.json`에 `PermissionRequest`가 있고 `gs hook permissionrequest`를 부른다. `gs`가 없거나 켜진 세션이 아니면 아무것도 출력하지 않고 종료 0이라 창이 그대로 뜬다.
- `gs overnight arm`과 `gs overnight disarm`이 있다. arm을 친 Claude 세션만 거부 대상이다. 같은 레포의 다른 세션과 다른 레포는 대상이 아니다. 세션을 가르는 값(예: 조상 Claude 프로세스 pid)을 고르고 왜 골랐는지 docstring에 적는다. 그 프로세스가 사라진 표시는 꺼진 것으로 본다.
- 거부 출력이 spec §6의 JSON 모양이고 `message`가 무슨 호출인지와 다음에 할 일을 말한다. 호출 이름과 시각을 `.goldstack/overnight/denied.log`에 더한다. 비밀을 담을 수 있는 명령 인자 전체는 적지 않는다.
- 위 각 경우를 시험한다. `GS_ROLE=worker` 차단 hook은 그대로 동작한다.

## 범위 밖
- `/overnight`이 언제 arm하는지는 티켓 02가 맡는다. 플러그인 경로의 실제 확인은 병합 뒤 사람이 한다(spec §1).

## 참고
- spec 결정 1-5, §6. 아이디어 `overnight-queue` 권한 절. 맥미니 전용 값을 넣지 않는다.
