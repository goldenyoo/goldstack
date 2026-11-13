---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
명령 문자열을 분해하는 차단 hook 티켓은 리뷰 라운드마다 새 우회와 회귀가 나온다. grill이 tier와 판정 방식을 미리 정해야 한다.

- goldstack-v35 02(medium, sonnet/high): 리뷰 3라운드, 1시간 26분. 수정마다 `check_segment`에 재귀 분기를 더했고 그 분기가 회귀 A–E를 만들었다(바깥 리다이렉션 검사 건너뜀, `xargs -I` 방어 깨짐, 재귀 한도 fail-open, `lead` 재조합; `run/retro-log.md` L278, L476).
- grill 빈틈: 새 래퍼 명령 `gs child`를 hook이 어떻게 판정할지 정하지 않고 통과 목록에 `gs child -- claude -p …`만 적었다(v35 02 티켓).
- 제안: `skills/grill/templates/spec.md` §5 주석에 (1) "차단 hook의 명령 분해를 바꾸는 티켓은 large", (2) "새 래퍼 명령을 만들면 hook이 그것을 어떻게 판정할지 grill에서 정한다. 재귀 분해보다 허용 목록을 먼저 고른다".

관련: [[hook-gs-child-bypass]]
