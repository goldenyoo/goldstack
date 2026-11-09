---
date: "2026-11-09"
severity: "low"
source: "/retro 세션(grill goldstack-v26~v28, overnight 2026-11-08)"
status: "taken"
issues: []
feature: "goldstack-v29"
---
/retro가 쓴 아이디어에 재현 명령이 잘린 채 남아 다음 grill이 재현하지 못한다.

- `hook-missed-agy-findings`의 놓침 3건 중 `""time …`은 명령이 `…`로 잘려 v28 grill이 재현하지 못했다(v28 spec §6). 나머지 둘은 원문이 있어 바로 재현됐다.

고칠 곳: `skills/retro/SKILL.md` 4단계(아이디어로 쓸 때) 또는 `skills/idea/templates/idea.md`: 근거에 재현 명령·입력이 있으면 줄이지 않고 원문을 코드로 남긴다.
