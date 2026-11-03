# 옛 위치 `.work/` 호환

**무엇**: `.goldstack/work/`가 없을 때 옛 `.work/`(그리고 `.out-of-scope/`, `.ideas/`)도 읽기.

**왜 밖**: 옛 위치를 쓰는 레포는 goldstack 자신 하나이고 `gs migrate` 한 번이면 된다. 호환 코드는 두 경로를 영구히 들고 가게 만든다.

**다시 볼 조건**: `gs migrate`를 돌릴 수 없는 레포(예: 옛 위치를 쓰는 다른 도구와 공존)가 생기면.

결정: goldstack-v2 grill 라운드 1-1 (2026-11-03)
