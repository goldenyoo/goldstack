---
name: feedback
description: "사람이 쓴 피드백을 gs feedback으로 보낸다. 사용: /feedback <한 줄 | list | send>"
argument-hint: <한 줄 | list | send>
disable-model-invocation: true
---
# /feedback $ARGUMENTS

레포 루트에서 `gs feedback`에 `$ARGUMENTS`를 그대로 인자로 전달한다. 글을 요약하거나 덧붙이지 않는다. 글 인자는 셸 메타문자가 실행되지 않도록 인용하고, `list`·`send`는 해당 하위 명령으로 전달한다.
명령의 출력과 종료 상태를 보이면 끝이다. `mode = "off"`로 거부되면 그 이유를 그대로 전한다.
