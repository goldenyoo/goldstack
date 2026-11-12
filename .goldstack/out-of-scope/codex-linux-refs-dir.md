# 리눅스 codex worker의 refs 디렉터리

**무엇**: 리눅스에서 `refs/heads/gs`가 실행 중 사라지면 codex worker가 커밋하지 못할 수 있다.

**왜 밖**: 리눅스에서 codex worker를 돌려 본 적이 없어 이번 무인 실행으로 재현·검증할 수 없다. 부모 `refs/heads`를 여는 것은 ref 보호를 약하게 할 수 있다.

**다시 볼 조건**: pod의 landlock 모드에서 codex worker가 `cannot lock ref`로 커밋하지 못하면. (goldstack-v32가 리눅스 codex worker를 landlock으로 열었다. 쓰기 목록은 지금과 같은 디렉터리라 같은 위험이 남는다. pod 측정에서는 커밋이 됐다.)

결정: goldstack-v22 grill 라운드 1-2 (2026-11-07). 조건 갱신: goldstack-v32 grill 라운드 3-4 (2026-11-12)
