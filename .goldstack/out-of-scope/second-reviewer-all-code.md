# 두 번째 리뷰어를 코드 티켓 전부에 붙이기

**무엇**: `second_reviewer: agy`를 틀리면 바로 사고인 티켓 밖의 코드 티켓까지 넓힌다.

**왜 밖**: goldstack-v19 시험에서 agy만 찾은 fix 지적이 0건이었다(코드 5장, 호출 7회. 유일한 fix 지적 `agy-1`은 `codex-2`와 같은 결함). goldstack-v17의 2장도 0건이다. 일렬 경로는 약 14분 늘었다. 기준은 `skills/grill/templates/spec.md` 그대로 둔다.

**다시 볼 조건**: 사고 기준 밖 티켓에서 첫 리뷰어가 놓친 결함이 병합된 뒤 발견되고, 그것을 agy가 찾았을 근거가 나오면.

결정: goldstack-v20 grill 라운드 4-3 (2026-11-06)
