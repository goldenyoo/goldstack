---
date: "2026-11-07"
severity: "low"
source: "/retro goldstack-v20"
status: "taken"
issues: []
feature: "goldstack-v21"
---
수정 worker가 지적이 요구하지 않은 설명을 코드 확인 없이 커밋해, 재리뷰의 새 지적과 2차 수정으로 이어진다.

- v20 06 fix의 마지막 메시지에 "이 남긴 문장은 코드로 확인하지 않고 내가 쓴 설명이다"가 있고, 그 `verify_ticket`·`-P` 문장이 지적 4(`docs/guide.md:277`)가 되어 fix2로 갔다.
- 재리뷰에서 새 지적이 나온 회차: v20 3/11, v19 3/8, v15 2/7. 모두가 이 원인인지는 세지 않았다.

고칠 곳: `src/gs/worker.py` fix brief에 "지적이 요구하지 않은 새 동작 설명은 쓰지 않거나, 쓰면 코드 줄을 확인한다"를 넣는다.
