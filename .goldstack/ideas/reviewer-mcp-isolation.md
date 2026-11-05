---
date: "2026-11-05"
severity: "medium"
source: "/retro goldstack-v10"
status: "taken"
feature: "goldstack-v11"
---
claude 리뷰어와 판단 모델이 사용자 MCP를 읽어 머신마다 쓸 수 있는 도구가 달라진다.

**근거**:
- worker는 `adapters.Claude.ISOLATION`(`--strict-mcp-config` 등)으로 격리한다. `review.py`의 claude 리뷰 명령과 `judge_argv`에는 `--tools`만 있고 이 옵션이 없다.
- goldstack-v10 04·06 리뷰 답에 `python_repl`이 나온다. import가 막혀 재현에 쓰지 못했다고 적었다. v7·v8·v9 보고서에도 같은 도구가 나온다.
- "goldstack은 환경을 가정하지 않는다" 원칙과 어긋난다.

**제안**: 리뷰·판단 명령에 worker와 같은 MCP 격리를 넣는다. 사용자 플러그인까지 끌지(`enabledPlugins`)도 함께 본다. 시험은 명령 인자로 확인한다. 리뷰어에게 셸을 줄지는 범위 밖 `claude-reviewer-bash`이고 여기서 다루지 않는다.
