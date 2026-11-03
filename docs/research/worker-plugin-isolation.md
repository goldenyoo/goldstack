# 08 worker 플러그인 격리: 실제 `claude -p` 실행 기록 (2026-11-04)

질문: claude worker(`claude -p`)를 goldstack 밖의 사용자 플러그인·skill·MCP 서버 없이 띄우면서
goldstack 플러그인의 worker 차단 hook(PreToolUse, `gs hook pretooluse`)과 사용자 CLAUDE.md·설정은 남길 수 있는가.

답: 된다. `--settings '{"enabledPlugins":{<goldstack 밖 플러그인>:false,…}}' --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands`.
`adapters.Claude`에 넣었다(§4). 완료 조건 두 기준을 실제 실행으로 확인했다(§3).

## 1. 환경과 재는 방법
- Claude Code 2.1.317, macOS arm64. OAuth 로그인(`apiKeySource: none`). `--model haiku`, 짧은 프롬프트로만 돌렸다(실행 11번, 합계 약 $0.025).
- 이 머신에 설치된 플러그인(`claude plugin list`): `goldstack@goldstack`(user), `ha-rtl@ha-rtl`(user),
  `oh-my-claudecode@omc`(user, MCP 서버 `t`), `pdf-viewer@synced`·`cowork-plugin-management@synced`(claude.ai에서 동기화, `pdf-viewer`는 MCP 서버 `pdf`).
  claude.ai 커넥터 MCP 5개(Claude Docs, Atlassian MCP, Google Drive, Atlassian, Slack). 동기화된 사용자 skill `~/.claude/skills/synced`(`anthropic-skills:*` 14개).
- 사용자 설정 `~/.claude/settings.json`: SessionStart hook 1개(herdr), Stop·Notification hook, `permissions.defaultMode`, `deniedMcpServers` 등. 사용자 `~/.claude/CLAUDE.md`는 이 머신에 없다.
- 버리는 레포 `/tmp/gs-iso/repo`(원격은 로컬 bare 레포 `/tmp/gs-iso/remote.git`). 레포에 `CLAUDE.md`("Project magic word: PERSIMMON-42")를 두었다.
- 실행: `cd /tmp/gs-iso/repo && GS_ROLE=worker GS_WORKTREE=/tmp/gs-iso/repo claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --model haiku <후보 옵션> < 프롬프트`.
- 무엇이 실렸나는 stream-json의 `system/init` 이벤트로 본다: `plugins`, `skills`, `slash_commands`, `mcp_servers`, `agents`, `tools`.
  사용자 설정이 읽혔나는 `hook_started:SessionStart` 개수로 본다(사용자 설정 hook 1개 + omc 플러그인 hook 3개 = 기준 4).
  CLAUDE.md는 "CLAUDE.md의 magic word만 답하라, 도구 쓰지 말라" 프롬프트의 답으로 본다.

## 2. 후보별 결과 (프롬프트: magic word)

| # | 추가 옵션 | 플러그인(builtin `cc-plugin-*` 4개 뺌) | skill | MCP 서버 | agents | SessionStart hook | CLAUDE.md | 판정 |
|---|---|---|---|---|---|---|---|---|
| base | 없음 | omc, ha-rtl, goldstack, pdf-viewer, cowork | 88(omc 40, ha-rtl 3, goldstack 8, synced 플러그인 3, anthropic-skills 14, 내장 20) | 7(plugin 2 + claude.ai 5) | 24(omc 19) | 4 | 답함 | 기준 |
| A | `--settings '{"enabledPlugins":{"oh-my-claudecode@omc":false,"ha-rtl@ha-rtl":false,"pdf-viewer@synced":false,"cowork-plugin-management@synced":false}}'` | goldstack만 | 42(goldstack 8, anthropic-skills 14, 내장) | 0 | 내장 5 | 1(사용자 것) | 답함 | 플러그인은 빠짐. 동기화 skill은 남음 |
| B | `--setting-sources project,local --plugin-dir <goldstack>` | goldstack@inline만 | 28(goldstack 8, 내장) | 0 | 내장 5 | **0** | 답함 | 사용자 설정이 통째로 빠짐(spec 2-7 위반) |
| C | `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` | 그대로 5개 | 88 | **0** | 24 | 4 | 답함 | MCP만 빠짐(plugin·claude.ai 둘 다) |
| D | `--disable-slash-commands` | 그대로 5개 | **0**(slash_commands도 0) | 7 | 24 | 4 | 답함 | skill·명령만 빠짐. 플러그인 MCP·agents·hook은 남음 |
| E | `--bare --plugin-dir <goldstack>` | goldstack@inline, omc, ha-rtl | 69 | 0 | – | 0 | – | **실패**: `Not logged in · Please run /login`(OAuth를 안 읽음), 종료 1. CLAUDE.md 자동 탐색과 hook도 꺼짐 |
| F | `--safe-mode --plugin-dir <goldstack>` | goldstack@inline, omc, ha-rtl | 20(내장만) | 0 | – | 0 | **못 답함** | CLAUDE.md·플러그인 skill·hook이 꺼짐 |
| H | `--settings '{}'` | 그대로 5개 | 88 | 7 | 24 | 4 | 답함 | 대조군: `--settings` 자체는 아무것도 안 뺀다 |

관찰:
- A에서 claude.ai 커넥터 MCP 5개도 사라졌다(두 번 돌려 같음). `--settings '{}'`(H)에서는 남으므로 `enabledPlugins`로 플러그인을 끈 것이 원인으로 보이나 이유는 모른다. 기대지 않고 C를 함께 넣어 명시적으로 뺀다.
- A의 `--settings`는 이 세션에만 적용된다. 실행 전후 `~/.claude/settings.json`의 md5가 같았다(`fa686945…`).
- builtin 플러그인(`cc-plugin-agents-md`, `-telemetry`, `-privacy`, `-plugin-authoring`)과 내장 agents(claude, Explore, general-purpose, Plan, statusline-setup)는 어느 옵션에서도 남는다. Claude Code 자체 기능이라 격리 대상이 아니다.
- 동기화 skill(`anthropic-skills:*`, `~/.claude/skills/synced`)은 플러그인이 아니라 A로 안 빠진다. B(사용자 설정 source를 뺌)나 D로만 빠졌다. D는 goldstack skill(`diagnosing-bugs`, `writing-for-agents` 등)도 뺀다. 아이디어 원문이 "이식한 model-invoked skill 포함"을 문제로 적었으므로 worker에서 goldstack skill이 빠지는 것도 원하는 쪽이다(worker는 brief만으로 일한다).

## 3. 고른 조합으로 hook·skill 확인 (프롬프트: push 시도)
프롬프트(`p_push.txt`): "1) 이 Bash 명령을 한 번 돌려라: `git push origin HEAD:main` 2) 돌았나 막혔나 한 줄 3) Skill 도구로 부를 수 있는 skill 이름을 한 줄로(없으면 none), Skill 도구가 있는지도".

### 3.1 G: A + C + D, `--disallowedTools` 없이 (hook 한 겹만 시험)
```
claude -p … --settings '{"enabledPlugins":{"ha-rtl@ha-rtl":false,"oh-my-claudecode@omc":false,"pdf-viewer@synced":false,"cowork-plugin-management@synced":false}}' \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands < p_push.txt
```
- init: plugins `goldstack@goldstack` + builtin 4, skills 0, slash_commands 0, mcp_servers 0, mcp 도구 0/26, agents 내장 5, SessionStart hook 1(사용자 설정 것).
- tool_use `git push origin HEAD:main` → tool_result:
  `PreToolUse:Bash hook error: [if [ "${GS_ROLE:-}" != worker ]; … exec gs hook pretooluse; …]: gs가 막음: \`git push\`는 worker가 하지 않는다. 이 일은 \`gs\`가 한다(push·PR·병합·인증). …`
- 답: "Blocked: a PreToolUse hook from the goldstack plugin refused the command … Skills: none. There is no Skill tool in this session."
- 원격 `remote.git/refs/heads`는 비어 있다(push 안 됨).

→ 기준 (1) goldstack PreToolUse hook이 worker에서 `git push`를 막는다: 충족. 기준 (2) 다른 사용자 플러그인의 skill이 문맥에 없다: 충족(init `skills` 0, 모델도 Skill 도구 없음이라 답함).

### 3.2 구현한 `adapters.Claude` 명령 그대로
`adapters.Claude(...).command(...)`가 만든 문자열을 그대로 돌렸다(이 머신의 `claude plugin list --json` 결과로 채워짐, 뒤에 `--model haiku`만 덧붙임):
```
claude -p --output-format stream-json --verbose --permission-mode bypassPermissions --disallowedTools "Bash(git push *)" "Bash(gh *)" \
  --settings '{"enabledPlugins":{"cowork-plugin-management@synced":false,"ha-rtl@ha-rtl":false,"oh-my-claudecode@omc":false,"pdf-viewer@synced":false}}' \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' --disable-slash-commands < p_push.txt
```
- init: plugins goldstack + builtin 4, mcp 0, skills 0, agents 내장 5. 종료 0.
- `git push`는 여기서도 goldstack hook이 먼저 막았다(같은 `gs가 막음` 메시지). 원격은 그대로 비어 있다. 비용 $0.001.
- 가변 인자 옵션(`--disallowedTools`, `--mcp-config`) 뒤에 바로 `--` 옵션이 와서 값이 섞이지 않는다(명령이 정상 파싱됨).

## 4. 고른 방법과 이유
`adapters.Claude` 명령 = 기존 BASE + `--settings '{"enabledPlugins":{…:false}}'` + `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` + `--disable-slash-commands`.

- 끌 플러그인 목록은 worker를 띄울 때 worktree에서 `claude plugin list --json`으로 읽는다(project scope 플러그인도 나오게). 이름이 `goldstack`인 플러그인(마켓 무관)만 빼고 모두 `false`로 둔다. 켜짐 여부는 보지 않는다(scope마다 다를 수 있고, 꺼진 것을 또 꺼도 해가 없다). `--settings`(flag settings)는 user·project·local보다 우선해서 project에서 켠 플러그인도 꺼진다.
- 목록을 못 읽으면(claude 없음, 종료 코드, JSON 아님) `--settings`만 빼고 나머지 격리는 넣는다. 조용히 넘어가지 않게 그 worker의 종료 메모(`outcome`)에 "플러그인 격리 못 함"을 남긴다. 격리는 차단 장치가 아니라 문맥 정리라 worker를 거부하지 않는다(차단은 hook + `--disallowedTools`가 맡는다).
- 버린 후보: `--bare`(OAuth 로그인을 못 읽어 이 환경에서 아예 안 돈다, CLAUDE.md·hook도 꺼짐), `--safe-mode`(CLAUDE.md와 goldstack hook이 꺼짐), `--setting-sources project,local`(사용자 설정이 통째로 빠짐: spec 2-7 "사용자 설정은 둔다"에 어긋남. 덤으로 goldstack도 `--plugin-dir`로 다시 실어야 함), `--restricted`(Bash를 없애고 bypassPermissions를 거부한다: worker가 일을 못 함).

## 5. 사용자 CLAUDE.md·설정은 남는가
- 설정: 남는다. 고른 조합에서 사용자 설정의 SessionStart hook(1개)이 그대로 돌았다(B처럼 user source를 빼면 0). `--settings`는 키 단위로 덮으므로 `enabledPlugins` 밖의 사용자 설정(permissions, hooks, env 등)은 그대로다. 단 `enabledPlugins`는 이 세션에서 goldstack 밖이 모두 꺼진다(의도).
- CLAUDE.md: 프로젝트 CLAUDE.md는 남는다(G를 포함해 A·B·C·D 모두 magic word를 답함, init `memory_paths.auto`도 있음). 사용자 `~/.claude/CLAUDE.md`는 이 머신에 없어 직접 보지 못했다. 고른 옵션 중 CLAUDE.md 탐색을 끄는 것은 없다(`--help`상 그것을 끄는 것은 `--bare`·`--safe-mode`뿐이고 둘 다 쓰지 않는다).

## 6. 못 빼는 것, 다시 볼 조건
- builtin 플러그인 4개와 내장 agents·도구는 남는다(Claude Code 자체).
- 다시 볼 조건: Claude Code가 `enabledPlugins` flag 설정의 우선순위나 `claude plugin list --json` 형식(`id` 필드)을 바꿀 때, `--disable-slash-commands`가 플러그인 hook까지 끄게 바뀔 때, worker에 goldstack skill을 다시 싣고 싶을 때(그때는 D 대신 동기화 skill만 끄는 방법이 필요하다: 2.1.317에서 찾지 못함), 다른 머신에서 사용자 `~/.claude/CLAUDE.md`가 실제로 실리는지 확인하고 싶을 때.
- 시험: `tests/test_isolation.py`(명령 문자열, 가짜 `claude`를 `GS_CLAUDE`로 끼움). 실제 hook 동작은 §3 기록이 증거다.
