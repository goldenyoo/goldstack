---
date: "2026-11-10"
severity: "medium"
source: "goldstack-v30 grill 라운드 2-5"
status: "open"
issues: []
feature: ""
---
`gs replay`(goldstack-v30)로 지난 large 티켓 3–4개를 `opus/xhigh`와 `fable/high`로 한 번씩 재생해 비교하고, 그 결과로 이 레포 `[tiers.claude] large`를 바꿀지 정한다.

순서와 되돌릴 조건은 `fable-large-tier-trial`(taken, goldstack-v30)의 "합의한 순서" 1–5단계를 그대로 따른다.
- 후보(v20–v28 large): v22 01·02, v25 03, v26 01·02, v27 01·03, v28 01·02. 수리·재시도 흐름과 hook·설정을 섞어 고른다.
- 예: `gs replay goldstack-v27/03 --worker claude:fable/high --usage 41,44`, 다른 호출이 없을 때 `/usage` 주간 %를 전후로 읽는다.
- 결과: `.goldstack/trials/replay.md`의 행. 재생은 수정·재리뷰를 하지 않으니 총시간 대신 fix 수를 본다(범위 밖 `replay-full-pipeline`).
- 먼저 `git pull`과 `gs self-update`로 0.2.14 이상인지 확인한다.

**관련**: [[fable-large-tier-trial]], [[model-tiering]]
