# 리눅스 codex worker의 refs 디렉터리

**무엇**: 리눅스에서 `refs/heads/gs`가 실행 중 사라지면 codex worker가 커밋하지 못할 수 있다.

**왜 밖**: 리눅스에서 codex worker를 돌려 본 적이 없어 이번 무인 실행으로 재현·검증할 수 없다. 부모 `refs/heads`를 여는 것은 ref 보호를 약하게 할 수 있다.

**다시 볼 조건**: 리눅스에서 codex worker를 쓰게 되거나 그 환경에서 커밋 실패가 나오면.

결정: goldstack-v22 grill 라운드 1-2 (2026-11-07)
