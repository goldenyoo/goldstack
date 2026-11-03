---
id: "09"
title: "조사+opt-in 구현: codex worker hook 차단"
blocked_by: ["02", "06", "08"]
model: claude
reviewer: codex
---
## 목표
codex worker를 sandbox 대신 hook(위험한 명령만 막기)으로 돌릴 수 있는지 조사하고, 되면 config로 켤 수 있게 한다. 기본값은 지금 sandbox.

## 완료 조건
- `docs/research/codex-hook.md`: codex-cli 0.166.0의 hook(`codex features list`의 `hooks stable`)을 실제로 돌려 본 결과. 답할 것: (1) hook 명령이 실패·시간 초과·없음일 때 막는가(fail-closed) 통과하는가, (2) PreToolUse류가 셸 명령 밖(apply_patch 등 파일 수정)도 잡는가, (3) `codex exec` 무인 실행에서 hook 신뢰 확인 없이 걸리는가, (4) gs의 기존 차단(`gs hook pretooluse` 규칙: push, gh, 비밀 파일)을 그대로 쓸 수 있는가.
- 기준(1 fail-closed, 2 파일 수정도 잡음, 3 무인에서 걸림)을 모두 충족하면 구현: config `[codex] guard = "sandbox" | "hook"`(없으면 `sandbox`). `hook`이면 codex를 sandbox 없이(네트워크 허용) 돌리고 gs hook을 건다. hook이 걸렸는지 실행 전에 확인하고 못 걸면 그 티켓을 띄우지 않는다(agy와 같은 원칙). 명령 문자열·검사 시험. 기본 `sandbox`일 때 명령은 지금과 같다(시험).
- 기준 미충족이면 코드는 바꾸지 않고 문서에 막힌 항목과 다시 볼 조건을 적고, `.goldstack/ideas/codex-worker-hook.md`에 근거를 덧붙이고 `status: "open"`, `feature: ""`로 되돌린다.

## 범위 밖
- 기본값을 hook으로 바꾸기(spec 1-3: 사람이 정함)

## 참고
- spec §3 1-3, §6 codex worker·hook. touches: `src/gs/adapters.py` `src/gs/hook.py` `src/gs/config.py` `src/gs/cli.py` `docs/research/codex-hook.md`
