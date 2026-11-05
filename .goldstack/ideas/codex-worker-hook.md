---
date: "2026-11-03"
severity: "medium"
source: "goldstack-v2 grill 라운드 2 질문"
status: "taken"
feature: "goldstack-v10"
---
codex worker를 sandbox 대신 hook으로 막기(agy처럼 deny+hook). 먼저 조사: codex hook이 fail-open인지, PreToolUse가 Bash 밖(apply_patch)도 잡는지, 무인 실행의 hook 신뢰(--dangerously-bypass-hook-trust). 되면 localhost 시험·git 디렉터리 우회가 사라진다

출처: goldstack-v2 grill 라운드 2 질문

## goldstack-v4 09 조사 결과 (2026-11-04, codex-cli 0.166.0) — 보류, 다시 연다

자세한 기록: `docs/research/codex-hook.md`.

- fail-open이다(막힌 이유). hook이 종료 1·시간 초과·kill·깨진 stdout·명령 없음이면 도구 호출이 그대로 실행되고, `--json` 이벤트·stderr·세션 기록에 흔적이 없다. 막는 길은 종료 2 + stderr, `permissionDecision: "deny"` JSON 둘뿐이다. sandbox를 빼면 hook 프로세스의 사고 하나로 push·gh가 나간다.
- apply_patch는 잡힌다: `tool_name: "apply_patch"`, `tool_input.command`에 패치 본문. 다만 지금 `gs hook pretooluse`는 이 도구를 몰라 통과시킨다(worktree 밖 Add File이 실제로 생김). 패치 머리줄 경로를 Write/Edit 판정으로 넘기는 번역이 필요하다.
- 무인 실행: `-c 'hooks.PreToolUse=[…]'`로 이 실행에만 걸 수 있다(사용자 설정 안 건드림). 신뢰 없으면 조용히 빠지고, `--dangerously-bypass-hook-trust`면 걸린다. 모델 호출 없이 hook이 걸렸는지 확인하는 수단은 없다.
- 셸 명령 차단(push, gh 쓰기, 비밀 파일 읽기)은 `gs hook pretooluse`를 그대로 쓸 수 있다. 입력 모양·종료 2 계약이 Claude Code와 같다. `GS_ROLE`·`GS_WORKTREE`도 hook에 전달된다.

다시 볼 조건: codex가 hook 실패를 막음으로 다루는 동작이나 설정을 내면(연구 문서 §4의 네 가지 실패 모드를 다시 돌려 확인).

- 2026-11-04 codex worker에는 비밀 파일 읽기 차단이 없다. `codex sandbox`(macOS, 0.166.0, 기본 정책)에서 임시 비밀 파일 `cat`은 되고 쓰기만 막혔다(worker의 `-s workspace-write`와 정책이 같은지는 추가 확인 필요). `docs/internals.md`의 "worker 차단 hook이 이 파일 읽기를 막는다"는 codex에 맞지 않는다. 위 조사와 다른 안: sandbox를 빼지 않고 그 위에 `gs hook pretooluse`를 겹치면 쓰기·네트워크는 sandbox가 그대로 막고 비밀 읽기만 보태어 막는다. hook이 fail-open이라 보조 장치이고, `--dangerously-bypass-hook-trust`가 필요하다 (출처: 2026-11-04 Gemini 리뷰, Claude가 재현)

- 2026-11-05 goldstack-v10 grill 1-6: 문서 수정만 v10에 넣었다. hook 겹치기는 범위 밖 `codex-secret-hook`, sandbox를 hook으로 대신하는 안은 위 조건대로 보류다.
