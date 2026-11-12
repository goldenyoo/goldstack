# 티켓 검증 좁히기

**무엇**: `verify_ticket`으로 티켓 검증을 좁히고 전체 시험은 integration에서만 돌린다.

**왜 밖**: v11에서 좁은 검증이 `/adopt` 상한을 놓쳐 병합이 멈췄고, 끝에서 실패하면 어느 티켓 탓인지 찾는 비용이 생긴다. integration 전체 검증이 실패하면 수리 없이 feature 전체가 병합 안 함으로 끝난다. goldstack-v32 03의 실패(`test_tiers`)는 티켓 `touches` 밖 시험이라 좁은 검증이면 integration까지 갔다. 느린 파일을 먼저 띄우는 순서는 측정에서 더 느렸다(595초 대 864초, goldstack-v33 spec §6).

**다시 볼 조건**: integration 검증 실패를 수리하는 길이 생기면.

결정: goldstack-v18 grill 라운드 3 (2026-11-06), 조건 수정 goldstack-v33 grill 라운드 1-9 (2026-11-12)
