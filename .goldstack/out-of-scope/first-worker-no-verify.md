# 첫 구현 worker의 전체 시험 제거

**무엇**: claude 첫 구현 worker도 전체 시험을 돌리지 않고 gs 검증에 맡긴다. codex 첫 worker는 goldstack-v18에서 뺐다.

**왜 밖**: 시험을 안 돌린 코드의 실패율을 아직 모른다. "30장 중 검증 실패 1건"은 전체 시험을 돌린 뒤의 값이다. codex에서 먼저 본다.

**다시 볼 조건**: goldstack-v19의 codex 구현 티켓에서 전체 시험 없이 빠져나간 회귀가 늘지 않았으면.

결정: goldstack-v12 grill 라운드 2-2 (2026-11-05), goldstack-v18 grill 라운드 2-1 (2026-11-06)
