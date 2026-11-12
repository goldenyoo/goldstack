# Landlock으로 네트워크 막기

**무엇**: Landlock ABI 4(커널 6.7부터)의 TCP bind·connect 제한으로 가둔 worker의 네트워크를 막는다.

**왜 밖**: #55의 pod 커널은 5.15라 ABI 1뿐이다(2026-11-12 측정). codex·agy 자신은 모델 API에 닿아야 해서 명령만 따로 막을 수도 없다.

**다시 볼 조건**: landlock 모드를 쓰는 머신의 커널이 6.7 이상이 되면.

결정: goldstack-v32 grill 라운드 2-7 (2026-11-12)
