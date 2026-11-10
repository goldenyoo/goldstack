# hook deny 정규식 줄바꿈 기본 포함

**무엇**: `hook.py` `check_worker_tests`가 모든 `[hook.worker_tests]` deny 정규식을 `re.DOTALL`로 맞춰 `.`이 줄바꿈도 넘게 한다.

**왜 밖**: 다른 레포가 쓴 정규식의 뜻까지 바꾼다. v30은 이 레포 config의 순회 규칙 하나만 `[\s\S]*`로 고쳤다.

**다시 볼 조건**: 다른 deny 규칙이나 다른 레포에서 줄바꿈 변형으로 차단을 통과한 기록이 나오면.

결정: goldstack-v30 grill 라운드 1-3 (2026-11-10)
