---
id: "09"
title: "plugin 뼈대와 worker 차단 hook"
blocked_by: ["02"]
model: claude
reviewer: codex
---
## 목표
goldstack을 Claude Code plugin으로 설치할 수 있고, worker로 도는 claude는 되돌릴 수 없는 일을 하지 못한다.

## 완료 조건
- 레포에 plugin 구조(매니페스트, hook 설정)가 있고 로컬 marketplace로 설치하는 방법이 README에 있다.
- PreToolUse hook은 `gs hook pretooluse`를 부른다(별도 런타임 없이 설치된 `gs` 사용).
- `GS_ROLE=worker`일 때만 차단한다. 대상: `git push`(모든 형태), force 계열(`--force`, `--force-with-lease`, `push -f`), `gh` 쓰기 명령(pr create·merge, release 등), worktree 밖 쓰기, 비밀 파일 읽기(`~/.ssh`, `.env` 등). 차단 메시지는 이유와 "이 일은 `gs`가 한다"를 말한다.
- `GS_ROLE`이 없으면 아무것도 하지 않는다(일반 세션에 영향 없음).
- `gs`가 claude worker를 띄울 때 `GS_ROLE=worker`를 넣는다. 02의 임시 도구 차단 옵션은 남겨 둔다(이중 장치).
- 시험: hook 입력 JSON → 판정 단위 시험. 실제 있었던 형태(`git push origin HEAD`, `git push --force-with-lease`, `gh pr merge 3`, `cd .. && git push`)가 모두 막히고 일반 명령(`git commit`, `git log`, `uv run …`)은 통과한다.

## 범위 밖
- skill(10), codex·agy 차단(그쪽은 sandbox·11).

## 참고
- spec §3(3-1)
- docs/research/pstack.md §7("Prove each new check fails on a real past mistake")
- docs/ORIGINS.md 실패 10(분류기가 정상 작업을 막음): 막는 것은 되돌릴 수 없는 일뿐
