---
id: "05"
title: "claude 리뷰어와 판단 모델에 worker와 같은 격리를 넣는다"
blocked_by: []
touches: ["src/gs/review.py", "src/gs/adapters.py", "tests/test_isolation.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
claude 리뷰어와 판단 모델이 머신마다 다른 사용자 MCP와 플러그인을 읽지 않게 한다.

## 완료 조건
- `review.py`의 claude 리뷰 명령과 `judge_argv`(판단, 실패 요약, 보고서 요약)가 worker와 같은 격리를 쓴다: 빈 MCP strict 설정, `--disable-slash-commands`, 다른 플러그인 끄기. 격리 값을 만드는 코드는 `adapters.Claude`의 것을 재사용하고 옵션을 다시 적지 않는다.
- 플러그인 목록을 못 읽으면 worker처럼 플러그인 끄기만 빼고 나머지는 넣는다. 리뷰와 판단 호출은 실패하지 않는다. 경고는 worker의 `isolation_warning`처럼 보이는 곳에 남긴다.
- `--tools` 제한은 그대로다. 리뷰어는 `Read,Grep,Glob`, 판단은 `Read`다.
- `GS_JUDGE`, `GS_REVIEWER_CMD` 시험 seam은 그대로 동작한다.
- `tests/test_isolation.py`에서 명령 인자로 확인한다: 리뷰 명령과 `judge_argv` 모두 격리 옵션이 있다. 플러그인 목록 실패 때도 호출이 만들어진다.

## 범위 밖
- 리뷰어에게 셸 주기(범위 밖 `claude-reviewer-bash`).
- codex·agy 리뷰어의 격리.
- 문서(10).

## 참고
- spec §3의 1-7, `.goldstack/ideas/reviewer-mcp-isolation.md`, `docs/research/worker-plugin-isolation.md`
