---
date: "2026-11-07"
severity: "medium"
source: "/retro goldstack-v20"
status: "taken"
issues: []
feature: "goldstack-v21"
---
`/overnight`과 `/go` 글이 단어 상한에 닿아, 다음 티켓은 글을 깎다가 문구 시험을 깨뜨린다.

- 2026-11-07 main: `overnight` 1705/1710, `go` 525/530.
- v20 03 worker는 04가 더할 자리를 남기려고 문장을 깎다가 `test_go_retro_step_and_overnight_skips_it`를 깼다. 04 fix는 7단어 초과를 깎다 시험 2개를 깼고 코드 리뷰가 잡아 수정 기회 하나를 썼다.
- 반복: goldstack-v11(`skill-word-limit-visibility`, `goldstack-v11-09-2`). 범위 밖 `skill-text-pin-removal`의 다시 볼 조건("문구 시험 때문에 티켓이 또 실패")이 찼다.

고칠 곳: 다음 `/overnight`·`/go` 티켓 전에 grill에서 상한을 올릴지, 글을 나눌지, 문구 시험을 줄일지 정한다.
