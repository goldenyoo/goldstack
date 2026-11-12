---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v33 /retro goldstack-v34"
status: "taken"
issues: []
feature: "goldstack-v35"
---
worker hook의 시험 파일 10개 상한(`[hook.worker_tests] max_files`)이 닿는 시험을 모두 돌리라는 brief 규칙과 부딪혀 worker가 명령을 쪼개거나 일부를 못 돌린다.

- goldstack-v33 05: 시험 파일 여러 개를 한 명령으로 돌리려다 막혀 "관련 높은 일부"로 줄여 돌렸다(`run/retro-log.md` L781–L782: "The worker hook caps a command at 10 test files. Splitting into a smaller, most-relevant set.").
- goldstack-v34 04: 13개를 두 번에 나눠 돌렸다(`run/retro-log.md` L317–L320).
- goldstack-v33 08: 편집 스크립트 글에 전체 시험 명령 문구가 들어 있어 Bash 한 번이 막혔다(오차단, `run/retro-log.md` L1151–L1152).
- goldstack-v33 03이 넣은 규칙("바꾼 이름을 `tests/`에서 grep해 나온 시험 파일을 모두 파일마다 돌린다")은 10개를 쉽게 넘긴다.

고칠 곳: brief에 "시험 파일이 10개를 넘으면 명령을 나눠 돌린다"를 넣거나, 상한을 실제 필요(전체 순회 막기)에 맞게 다시 본다. 범위 밖 `hook-word-parser`(본문 판정 오차단)와 함께 본다.
