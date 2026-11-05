---
date: "2026-11-05"
severity: "medium"
source: "/retro goldstack-v11"
status: "taken"
feature: "goldstack-v12"
---
`/retro`의 agy 요약 답이 커서 회고 세션의 문맥을 많이 쓴다.

**근거**: `/retro goldstack-v11`의 답이 91KB였고, `file://` 링크를 빼면 40KB였다. 51KB가 링크다. `/retro goldstack-v10` 때도 답 크기가 후보로 나왔다(파일 없음).

**제안**: `skills/retro/SKILL.md`의 agy 프롬프트에 형식과 길이를 적는다. 근거는 `L123`처럼 줄 번호만, 링크 없이, 답은 1만 자 안에. 이 길이로 충분한지는 다음 `/retro`에서 본다.
