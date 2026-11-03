# 09 codex worker hook 차단: 실제 `codex exec` 실행 기록 (2026-11-04)

질문: codex worker를 `workspace-write` sandbox 대신 hook(위험한 명령만 막기)으로 돌릴 수 있는가.
sandbox를 빼면 localhost 시험이 돌고 worktree git 디렉터리 add-dir 우회가 사라진다(아이디어 `codex-worker-hook`).

답: **아직 안 된다.** codex hook은 fail-open이다. hook 명령이 실패(종료 1)·시간 초과·없음·kill·깨진 출력이면
도구 호출이 경고 한 줄 없이 그대로 실행된다(§2.1). 기준 1을 못 넘으므로 코드는 바꾸지 않았다(§5).
기준 2(apply_patch도 잡음)와 기준 3(무인 실행에서 걸림, 단 `--dangerously-bypass-hook-trust` 필요)은 충족한다.

## 1. 환경과 재는 방법
- codex-cli 0.166.0(standalone, macOS arm64). `codex features list`: `hooks stable true`, `plugin_hooks removed false`. 모델은 기본값(`gpt-6.1-sol`).
- 버리는 레포 `/tmp/gscx/repo`(원격 없음). 실행은 모두
  `codex exec --json --skip-git-repo-check -s <sandbox> -c '<hook 설정>' [--dangerously-bypass-hook-trust] "<프롬프트>" < /dev/null`.
- hook은 사용자 `~/.codex/hooks.json`·`config.toml`을 건드리지 않고 **`-c`로 이 실행에만 건다**(바이너리에 `HookEventsToml`이 있어 config.toml 키로 받는다):
  `-c 'hooks.PreToolUse=[{matcher="*",hooks=[{type="command",command="<hook>",timeout=<초>}]}]'`.
- 시험 hook `probe.sh`: stdin 입력을 로그에 남기고, 파일 `/tmp/gscx/mode`의 값대로 행동한다
  (`allow` 종료 0, `deny2` stderr + 종료 2, `fail1` 종료 1, `sleep` 30초, `sleepdeny` 20초 뒤 종료 2, `badjson` 깨진 stdout,
  `jsondeny` `hookSpecificOutput.permissionDecision="deny"` JSON, `kill` 자기 SIGKILL). hook 설정 문자열은 그대로 두고 동작만 바꾼다.
- 막혔는지는 `--json` 이벤트(`command_execution`·`file_change` 항목이 생겼나)와 실제 파일(`out-<mode>.txt`가 생겼나)로 본다.
  프롬프트는 "막히면 다시 시도하거나 돌아가지 말고 보고하고 멈춰라"로 끝낸다.

## 2. 결과

### 2.1 (1) hook이 실패·시간 초과·없음이면 막는가 → **통과시킨다(fail-open)**

| hook 동작 | 결과 | 비고 |
|---|---|---|
| 종료 2 + stderr 이유 (`deny2`) | **막음** | stderr에 `Command blocked by PreToolUse hook: probe denied`. 모델이 이유를 본다 |
| JSON `permissionDecision: "deny"` (`jsondeny`) | **막음** | 이유 `probe json deny`가 모델에게 간다 |
| 종료 1 (`fail1`) | 실행됨 | `out-fail1.txt` 생김 |
| 시간 초과: timeout=3, 20초 뒤 종료 2 (`sleepdeny`) | 실행됨 | timeout은 지켜진다(전체 11초). 시간이 지나면 막지 않고 실행 |
| 시간 초과: timeout=5, 30초 sleep (`sleep`) | 실행됨 | |
| 종료 0 + 깨진 stdout (`badjson`) | 실행됨 | |
| SIGKILL (`kill`) | 실행됨 | |
| hook 명령 경로 없음 (`/tmp/gscx/no-such-hook`) | 실행됨 | |

- 막히지 않은 다섯 경우 모두 `--json` 이벤트·stderr·세션 기록(`~/.codex/sessions/…`)에 hook 실패 흔적이 없다. 조용히 통과한다.
  그래서 gs가 사후에 "hook이 실패했다"를 알아챌 수도 없다.
- 막는 길은 둘(종료 2 + stderr, `permissionDecision: "deny"` JSON)뿐이다. 바이너리 문자열 `PreToolUse hook exited with code 2 but did not write a blocking reason to stderr`로 보아 종료 2인데 stderr가 비면 그것도 막지 않을 수 있다(재지 않음).
- 비교: agy는 hook 실패를 막음으로 다룬다(docs/research/agy.md §2.2). Claude worker는 hook 말고 `--disallowedTools`가 한 겹 더 있다.
  codex는 hook 실패를 "판정 없음"으로 보고 지나간다.

### 2.2 (2) PreToolUse가 셸 밖(apply_patch) 파일 수정도 잡는가 → **잡는다**
- 모델이 `apply_patch`로 파일을 고치면 hook 입력은 `tool_name: "apply_patch"`, `tool_input.command`에 패치 본문 전체가 온다:
  `{"command": "*** Begin Patch\n*** Update File: /private/tmp/gscx/repo/a.txt\n@@\n-hello\n+hello-patched\n*** End Patch"}`.
- `deny2`일 때 패치가 적용되지 않았다(`a.txt` 그대로, `file_change` 항목 없음). 셸 명령은 `tool_name: "Bash"`, `tool_input.command`.
- `matcher="*"`로 둘 다 잡혔다. MCP 도구는 이번에 재지 않았다(gs worker에는 MCP를 싣지 않을 수 있다).

### 2.3 (3) `codex exec` 무인 실행에서 신뢰 확인 없이 걸리는가 → **`--dangerously-bypass-hook-trust`가 있으면 걸린다**
- 플래그 없이 `-c`로 건 hook은 **조용히 건너뛴다**(시험 A: `echo` 실행됨, hook 로그 비어 있음, 경고 없음). 신뢰는
  `~/.codex/config.toml`의 `[hooks.state."<출처>:<이벤트>:<그룹>:<핸들러>"] trusted_hash = "sha256:…"`로 저장되는데,
  gs가 사용자 전역 설정에 쓰는 것은 원칙 밖이다.
- `--dangerously-bypass-hook-trust`를 주면 같은 hook이 걸린다(시험 B 이후 전부). `--json`에 같은 경고
  (`` `--dangerously-bypass-hook-trust` is enabled… ``) `error` 이벤트가 두 번 나오지만 실행은 계속된다(종료 0).
- `-s workspace-write`와 `-s danger-full-access` 둘 다 hook이 걸렸다. hook 입력의 `permission_mode`는 둘 다 `bypassPermissions`.
- hook 프로세스는 codex의 환경을 물려받는다: `GS_ROLE=worker`, `GS_WORKTREE`가 hook에 그대로 왔다(`shell_environment_policy`와 별개).
- 실행 전 확인 수단: `codex hooks` 하위 명령이 없고 `codex doctor`도 hook을 보이지 않는다(app-server에 `hooks/list`가 있으나 재지 않음).
  agy의 `agy -p /hooks` 같은 모델 호출 없는 확인이 없다. 확인하려면 버리는 디렉터리에서 `codex exec`를 한 번 돌려야 한다(모델 호출 비용).

### 2.4 (4) gs의 기존 차단(`gs hook pretooluse`)을 그대로 쓸 수 있는가 → **셸 명령은 그대로, apply_patch는 아니다**
- 입력 모양이 Claude Code와 같다(`tool_name`, `tool_input`, `cwd`, `hook_event_name`, `session_id`…). 막는 방식(종료 2 + stderr)도 codex가 알아듣는다.
- 실제 실행(`-s danger-full-access`, hook = `<gs python> -m gs.cli hook pretooluse`, `GS_ROLE=worker GS_WORKTREE=/tmp/gscx/repo`):

| 도구 호출 | gs 판정 | 결과 |
|---|---|---|
| Bash `git push origin HEAD` | 종료 2 `` `git push`는 worker가 하지 않는다 `` | **막힘** |
| Bash `gh pr create --fill` | 종료 2 `` `gh pr create`는 GitHub에 쓰는 명령이다 `` | **막힘** |
| Bash `echo ok > inside.txt` | 종료 0 | 실행(정상) |
| Bash `curl … https://example.com` | 종료 0 | 실행, `200`(sandbox 없이 네트워크 열림) |
| apply_patch `*** Add File: /Users/goldenyoo/gscx-probe-outside.txt` | 종료 0 | **worktree 밖에 파일이 생김** |

- 비밀 파일: codex Bash 입력 모양 그대로 `cat .env`를 넣으면 종료 2(`비밀 파일 .env을 읽는다`). 같은 모양으로
  apply_patch `*** Update File: …/.env`를 넣으면 종료 0(통과).
- 이유: `hook.decide()`는 `Bash`·`Write`·`Edit`·`Read`… 만 안다. `apply_patch`는 모르는 도구라 통과한다.
  쓰려면 패치 머리줄(`*** Add File:`·`*** Update File:`·`*** Delete File:`·`*** Move to:`)의 경로를 뽑아 `Write`/`Edit` 판정에 넘기는
  번역(agy의 `hook_agy.translate`와 같은 자리)이 필요하다. 어렵지 않지만 기준 1이 막혀 만들지 않았다.

## 3. 판정

| 기준 | 결과 |
|---|---|
| 1 fail-closed | **미충족**. 종료 2·deny JSON 말고는 전부 통과, 흔적도 없음 |
| 2 파일 수정도 잡음 | 충족(`apply_patch`가 PreToolUse로 온다) |
| 3 무인에서 걸림 | 충족, `--dangerously-bypass-hook-trust` 필요(없으면 조용히 빠짐) |
| 4 gs 차단 재사용 | 셸 명령은 그대로. apply_patch 번역이 따로 필요 |

sandbox를 빼면 hook이 유일한 장치가 된다. 그 장치가 hook 프로세스의 사고(gs python 환경이 깨짐, import 오류, 느린 디스크로 시간 초과,
`uv` 캐시 정리로 경로가 사라짐) 하나로 경고 없이 꺼진다. 꺼진 동안에는 네트워크가 열려 있어 `git push`·`gh pr merge`가 실제로 나간다.
gs hook 쪽에서 모든 예외를 종료 2로 바꿔도 시간 초과·kill·명령 없음은 codex가 판정하므로 막을 수 없다. 그래서 opt-in으로도 넣지 않는다.

## 4. 막힌 항목과 다시 볼 조건
- **막힌 항목**: codex 0.166.0 PreToolUse hook의 fail-open(실패·시간 초과·없음·kill·깨진 출력이 통과, 흔적 없음).
- **다시 볼 조건**: codex 새 버전에서 hook 실패를 막음으로 다루는 동작이나 설정(예: 핸들러별 fail-closed 옵션)이 생기면.
  §1의 `probe.sh` 모드 `fail1`·`sleepdeny`·`kill`·없는 경로 네 가지를 다시 돌려 `out-*.txt`가 안 생기면 기준 1 충족이다.
  그때 할 일: §2.4의 apply_patch 번역, `-c hooks.PreToolUse=…` + `--dangerously-bypass-hook-trust` + `-s danger-full-access`,
  실행 전 확인(버리는 디렉터리에서 `git push`가 막히는지 한 번 돌림, 비용 있음).
- 대안(이번 범위 밖): sandbox는 그대로 두고 hook을 두 번째 겹으로 더하는 것. fail-open이어도 sandbox가 첫 줄이라 해가 적다.
  다만 sandbox 때문에 생긴 문제(localhost 시험, git 디렉터리 add-dir)는 그대로라 아이디어의 목적은 못 이룬다.

## 5. 바꾼 것
- 코드는 바꾸지 않았다. `[codex] guard` 설정도 넣지 않았다(완료 조건: 기준 미충족이면 코드 변경 없음).
- `.goldstack/ideas/codex-worker-hook.md`에 근거를 덧붙이고 `status: "open"`, `feature: ""`로 되돌렸다.
- 이 실험으로 생긴 `~/gscx-probe-outside.txt`(내용 `x`)는 §2.4의 apply_patch 통과 증거다. worker가 worktree 밖을 못 지우므로 사람이 지운다.
