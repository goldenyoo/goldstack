# 모델 밖 기본값도 doctor로 갱신

**무엇**: `[agy] max_calls_per_run` 같은 모델이 아닌 기본값도 옛 기본값 이력으로 `gs doctor`가 제안하고 `--write`로 바꾼다.

**왜 밖**: goldstack-v34는 `[models]`·`[tiers.*]`만 다룬다. 모델 밖 기본값은 바꿀 계획이 없다.

**다시 볼 조건**: 모델 밖 기본값을 바꿀 일이 생기면.

결정: goldstack-v34 grill 라운드 1 (2026-11-12)
