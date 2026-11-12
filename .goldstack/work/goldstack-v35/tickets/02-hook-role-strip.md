---
id: "02"
title: "worker가 GS_ROLE을 지우거나 바꾸는 명령을 막는다"
blocked_by: []
touches: ["src/gs/hook.py", "tests/test_hook_role_strip.py"]
tier: medium
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
worker가 `GS_ROLE`을 지운 환경으로 프로세스를 띄워 worker hook을 비켜 가지 못하게 한다(spec 2-4). #59의 worker들이 측정용 자식 `claude -p`를 `env -u GS_ROLE …`로 띄웠고, 같은 형태면 자식에서 `git push`가 막히지 않는다.

## 완료 조건
- `GS_ROLE=worker`일 때 Bash 명령의 다음 형태를 막는다. 막는 이유는 `GS_ROLE`을 바꿀 수 없다는 것과 "중첩 세션은 `gs child -- <명령>`으로 띄운다(GS_*는 남고 Claude Code 세션 변수만 지운다)"를 함께 보인다.
  - `env -u GS_ROLE …`, `env --unset=GS_ROLE …`, `env -i …`(환경을 비움), `env GS_ROLE=<worker 아닌 값> …`
  - `unset GS_ROLE`, `export GS_ROLE=<값>`, `GS_ROLE=<값> <명령>`(같은 줄 대입), `export -n GS_ROLE`
  - 위 형태가 `bash -c`·`sh -c`·`zsh -c` 본문, `$( )`, `;`·`&&`·`|` 뒤, `sudo`·`timeout`·`nohup`·`setsid` 같은 앞붙이 뒤에 있어도 막는다(이 파일의 기존 명령 분해를 쓴다).
  - 판정은 `strip_prefix` **전** argv로 한다. `strip_prefix`는 `GS_ROLE=x` 대입과 `env -i`를 지우고, `env -u GS_ROLE …`에서는 `GS_ROLE`을 명령 이름으로 남기기 때문이다(교차 검토 3).
- 통과: `echo $GS_ROLE`, `env | grep GS_`, `printenv GS_ROLE`, `env -u CLAUDE_EFFORT claude -p …`(다른 변수만 지움), `gs child -- claude -p …`, 커밋 메시지(`git commit -m "unset GS_ROLE 막기"`)·heredoc 본문 속 `unset GS_ROLE` 글자(데이터).
- 알려진 오차단: 명령 분해가 따옴표 정보를 잃어 `echo ';' unset GS_ROLE`의 뒤쪽을 명령으로 읽는다. 이 hook의 기존 한계(머리말의 `echo ';' zsh -c` 예)와 같으니 막아도 되고, 머리말 알려진 오차단 목록에 이 예를 더한다. 시험에 그 동작을 고정한다.
- `tests/test_hook_role_strip.py`(`support`를 import한다): 위 막는 형태 각각과 통과 형태 각각. `GS_ROLE`이 없는 세션에서는 모두 통과. 막는 형태 첫 시험은 고치기 전 코드에서 실패한다.
- `hook.py` 머리말의 막는 것 목록에 한 줄을 더한다.

## 범위 밖
- `gs child` 명령 자체는 03
- 스크립트 파일 안·인터프리터 코드(`python -c "os.environ.pop(...)"`) 추적(이 hook의 알려진 한계, 머리말 그대로)
- 다른 `GS_*` 변수 보호

## 참고
- spec §3 2-3, 2-4, §6 #59 줄(pod 로그의 실제 명령)
