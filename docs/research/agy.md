# agy 권한과 차단 장치 (2026-11-03)

대상: agy 1.4.12(Antigravity CLI, `~/.local/bin/agy`), macOS(arm64). 티켓 11. 05(모델 어댑터)에 줄 권고는 [§6](#6-05에-줄-권고).

표시: **[측정]** 실제로 돌려 봄(실험 번호는 §7) · **[추정]** 문서·changelog·내장 문서에서 읽었고 돌려 보지 않음 · **[모름]** 확인 못 함.

출처: `agy --help`, print 모드의 읽기 전용 slash 명령(`agy -p /config`, `/hooks`, `/permissions`, `/model`, `/effort`: 모델 호출 없음), 내장 문서 `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/{hooks,plugins,json_configs}.md`, changelog `~/.gemini/antigravity-cli/cache/CHANGELOG.md`, `https://antigravity.google/docs/cli/reference`. 실험은 모두 `/tmp/agyexp.*`의 버리는 레포(원격은 같은 디렉터리의 로컬 bare 레포)에서 했다.

## 0. 요약
- `--mode auto`는 **이 계정에서 쓸 수 없다**. 경고 한 줄을 내고 기본 모드로 돈다 **[측정]**. 기본 모드의 `-p`는 모든 셸 명령을 자동 거부하고도 종료 코드 0, `status: SUCCESS`로 끝난다 **[측정]**. spec §7의 `agy -p --output-format stream-json --mode auto`로 띄우면 worker는 아무것도 못 하고 성공으로 보고된다.
- worker로 쓰려면 `--dangerously-skip-permissions`(= `always-proceed`)가 필요하다. 이 모드에서도 **deny 규칙과 PreToolUse hook은 동작한다** **[측정]**.
- deny 규칙(`command(git push)`)은 단어 단위 매칭이라 `git -C . push`, `sh -c '…'`, 스크립트, python으로 우회된다 **[측정]**.
- PreToolUse hook은 있고, 막을 수 있고, **실패하면 막는 쪽(fail-closed)**이다 **[측정]**. hook 프로세스는 agy의 환경 변수(`GS_ROLE`)를 물려받는다 **[측정]**. 그래서 09의 `gs.hook.decide()`를 agy 입력 형식에 맞춰 붙이면 claude worker와 같은 수준으로 막는다 **[측정: 임시 어댑터로]**.
- `--sandbox`는 print 모드에서 **workspace 자체를 읽기 전용**으로 만들어 커밋이 안 된다 **[측정]**. worker에는 못 쓴다.
- 결론: deny 규칙 + `gs` PreToolUse hook만으로는 **구현 worker에 부족하다**. 스크립트 파일, python, git alias로 실제 push된다 **[측정]** E3a·E3c(claude worker의 09 hook도 같은 빈틈). agy를 구현 worker로 띄우는 것은 다른 브랜치가 넣는 **구조적 환경 차단**(모든 worker 공통: 환경 변수로 준 git 설정이 모든 push URL을 막힌 주소로 바꾸고, `GH_TOKEN`은 무효 값)이 있을 때만이다. 이 차단이 있으면 스크립트·alias·python을 거친 push도 실패한다 **[추정]**(§5). 그 위에 `gs`가 결과를 다시 검증한다. 이 차단이 없으면 agy는 **리뷰 전용**이다.
- 모델 창은 약 105만 토큰이지만 agy는 약 25만 토큰에서 자동 압축하고, 그 뒤 모델은 앞서 읽은 원문을 못 본다 **[측정]**. 넓게 읽히는 일에는 입력을 줄인다(§8).

## 1. 권한 모드
| 항목 | 내용 | 근거 |
|---|---|---|
| 설정 키 | `toolPermission`: `request-review`(기본) / `proceed-in-sandbox` / `always-proceed` / `strict`. "Deny rules apply in every mode." | [추정] reference 문서. 기본값은 `agy -p /config`로 [측정] |
| `agentMode`(`--mode`) | `""` / `accept-edits` / `auto` / `plan`. 기본 `""` | [측정] `--help`, `/config` |
| 기본 모드 + `-p` | 셸 명령이 사람에게 물어야 해서 자동 거부된다. stderr에 `a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied`. 모델은 거기서 멈춘다. 종료 0, `result.status: SUCCESS`, `result.denied_actions: [{"action":"command",…}]` | [측정] E1 |
| `--mode auto` | 이 계정에서 `warning: --mode auto is not available for this account; continuing in the default mode.` 그 뒤는 기본 모드와 같다(위 줄) | [측정] E1 |
| `--mode auto`의 원래 범위 | 파일 수정과 안전한 명령은 묻지 않고, 터미널 sandbox 안에서 돈다. sandbox를 벗어나는 명령은 별도 agent가 검토하고, 되돌릴 수 없는 일(파괴적 git 등)은 묻는다. Preview, sandbox 필요, business·enterprise 계정은 안 됨. `-p`에서 "묻는다"는 자동 거부가 된다 | [추정] reference·changelog. 왜 이 계정이 안 되는지는 [모름] |
| 잘못된 `--mode` 값 | `warning: unrecognized --mode value "bogus"` 후 기본 모드로 진행, 종료 0 | [측정] X6 |
| `--dangerously-skip-permissions` | `init.permission_mode`가 `always-proceed`가 된다. 셸·파일 도구를 묻지 않고 실행한다. deny 규칙과 hook은 여전히 적용된다 | [측정] E2a, E3, X2 |
| `--settings` | 이번 세션에만 쓰는 settings.json 조각(인라인 JSON 또는 파일 경로). 디스크에 저장되지 않는다 | [측정] `/permissions`에 반영되는 것 확인. "저장 안 됨"은 [추정](`--help` 문구) |

## 2. 도구 허용·차단, hook, sandbox
### 2.1 허용·차단 규칙
- 형식: `settings.permissions = {"allow": [...], "ask": [...], "deny": [...]}`. 항목은 `command(<명령 앞부분>)`, `read_file(<경로>)`, `write_file(<경로>)`, `mcp(<서버>/<도구>)`, `read_url(<도메인>)`, `execute_url(<도메인>)`. `--settings '{"permissions":{"deny":["command(git push)"]}}'`가 `/permissions`에 `global deny command(git push)`로 잡힌다 **[측정]**. 형식 목록은 바이너리에 든 내장 문서에서 읽었다 **[추정]**.
- 매칭은 문자열 비교이고 정규식이 아니다(`regex:` 접두로 바꿀 수 있다) **[추정]** changelog.
- `--dangerously-skip-permissions`에서도 deny가 막는다 **[측정]** E2a. 막힌 도구 호출은 `step_update.state: ERROR`, 메시지 `Matches user-configured deny rule.`이다.
- `command(git push)`의 실제 범위 **[측정]** E3a:

| 명령 | deny 규칙 | gs hook(§2.2 어댑터) |
|---|---|---|
| `git push origin HEAD:v1` | 막음 | 막음 |
| `env git push …` | 막음 | 막음 |
| `cd . && git push …` | 막음 | 막음 |
| `git push --force origin HEAD:main` | 막음 | 막음 |
| `git -C . push …` | **통과(push됨)** | 막음 |
| `sh -c 'git push …'` | **통과** | 막음 |
| 셸 한 줄로 스크립트 만들고 실행(`printf … > p.sh && ./p.sh`) | **통과** | **통과*** |
| 파일 도구로 `p2.sh`를 쓰고 따로 `sh p2.sh` | – | **통과** |
| `python3 -c "subprocess.run(['git','push',…])"` | **통과** | **통과** |
| `git -c alias.up=push up origin …` | – | **통과** |
| `echo y > /tmp/…/outside.txt`(worktree 밖) | – | 막음 |

\* 이 줄은 agy로는 E3b에서만 돌렸고, E3b의 막음은 엉성한 시험 hook이 프롬프트(`lastUserInput`)에 든 "git push"를 보고 막은 것이라 무효다. 같은 명령 문자열을 `decide()`에 바로 넣으면 `None`(통과)이다 **[측정]**.

### 2.2 hook
- 있다. `hooks.json`의 이벤트는 `SessionStart`, `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`이고, 형식은 Claude Code와 비슷하지만 같지 않다 **[추정]** 내장 hooks.md. `PreToolUse`가 `-p`에서 실제로 불리고 막는다 **[측정]** E3b·E3c·E6·E11.
- 설정 위치 **[측정]**: 전역 `~/.gemini/config/hooks.json`(이미 cmux·herdr hook이 있다), workspace `<repo>/.agents/hooks.json`. 신뢰하지 않은 workspace에서도 `-p`가 workspace hook을 읽는다(`agy -p /hooks`로 확인, E3b에서 실제로 불림). plugin 루트의 `hooks.json`도 읽는다 **[추정]** plugins.md. 시험용 plugin 디렉터리가 `agy plugin validate --strict`를 통과한 것까지만 **[측정]**했고, 설치는 전역 설정을 바꾸므로 하지 않았다.
- 입력(stdin) **[측정]** 로그로 확인:
  ```json
  {"conversationId": "…", "workspacePaths": ["/tmp/…/e3b"], "transcriptPath": "…", "artifactDirectoryPath": "…",
   "modelName": "gemini-3.8-flash-medium", "lastUserInput": "<프롬프트 전체>", "stepIdx": 2,
   "toolCall": {"name": "run_command", "args": {"CommandLine": "git push origin HEAD:v1", "WaitMsBeforeAsync": 5000, "toolSummary": "…"}}}
  ```
  hook에서 본 도구 이름과 인자: `run_command`(`CommandLine`), `write_file`(`Path`, `Content`), `edit_file`(`Path`), `read_file`(`Path`) **[측정]** E3c·E6. `init` 이벤트의 도구 목록 이름(`write_to_file`, `replace_file_content`, `view_file`)과 **다르다**. matcher는 `"*"`로 두고 이름은 어댑터에서 보는 편이 안전하다.
  `lastUserInput`에는 프롬프트 전체가 들어 있다. 문자열 전체를 grep하면 brief에 적힌 금지 문구 때문에 정상 명령까지 막는다(E3b). `toolCall.args`만 봐야 한다.
- 출력 **[측정]**: stdout에 `{"decision":"deny","reason":"…"}`를 내면 `tool call denied by pre-tool hook: <reason>`으로 막히고 모델에게 이유가 보인다. `{"decision":"allow"}`면 진행한다. `ask`도 있지만 `-p`에서 어떻게 되는지는 [모름](자동 거부로 [추정]).
- 실패 시 **막는다(fail-closed)** **[측정]** E4: 종료 코드 1, JSON이 아닌 출력, `timeout` 초과 모두 그 도구 호출이 ERROR가 되고 실행되지 않는다. 이때 Claude Code hook(종료 2 = 막음)과 달리 **종료 코드가 아니라 stdout JSON**으로 판정한다.
- 환경 **[측정]** E11: hook 프로세스는 agy를 띄운 환경을 물려받는다(`GS_ROLE`, `GS_WORKTREE`, 임의 변수). 작업 디렉터리는 `hooks.json`이 있는 디렉터리다(문서와 일치).
- 실행 중 변경 **[측정]** E11: agent가 `.agents/hooks.json`을 `{}`로 덮어써도 그 실행의 hook은 계속 막았다(시작할 때 읽는다). 다만 파일은 바뀐 채 worktree에 남는다.
- 실행 중 hook 정의 다시 읽기: changelog에 "workspace가 바뀌면 다시 읽는다"는 말이 있다 **[추정]**. 실행 중 `--add-dir` 같은 workspace 변경으로 hook이 바뀌는지는 [모름].

### 2.3 sandbox
- `--sandbox` 또는 `enableTerminalSandbox: true`(기본 false)는 셸 명령을 OS 격리(macOS seatbelt)에 넣는다. 파일 도구에는 적용되지 않는다 **[추정]** reference("terminal sandbox").
- print 모드에서 실제로 본 동작 **[측정]** E5c·E7·E8·E9·E10:
  - **workspace 안 쓰기가 막힌다**(`operation not permitted: s.txt`, `mkdir: sub: Operation not permitted`). git 레포든 아니든, `/tmp`든 `/private/tmp`든 `$TMPDIR`(`/var/folders/…`)든, `trustedWorkspaces`에 넣든, `git worktree`든 같았다. 내 도구 sandbox 밖에서 돌려도 같았다(E9). 그래서 **커밋을 못 한다**. 원인은 [모름].
  - 반면 workspace 밖 `/tmp/…` 쓰기는 됐고, `/tmp`에 있는 로컬 bare 원격으로 `git push`도 됐다.
  - `~/.ssh` 읽기는 막혔다(`Operation not permitted`).
  - 네트워크: `--dangerously-skip-permissions`와 같이 쓰면 `git ls-remote https://github.com/…`가 됐다. `proceed-in-sandbox`면 DNS부터 막혔다.
  - 실패한 명령에는 "`BypassSandbox`로 다시 돌려 보라"는 안내가 붙는다. skip-permissions에서는 그 우회도 묻지 않고 승인된다고 [추정]한다.
- 결론: worker(커밋 필요)에는 쓸 수 없다. 원격 push 차단 수단도 못 된다(skip-permissions에서 네트워크가 열림).

## 3. headless(`-p`): 종료 코드, stream-json, 시간 제한
### 3.1 종료 코드
| 종료 | 경우 | 근거 |
|---|---|---|
| 0 | 정상 완료 | [측정] |
| 0 | 도구가 권한 때문에 자동 거부됨(`denied_actions` 있음, 응답이 비어도) | [측정] E1 |
| 0 | `--print-timeout` 만료(턴 진행 중). stderr `[agy] print timeout after 10s with turn in progress; returning partial output`, `finished_reason: "print_timeout"` | [측정] X11 |
| 0 | `--mode` 값 오류·`auto` 불가(경고만) | [측정] X6, E1 |
| 1 | 모르는 모델, 모델과 `--effort` 충돌, 잘못된 `--json-schema` | [측정] X1·X10·X3 |
| 1 | SIGTERM(`error: interrupted`, `result.status: ERROR`, `finished_reason: "interrupted"`) | [측정] X4 |
| 2 | 플래그 파싱 오류(`flags provided but not defined`, 사용법 출력, JSON 없음) | [측정] 실수로 확인 |
| 3 | 응답 일부를 stream한 뒤 모델·agent 오류로 끝남(`AGY_ERROR` 줄) | [추정] changelog |
| 0이 아닌 값 | 서버 쪽 요청 실패 | [추정] changelog. 정확한 값은 [모름] |

정리하면 종료 0은 "agent가 일을 했다"는 뜻이 아니다. 거부, 시간 제한, 모드 무시가 모두 0이다.

### 3.2 stream-json(`--output-format stream-json`)
NDJSON 한 줄에 이벤트 하나. 본 이벤트는 세 종류다 **[측정]**:
- `{"event":"init","conversation_id":…,"init":{"model":"gemini-3.8-flash-medium","cwd":…,"tools":[…],"permission_mode":"always-proceed"}}`. `--model`이 없으면 `model` 키가 없다(X8).
- `{"event":"step_update","step_update":{"conversation_id","step_index","state","step_type",…}}`
  - `state`: `ACTIVE` / `DONE` / `ERROR`
  - `step_type`: `user_input` / `agent_response`(`usage`, `duration_seconds`) / `tool`(`tool_name`, `tool_info.parameters`, 끝나면 `tool_info.output` 또는 `tool_info.error{type,message}`)
- **끝 이벤트** `{"event":"result","result":{…}}`. 마지막 줄에 한 번 나온다.
  - `status`: `SUCCESS` / `ERROR`
  - `response`(최종 답), `duration_seconds`, `num_turns`, `usage{input_tokens,output_tokens,thinking_tokens,cache_read_tokens,total_tokens}`
  - 있을 수도 있는 것: `denied_actions[{action,display_name}]`(E1), `error`(문자열), `finished_reason`: `print_timeout` / `interrupted` / `error`. 정상 완료에는 `finished_reason`이 없었다.
  - 시작 단계 오류(모르는 모델 등)에도 `result`가 나온다(`conversation_id: ""`, 종료 1). SIGTERM에도 나온다. 플래그 파싱 오류에는 나오지 않는다.
- 주의: deny 규칙에 막힌 경우(E2a)와 hook에 막힌 경우(E3b)에는 `denied_actions`가 **없었다**. 막힌 사실은 해당 `step_update`의 ERROR에만 있다.

### 3.3 시간 제한
- `--print-timeout`의 기본값은 0(무제한) **[측정]** `--help`. 만료되면 부분 출력을 내고 **종료 0**이다 **[측정]** X11.
- 턴이 끝나도 백그라운드 작업이 있으면 `--print-timeout`까지(최대 30분) 기다린 뒤 끝낸다. stderr `root agent idle; waiting up to 8s for 1 background task(s)` / `terminating 1 background task(s) on exit` **[측정]** X2. 30분 상한은 [추정] changelog.
- 따라서 시간 제한은 agy에 맡기지 말고 `gs`(07의 idle 시간 초과)가 프로세스를 끊는 쪽이 맞다. 끊으면 종료 1과 `result.status: ERROR`가 남는다(X4).

## 4. 모델 선택과 추론 강도
- 목록: `agy models`(`--output-format json` 가능). 이 계정에서는 `gemini-4-argon-{low,medium,high}`, `gemini-3.8-flash-{low,medium,high}`, `claude-opus-5-5-*`, `claude-sonnet-5-5-*`, `gpt-oss-120b-medium` **[측정]**.
- **Carbon (2026-11-12)**: agy 1.5.6의 `agy models`에 `gemini-4-carbon-{low,medium,high}`가 있다(맥북에서 확인). 이 레포는 `models.agy`와 `[tiers.agy]` 세 칸을 `gemini-4-carbon-high`로, gs 기본값(`DEFAULT_CONFIG`)은 `medium = gemini-4-carbon-medium`, `large`·`models.agy = gemini-4-carbon-high`로 옮겼다. Argon과 비교 측정은 하지 않았다. 사람이 Carbon을 쓰겠다고 정해 바꿨고, 시간·지적 품질은 바꾼 뒤 실행 보고서와 `/retro`로 본다. 아래 Argon 측정은 옛 모델 기준이다.
- 지정 방법 **[측정]** X7·X9·X10 + `/model`·`/effort`:
  - `--model gemini-4-argon-high` 처럼 강도가 붙은 slug, 또는
  - `--model gemini-4-argon --effort high`(→ `/model`이 `gemini-4-argon-high`로 해석). `--effort` 값은 `low|medium|high|xhigh|max` 중 모델이 지원하는 것.
  - 기본 강도: 모델만 주면 medium(argon에서 확인). 아무것도 안 주면 이 계정은 `gemini-4-argon-medium`이다.
  - 강도 붙은 slug와 다른 `--effort`를 같이 주면 종료 1(`conflicts with --effort=low`).
  - 모르는 모델은 `-p`에서 종료 1과 모델 목록. 대체 모델로 조용히 내려가지 않는다.
- agy는 Claude·GPT 모델도 띄운다. 리뷰를 "다른 계열"로 하려면 어댑터가 Gemini slug를 명시해야 한다. 기본값에 기대면 설정이 바뀌었을 때 계열이 달라질 수 있다 **[추정]**.

## 5. 위험한 명령을 막을 수 있는가
실제 시도 결과(§2.1 표, §7)를 정리한다.
- 기본 모드: 모든 명령이 막힌다. 대신 일도 못 한다 **[측정]**.
- skip-permissions + deny 규칙만: 직접 쓴 `git push`는 막지만 흔한 변형 4가지로 실제 push됐다 **[측정]**. 혼자서는 부족하다.
- skip-permissions + PreToolUse hook(`gs.hook.decide()` 재사용): `-C`, `sh -c`, `cd &&`, `env`, force, worktree 밖 쓰기(셸·파일 도구 둘 다)를 막았다 **[측정]**. 커밋은 통과했다 **[측정]** E3c. 통과한 것은 python subprocess, 스크립트 파일(파일 도구로 쓰든 셸 한 줄로 쓰든), `git -c alias.x=push`이다 **[측정]**. 이 셋은 `decide()` 자체의 빈틈이라 claude worker(09)도 똑같다. 같은 입력을 `decide()`에 바로 넣어 `None`이 나오는 것을 확인했다 **[측정]**.
- sandbox: 커밋을 못 하게 만들어 worker에 못 쓴다 **[측정]**.
- 정상 작업 중의 실수로도 뚫린다. 예: worker가 레포의 `scripts/release.sh`를 돌리고 그 안에 `git push origin HEAD:main`이 있으면 deny 규칙과 hook을 모두 지난다(hook 통과는 **[측정]**: 같은 꼴을 `decide()`에 넣어 `None`, 실제 push는 E3a의 스크립트 사례). 원격 인증이 살아 있으면 `gs`의 검증·병합 전에 push된다. 그래서 hook은 "실수"를 막는 장치로도 부족하다.
- 구조적 환경 차단(다른 브랜치, 모든 worker 공통): worker 환경에 `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n`으로 git 설정을 넣어 모든 push URL을 막힌 주소로 바꾸고(`pushInsteadOf`/`insteadOf` 계열), `GH_TOKEN`을 무효 값으로 둔다. 환경 변수는 셸·스크립트·python subprocess·alias가 모두 물려받으므로 위 세 우회도 push 단계에서 실패한다 **[추정]**: git의 설정 규칙에서 미룬 것이고, 이 조사에서 agy로 돌려 보지 않았다. 그 브랜치의 시험이 확인한다. 같은 환경에서 `git config`를 다시 쓰거나 환경 변수를 지우는 의도적 우회는 여전히 남는다 **[추정]**.
- 결론: 구현 worker로 쓰려면 deny 규칙 + hook + **구조적 환경 차단** + `gs`의 사후 검증(브랜치·커밋 재확인, push·PR·병합은 `gs`만)이 모두 있어야 한다. 앞의 둘만으로는 리뷰 전용이다.

## 6. 05에 줄 권고
**띄우는 명령**(worktree에서, herdr pane 안):
```sh
GS_ROLE=worker GS_WORKTREE=<worktree> \
agy -p "<brief 전문>" \
  --output-format stream-json \
  --dangerously-skip-permissions \
  --settings '{"permissions":{"deny":["command(git push)","command(gh pr create)","command(gh pr merge)","command(gh pr close)","command(gh api)","command(gh repo)","command(gh release)","command(gh auth)"]}}' \
  --model <slug, 예: gemini-4-argon-high>
```
- `--mode auto`는 넣지 않는다(이 계정에서 무시되고, 되더라도 `-p`에서 "묻는다"가 거부라서 정상 작업이 막힌다. ORIGINS 실패 10과 같은 꼴). spec §7의 headless 명령은 이 권고로 바뀌어야 한다.
- `--sandbox`는 넣지 않는다(§2.3).
- `--print-timeout`은 넣지 않는다. 시간 제한은 `gs`가 한다(§3.3).
- 모델은 강도까지 붙은 slug 하나로 준다. `--effort`를 따로 쓰면 충돌 오류(종료 1)가 날 수 있다.
- gh deny 목록은 git push 결과에서 미루어 정했다 **[추정]**. 05에서 한 번 확인한다.

**구현 worker로 쓸 조건**: 아래 두 겹에 더해, 모든 worker에 거는 구조적 환경 차단(§5: push URL을 막힌 주소로 바꾸는 env git 설정 + 무효 `GH_TOKEN`)이 있어야 한다. 두 겹만으로는 스크립트·python·alias push가 통과한다 **[측정]**. agy를 구현 worker로 쓰는 것은 이 환경 차단과 `gs`의 재검증에 기대는 것이다. 환경 차단이 없으면 agy는 리뷰 전용으로만 띄운다.

**차단(두 겹, 둘 다 필수. 단 위 환경 차단 없이는 충분하지 않다)**:
1. deny 규칙(위 `--settings`). hook이 빠져도 직접 쓴 형태는 막는 마지막 줄이다.
2. PreToolUse hook: `gs hook agy-pretooluse`(새 진입점) 같은 것을 만든다. agy 입력을 09의 `decide()` 입력으로 바꾸고 결과를 agy 출력 JSON으로 낸다.
   - `toolCall.name == "run_command"` → `{"tool_name":"Bash","tool_input":{"command": args.CommandLine}}`
   - `write_file` / `edit_file`(그 밖에 `Path` 인자를 가진 쓰기 도구) → `Write`/`Edit` + `file_path = args.Path`
   - `read_file` 등 → `Read`
   - `cwd`와 worktree는 `workspacePaths[0]`에서 얻는다. 이번 실험에서 `GS_WORKTREE`는 바깥 값(이 티켓의 worktree)이 그대로 들어왔다. 어댑터가 반드시 다시 설정한다.
   - 막으면 `{"decision":"deny","reason":"gs가 막음: …"}`, 아니면 `{"decision":"allow"}`. `GS_ROLE != worker`면 `{"decision":"allow"}`만 낸다(일반 agy 세션에 영향 없음). 종료 코드는 0이다. 실패하면 agy가 막아 주므로(fail-closed) 예외는 그냥 두어도 안전하다. 다만 정상 세션까지 막히지 않게 `GS_ROLE` 확인은 입력을 읽기 전에 한다.
   - `lastUserInput`은 보지 않는다.
   - 실험에 쓴 어댑터 시제품은 30줄 남짓이었다(§7 E3c).
3. hook을 둘 곳. 권고 순서:
   - (a) **agy 네이티브 plugin**(루트에 `plugin.json` + `hooks.json`, matcher `"*"`, 명령 `gs hook agy-pretooluse`)을 한 번 설치한다(`agy plugin install <dir>`). Claude plugin(09)과 같은 방식으로, `GS_ROLE=worker`일 때만 막는다. 09의 Claude plugin을 `agy plugin import`로 들여오는 것은 안 된다. 도구 이름(`Bash` vs `run_command`)과 출력 계약(종료 2 vs stdout JSON)이 다르다. plugin 로딩 자체는 [추정]이니 05에서 `agy -p /hooks`로 확인한다.
   - (b) 대안: `gs`가 worktree에 `.agents/hooks.json`을 쓰고 git exclude 파일에 넣는다(로딩은 [측정]). exclude 경로는 `git rev-parse --path-format=absolute --git-path info/exclude`로 얻는다. linked worktree에서는 `.git`이 디렉터리가 아니라 파일이라 `<worktree>/.git/info/exclude`는 없는 경로다(`ENOTDIR`) **[측정]**. `.agents`나 `hooks.json`이 심볼릭 링크이면 worktree 밖을 덮어쓸 수 있으니 거부한다. 이 경우 agent가 그 파일을 고쳐 커밋하거나 다음 실행(재시도)에 영향을 줄 수 있다. hook이 `.agents/` 쓰기를 막아야 한다.
4. `gs check`는 agy 티켓에서 hook이 실제로 걸려 있는지(`agy -p /hooks` 출력에 gs hook 줄이 있는지) 확인하고, 없으면 경고하고 agy 구현 worker를 거부한다.

**끝 판정**: 종료 0만 보면 안 된다. 성공은 다음을 모두 만족할 때다.
- 종료 코드 0
- 마지막 줄이 `event: result`이고 `status == "SUCCESS"`
- `finished_reason`이 없음(`print_timeout`/`interrupted`/`error`면 실패)
- 기존 규칙대로 브랜치에 커밋이 있음

`denied_actions`와 ERROR 상태 tool 단계는 실패 로그(07)에 붙인다. stderr 첫 줄의 `warning:`도 로그에 남긴다(모드 무시 같은 조용한 강등을 잡는다).

**막을 수 없는 경우의 대안**: (a)·(b) 모두 hook이 걸리지 않거나, 구조적 환경 차단이 없으면 agy는 **리뷰 전용**으로 쓴다. 기본 모드(`toolPermission` 기본값, skip-permissions 없음)에서는 셸 명령이 전부 자동 거부되고 workspace 읽기는 된다. 읽기가 된다는 것은 changelog에서 읽은 것이라 [추정]이다(2026-11-04에 **[측정]**으로 확인, §8). 리뷰에 셸이 필요 없으면 이 모드가 그대로 차단 장치다.

## 7. 실험 기록
모두 `gemini-3.8-flash-{low,medium}`, `--output-format stream-json`, `/tmp/agyexp.jDw1/` 아래 버리는 레포(원격 = `remote.git` 로컬 bare). 이 worker 셸의 `git push`는 09 hook에 막혀서(예상대로) 원격은 `git clone --bare`로 만들었다. 프롬프트는 "아래 명령을 그대로, 막혀도 우회하지 말고 차례로 돌려 표로 보고하라"는 식이다.

| # | 설정 | 결과 |
|---|---|---|
| E1 | `--mode auto`, 규칙 없음 | auto 불가 경고 → 기본 모드. 첫 `echo`부터 자동 거부, 모델 멈춤. 종료 0, `SUCCESS`, `denied_actions` |
| E2a | skip-permissions + deny `command(git push)` | 파일 생성·커밋 됨, `git push` 막힘. 종료 0 |
| E3a | E2a + push 변형 8개 | 막힘: 직접, `env`, `cd &&`, `--force` / push됨: `-C`, `sh -c`, 스크립트, python |
| E3b | skip-permissions + 문자열 grep hook | 8개 모두 막힘. 그러나 `lastUserInput`을 본 탓이라 무효. 이 실행과 E2a·E3a·E3c·E4의 `result`에는 `denied_actions`가 없었다(E1에만 있음) |
| E3c | skip-permissions + `decide()` 어댑터 hook | 막힘: `-C`, `sh -c`, 셸로 worktree 밖 쓰기 / 통과: python, alias, 파일 도구로 쓴 스크립트, 커밋, 파일 도구로 worktree 밖 쓰기(어댑터가 도구 이름을 잘못 앎 → E6에서 고침) |
| E4 | 고장 난 hook(종료 1 / 비JSON / 시간 초과) | 셋 다 도구 호출이 막힘(fail-closed). 종료 0 |
| E5·E7 | `--sandbox` + skip-permissions / proceed-in-sandbox, 일반 레포·`git worktree` | workspace 쓰기 막힘(커밋 불가), `/tmp` 원격 push 됨, 네트워크는 skip이면 열림·proceed-in-sandbox면 막힘. 프롬프트에 "sandbox 시험"이라 적은 두 번은 모델이 거절함 |
| E6 | E3c 어댑터 수정 + 파일 도구 | `read_file`/`edit_file`은 workspace 안 통과, `write_file`/`edit_file`로 밖에 쓰기 막힘 |
| E8·E9·E10 | sandbox: `$TMPDIR` workspace, `trustedWorkspaces`, 내 도구 sandbox 밖, git 아닌 디렉터리 | 모두 workspace 쓰기 막힘 |
| E11 | hook 환경, agent가 `.agents/hooks.json`을 `{}`로 덮어씀 | hook이 `GS_ROLE` 등 물려받음. 덮어쓴 뒤 `git push`도 막힘 |
| X1–X11 | 종료 코드·모델·강도 | §3.1, §4 |

다시 돌리려면 위 설정으로 같은 구성을 만들면 된다. 실험 스크립트는 레포에 넣지 않았다(티켓: 코드는 바꾸지 않는다).

## 8. 문맥 한도와 자동 압축 (2026-11-04)
계기: 레포 전체 리뷰를 맡긴 agy 답 10개 중 3개가 틀렸고, 있지도 않은 함수 이름을 인용했다(Codex는 같은 질문에 근거가 모두 맞았다). 측정은 agy 1.4.12(그 뒤 이 머신은 1.5.0으로 올랐고 1.5.0은 재지 않았다), `gemini-4-argon-high`, 기본 모드 + `--sandbox`, 한 번의 실행이다. 대화 기록(`~/.gemini/antigravity-cli/conversations/<id>.db`의 `steps`, `gen_metadata`)은 공개 형식이 아니라 읽어서 해석했다.

**결론**: agy 호출 한 번의 입력은 **약 8만 토큰 이하**로 잡는다. 약 25만 토큰이 넘으면 압축되고, 압축 뒤 답은 앞서 읽은 파일을 기억으로 인용한다. 압축이 일어나도 오류가 나지 않아 답만 봐서는 모른다. 8만은 가장 이른 압축 보고(아래 84,678)를 기준으로 한 보수적인 값이다.

### 8.1 한도
| 항목 | 값 | 근거 |
|---|---|---|
| Gemini 4 Argon 모델 한도 | 1,048,576 토큰(입력+출력 합산) | [Google 문서](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-4-argon) |
| agy 압축 기준 | 256,000 토큰 | **[측정]** `gen_metadata`의 값(이름표 없는 필드를 해석). [#1245](https://github.com/google-antigravity/antigravity-cli/issues/1245)의 `max_context_tokens = 256000`, [모니터 도구](https://github.com/AGI-is-going-to-arrive/Antigravity-Context-Window-Monitor)의 IDE 보고값과 일치. 공식 문서에는 없다 |
| 실제 압축 시점 | 대체로 235,000–279,000 | **[추정]** #1245 사용자 측정 |
| 더 이른 압축 | 84,678–115,605 | **[추정]** [#878](https://github.com/google-antigravity/antigravity-cli/issues/878) 무인 실행 보고 1건(agy 1.3.5) |
| 비교: Codex(gpt-6.1-sol) | 문맥 창 475,000 | **[측정]** 같은 질문에 최고 246,844 토큰, 압축 0회. 세션 기록 |

`contextWindow` 키는 `agy -p /config`에 비어 있다 **[측정]**. `/model`에서 512K·900K를 고르면 여기 저장되지만 압축은 여전히 약 25만이고, `AGY_CLI_AUTO_COMPACT_OVERRIDE`도 효과가 없다는 보고가 있다 **[추정]**(#1245, 시험 안 함). 관련 이슈는 2026-11-04 기준 모두 열려 있고 관리자 설명은 없다. 비공식 바이너리 패치는 쓰지 않는다.

### 8.2 이번 실행에서 일어난 일 **[측정]**
| 시점 | 문맥 토큰 | 일 |
|---|---|---|
| step 0 / 8 / 15 | 12,413 / 64,924 / 149,533 | 문서·spec·보고서 읽기 |
| step 24 / 33 / 42 | 181,197 / 220,999 / 266,212 | `src/gs` 읽기. 42에서 256,000을 넘음 |
| step 54 | 16,381 | `CHECKPOINT`: 약 70만 자가 11,249바이트 요약으로. 요약에 "27개 파일 모두 완독" |
| step 55–152 | 79,435까지 | skill·아이디어 읽기. `src/gs`는 다시 읽지 않음 |
| step 154 | - | 답 작성. 이 단계 입력 기록에 요약과 압축 뒤 파일은 있고 `go.py` 원문은 없다 |

- 인용한 함수 이름 9개 중 8개가 step 154에서 처음 나온다(git 역사에도 없다). `_required_checks`를 `_required_check_names`로 쓰는 식의 복원이다.
- 요약에 남은 사실과 압축 뒤 읽은 파일에 근거한 지적은 맞았고, 요약에서 빠진 코드에 대한 지적이 틀렸다. step 41에서 읽은 `_required_checks`는 rulesets도 읽는데 답은 "구식 API만 조회"라고 썼다.
- 모델은 요청한 그대로였다(`used_claude` false, 생성 14건 모두 Gemini 4 Argon High).
- 같은 현상의 독립 보고: [#1294](https://github.com/google-antigravity/antigravity-cli/issues/1294)는 압축 뒤 읽은 파일 인용이 원문과 100%, 압축 전 파일 인용이 0% 일치했다고 한다 **[추정]**(측정 방법 설명 없음). 거기서는 요약이 "파일이 메모리에 있다", "도구를 더 부르지 마라"고 알렸다고 하는데, 이번 요약에 그 문구는 없었다.

한계: 한 번의 실행이고 Codex와 조건이 달랐다(Codex는 셸이 있었다). "Gemini가 Codex보다 부정확하다"는 결론은 낼 수 없다. 압축이 없었으면 맞았을지도 이 기록으로는 모른다.

### 8.3 기본 모드 `-p`의 읽기 **[측정]**
`--dangerously-skip-permissions` 없이 `read_file`이 125회 돌았고 쓰기·셸은 쓰지 않았다. `read_file`은 한 번에 46,080바이트까지 주고 이어 읽는 방법을 알려 준다. 서브에이전트의 `find`는 거부됐다(`print mode, soft-denying`). 목록을 보지 못한 채 파일 이름을 추측해 23번이 `file does not exist`로 실패했고, v7·v8 실제 티켓을 한 장도 읽지 못한 채 티켓 내용을 언급했다. `list_dir`·`grep_search`는 한 번도 부르지 않았고, 이 모드에서 쓸 수 있는지는 **[모름]**.

### 8.4 쓸 때
- 레포 전체를 한 번에 맡기지 않는다. 영역별로 나눠 여러 번 부른다.
- 한 호출에 넣을 파일 목록을 직접 준다(셸이 없으면 이름을 추측한다).
- "인용 직전에 그 파일을 다시 읽고, 못 읽었으면 추정이라고 적어라"를 프롬프트에 넣는다.
- 답의 파일·함수·줄 번호가 실제로 있는지 기계로 먼저 본다. 가짜 이름은 잡히지만 진짜 이름으로 틀린 논리는 못 잡으므로 코드 대조는 여전히 한다.
- 결과가 중요하면 대화 기록에 `CHECKPOINT`가 있는지 본다. `stream-json`에는 압축 이벤트가 없다는 보고가 있다 **[추정]**([#1316](https://github.com/google-antigravity/antigravity-cli/issues/1316)). 큰 `-p` 메시지 하나가 약 19만 2천 자에서 오류 없이 잘렸다는 보고도 같은 곳에 있다.

리뷰처럼 입력이 diff·티켓·spec으로 좁은 호출은 같은 위험이 작아 보인다(지난 리뷰 결과를 따로 검사하지는 않았다). `/retro`의 로그 요약은 `.goldstack/ideas/retro-log-prep.md`.
