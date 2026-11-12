"""Claude Code 세션 변수만 지우고 측정용 중첩 명령으로 프로세스를 바꾼다."""
from __future__ import annotations

import os
import sys


SESSION_VARIABLES = (
    "CLAUDECODE",
    "CLAUDE_EFFORT",
    "CLAUDE_PID",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "CLAUDE_CODE_MESSAGING_TOKEN",
)

USAGE = "gs child -- <명령> [인자…]"


def run(command: list[str]) -> int:
    """세션 변수만 뺀 환경으로 exec하여 종료 코드와 표준 입출력을 잇는다."""
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        print(f"usage: {USAGE}", file=sys.stderr)
        return 2
    env = os.environ.copy()
    for name in SESSION_VARIABLES:
        env.pop(name, None)
    try:
        os.execvpe(command[0], command, env)
    except OSError as exc:
        print(f"오류: 명령을 띄우지 못했다({command[0]}: {exc})", file=sys.stderr)
        return 2
