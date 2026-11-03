---
id: "08"
title: "조사+구현: worker 플러그인 격리"
blocked_by: []
model: claude
reviewer: codex
---
## 목표
claude worker가 goldstack 밖의 사용자 플러그인·skill·MCP 서버 없이 시작하게 하되, goldstack의 worker 차단 hook은 유지한다.

## 완료 조건
- `docs/research/worker-plugin-isolation.md`: Claude Code 2.1.317에서 `claude -p` 세션의 플러그인·skill·MCP를 거르는 방법(후보: `--bare`+`--plugin-dir`, `--setting-sources`, `--strict-mcp-config`+빈 `--mcp-config`, `--disable-slash-commands`, 플러그인 설정 덮어쓰기 등)을 실제로 돌려 본 결과(명령, 무엇이 실렸나, goldstack hook이 걸렸나)와 고른 방법·이유. 사용자 CLAUDE.md·설정이 유지되는지도 적는다.
- 기준 충족 시 구현: 고른 방법이 (1) goldstack 플러그인의 PreToolUse hook이 worker에서 `git push`를 막는다는 것을 실제 `claude` 실행으로 확인했고, (2) 다른 사용자 플러그인의 skill이 worker 문맥에 없다는 것을 확인했으면, `adapters.Claude` 명령에 넣고 명령 문자열 시험을 더한다(`tests/test_isolation.py`).
- 기준 미충족이면 `adapters.py`는 바꾸지 않고 문서에 막힌 이유와 다시 볼 조건을 적는다. 그 경우 `.goldstack/ideas/worker-plugin-isolation.md`(v3가 옮긴 기존 파일)에 막힌 이유를 덧붙이고 `status: "open"`, `feature: ""`로 되돌린다.
- 비용: 실제 `claude` 실행은 조사에 필요한 만큼만(짧은 프롬프트).

## 범위 밖
- codex·agy worker 격리, 사용자 CLAUDE.md·설정 빼기(spec 2-7에서 뺌)

## 참고
- spec §3 1-3, 2-7, §6 claude worker 명령·`claude --help`. touches: `src/gs/adapters.py` `docs/research/worker-plugin-isolation.md` `tests/test_isolation.py`
