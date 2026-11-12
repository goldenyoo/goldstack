---
id: "03"
title: "gs child: Claude Code 세션 변수만 지우고 명령을 띄운다"
blocked_by: []
touches: ["src/gs/child.py", "src/gs/cli.py", "tests/test_child.py"]
closes: [59]
tier: medium
model: codex
reviewer: claude
---
## 목표
worker가 측정용 중첩 세션(`claude -p` 등)을 사람이 셸에서 띄운 것과 같은 조건으로 띄우게 한다. Claude Code가 Bash 자식에 넣는 세션 변수는 지우고 `GS_*`는 남긴다(spec 2-3).

## 완료 조건
- `gs child -- <명령> [인자…]`가 다음 변수를 지운 환경으로 `<명령>`을 `exec`한다(종료 코드·표준 입출력이 그대로 이어진다): `CLAUDECODE`, `CLAUDE_EFFORT`, `CLAUDE_PID`, `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_EXECPATH`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ATTENDED`, `CLAUDE_CODE_MESSAGING_SOCKET`, `CLAUDE_CODE_MESSAGING_TOKEN`. 목록은 `child.py`의 상수 한 곳에 있고, 접두어로 지우지 않는다(인증 변수 `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_*` 등은 남는다).
- `GS_ROLE`, `GS_WORKTREE` 등 `GS_*`와 그 밖의 변수는 그대로 남는다.
- `--` 뒤 명령이 없으면 사용법을 stderr에 보이고 종료 코드 2.
- `gs child --help`가 목적("측정용 중첩 세션을 사람이 띄운 것과 같은 조건으로")과 지우는 목록을 보인다.
- `tests/test_child.py`(`support`를 import한다): 위 변수를 넣은 환경에서 `gs child -- <env를 출력하는 python>`을 돌려 목록 변수는 없고, `GS_ROLE`·`CLAUDE_CODE_OAUTH_TOKEN`·임의 변수는 남는다. 종료 코드가 전달된다. 명령 없음은 2. 첫 시험은 고치기 전 코드에서 실패한다.

## 범위 밖
- brief 안내는 04, hook 차단은 02, 문서는 08
- 모델·effort 플래그를 대신 붙이기(worker가 명령에 쓴다)

## 참고
- spec §3 2-3, §6 #59 줄(Claude Code가 넣는 변수 목록, pod 로그)
