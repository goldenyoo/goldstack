---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v33 /retro goldstack-v34"
status: "open"
issues: []
feature: ""
---
codex worker 로그에 해가 없지만 worker를 헷갈리게 하는 환경 잡음 세 가지가 매번 나온다.

- codex가 goldstack 플러그인의 hook 설정을 읽다 실패한다. 호출마다 첫 줄에 나온다(v33 02, v34 02·03 `worker.log` L3):
  ```text
  failed to parse plugin hooks config /Users/goldenyoo/.codex/plugins/cache/goldstack/goldstack/0.2.16/hooks/hooks.json: unknown field `modules`
  ```
  codex worker는 hook이 아니라 sandbox로 막으므로(`docs/internals.md` 계열 표) 해는 없다.
- 커밋할 때 `error: Unable to create '…/.git/packed-refs.lock'`가 찍히지만 커밋은 된다(v34 02 L85).
- sandbox 안에서 `.venv/bin/gs check <f>`가 `오류: 이 머신에서 codex 샌드박스가 동작하지 않는다(WARNING: proceeding, even though we could not create PATH aliases…)`로 실패한다. worker가 `GS_SANDBOX_PROBE=pass`로 다시 쳐서 넘어갔다(v34 03 L37, L45).

고칠 곳: codex worker용 안내 한 줄(profile 또는 brief): "sandbox 안 `gs check`는 `GS_SANDBOX_PROBE=pass`로, 위 hooks·packed-refs 경고는 무시해도 된다". hooks 파싱 실패는 codex 쪽이라 기록만.
