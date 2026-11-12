# 샌드박스를 끄는 설정

**무엇**: OS 샌드박스가 없는 머신에서 codex를 가두지 않고 `danger-full-access`로 돌리는 설정(예: `[codex] sandbox = "off"`).

**왜 밖**: gh 인증이 살아 있는 머신에서 push·병합을 막는 장치가 환경 변수(`GIT_CONFIG_*`, 틀린 `GH_TOKEN`)뿐이고 `unset`으로 풀린다. codex hook은 fail-open이다(docs/research/codex-hook.md). 같은 머신에서는 Landlock 모드가 자격 증명을 가려 대신한다.

**다시 볼 조건**: Landlock도 쓸 수 없는(커널 미지원) 머신에서 codex를 꼭 돌려야 하게 되면.

결정: goldstack-v32 grill 라운드 1-10, 2-3 (2026-11-12)
