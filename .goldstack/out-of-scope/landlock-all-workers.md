# 모든 worker를 Landlock으로 가두기

**무엇**: Landlock 모드에서 agy worker와 claude worker도 `gs jail`로 띄워 자격 증명 경로를 가린다.

**왜 밖**: 이번 목표는 OS 샌드박스에 기대던 세 경로(codex worker, codex 리뷰, agy 리뷰)를 그 머신에서도 지금 수준으로 돌리는 것이다. agy·claude worker는 맥에서도 OS 샌드박스 없이 hook으로 돌고, 가두면 맥까지 동작이 바뀌는 별도 결정이다.

**다시 볼 조건**: agy·claude worker가 hook을 지나 자격 증명을 읽은 기록이 나오면.

결정: goldstack-v32 grill 라운드 3-1 (2026-11-12)
