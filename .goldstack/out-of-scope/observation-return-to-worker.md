# 관찰을 worker에게 되돌리기

**무엇**: worker가 `## 남긴 관찰`에 touches 안 결함을 적으면 gs가 리뷰 전에 그 관찰을 worker에게 되돌려 고치게 한다.

**왜 밖**: 원인은 brief에 "고쳐라"는 말이 없던 것이다. brief 한 줄(goldstack-v42 01)로 먼저 본다. 되돌리기는 재개 상태를 바꾸는 large다.

**다시 볼 조건**: goldstack-v42 01 규칙 뒤에도 worker 관찰이 그대로 리뷰 fix 지적이 된 일이 보고서·회고에 나오면.

결정: goldstack-v42 grill 라운드 2-1 (2026-11-15)
