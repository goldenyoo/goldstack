---
id: "04"
title: "두 번째 리뷰어의 재리뷰 회차를 config로 줄이기"
blocked_by: ["02"]
touches: ["src/gs/config.py", "src/gs/go.py", "src/gs/review.py", "src/gs/check.py", "tests/test_second_reviewer_rereview.py", "tests/test_config.py", "tests/test_agy_config.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
config로 두 번째 리뷰어(티켓 `second_reviewer`)가 몇 차 재리뷰까지 직접 보는지 정하고, 빠지는 회차의 그 지적 판정은 같은 티켓의 다른 리뷰어에게 넘긴다(spec 결정 2-4, 아이디어 agy-rereview-slow).

## 완료 조건
- `.goldstack/config.toml`의 `[review] second_reviewer_rereview` 값 `"all"`(기본, 키가 없을 때도) · `"first"` · `"none"`. `"first"`면 두 번째 리뷰어는 1차 재리뷰까지만 불리고 2차 재리뷰·수리 재리뷰에서는 불리지 않는다. `"none"`이면 모든 재리뷰에서 빠진다. 다른 값은 `gs check`·config 읽기에서 오류다.
- 두 번째 리뷰어가 빠진 회차에 그 리뷰어 기록의 판정할 지적은 같은 티켓의 첫 리뷰어 재리뷰에 함께 실리고, 판정은 원래 기록의 지적에 적힌다(어느 리뷰어가 판정했는지 남긴다). 지적 id는 리뷰 기록마다 따로 매겨져 겹치므로(재리뷰 판정 파서는 겹치는 id를 오류로 본다), 합친 호출에는 호출용 고유 id를 주고 (원래 기록, 원래 id)로 되돌려 적는다. 첫 리뷰어도 부를 수 없으면(한도, 같은 계열) 지금처럼 `unchecked`다.
- 빠진 회차는 agy 호출 수(`[agy] max_calls_per_run`)에 세지 않는다. `gs check`의 agy 최악 호출 수 계산(`check.agy_problems`)도 이 값을 반영한다. `"all"`이면 출력 문구와 수(`배정 N × 3`)가 지금과 같다(`tests/test_agy_config.py`).
- `DEFAULT_CONFIG`(`gs init` 템플릿)는 바꾸지 않는다. `"all"`의 동작은 지금과 같다.
- `tests/test_second_reviewer_rereview.py`: 가짜 리뷰어 둘로 (1) `"first"`에서 2차 재리뷰에 두 번째 리뷰어 호출이 없고 그 지적이 첫 리뷰어 판정으로 resolved가 된다, (2) `"all"`은 지금처럼 둘 다 부른다, (3) 수리 재리뷰도 (1)과 같다, (4) 두 기록의 지적 id가 둘 다 1이어도 판정이 각 원래 지적에 맞게 적힌다. (1)은 회차 판정 코드를 되돌리면 실패한다. 재개(다음 `gs go`가 2차 재리뷰부터 잇는 경우)에서도 같은 리뷰어를 고른다.
- 관련 docstring(`go.py` 머리의 리뷰 절, `_plan_rereviews`, `_plan_repair_reviews`)을 고친다.

## 범위 밖
- 이 레포 `.goldstack/config.toml`에 값을 넣는 것(06), 문서(06)

## 참고
- spec §3 결정 2-4, `docs/guide.md` `second_reviewer` 절
