---
date: "2026-11-06"
severity: "medium"
source: "/retro goldstack-v18"
status: "taken"
issues: []
feature: "goldstack-v21"
---
좁은 `verify` 티켓이 전체 시험을 깨고 병합되어 뒤 티켓이 연쇄로 실패한다. `gs check`가 설정 파일을 고치는 티켓의 좁은 검증에 경고한다.

- v18 04는 `.goldstack/config.toml`을 고치고 `gs config … | grep`으로만 검증해 병합됐다. `tests/test_tiers.py`가 레포 설정과 기본값이 같다고 단언해 01·02·03의 첫 검증이 같은 시험에서 실패했고, 03은 3번째 시도에 들어갔으며 v18을 다시 돌렸다.
- 범위 밖 `ticket-verify-narrow`에 v11의 같은 유형(좁은 검증이 `/adopt` 상한을 놓침)이 적혀 있다.

고칠 곳: `src/gs/check.py` 경고와 `skills/grill/templates/spec.md`의 `verify` 규칙. 깨진 integration을 티켓마다 따로 수리해 충돌한 일도 이 경우에 함께 일어났다.
