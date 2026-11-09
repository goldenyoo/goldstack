---
date: "2026-11-09"
severity: "low"
source: "/retro 세션(grill goldstack-v26~v28, overnight 2026-11-08)"
status: "taken"
issues: []
feature: "goldstack-v29"
---
밤샘이 끝나면 설치본이 마지막 feature보다 한 버전 뒤처진다.

- overnight 2026-11-08: v28 병합 뒤 main은 0.2.12인데 설치본은 0.2.11. 사이 단계의 `gs overnight next`만 `gs self-update`를 하고, 7단계(아침 보고)에는 없다. v28의 worker noequals는 사람이 `gs self-update`를 칠 때까지 쓰이지 않는다.
- `gs doctor`가 "설치본이 main보다 뒤처짐"을 경고하므로 다음 실행 사전 점검에서는 잡힌다.

고칠 곳: `skills/overnight/SKILL.md` 7단계, `gs overnight disarm` 앞에 `gs self-update`(실패는 결과를 바꾸지 않고 아침 보고에 적는다). overnight `WORD_LIMITS` 1880, 지금 1705단어.
