# gs remote check의 샌드박스 점검

**무엇**: `gs remote check <머신>`의 원격 점검에 샌드박스 행을 더한다.

**왜 밖**: #55의 pod에서는 grill과 `/go`를 pod 안에서 직접 한다(goldstack-v32 1-2). 그 경로는 `gs check`·`gs go`·`gs doctor` 점검이 덮는다.

**다시 볼 조건**: `gs remote go`로 샌드박스 없는 머신에 띄우게 되면.

결정: goldstack-v32 grill 라운드 1-4 (2026-11-12)
