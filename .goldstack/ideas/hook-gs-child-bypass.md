---
date: "2026-11-13"
severity: "high"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
0.2.19 worker hook은 `gs child` 앞붙이를 이용한 `GS_ROLE` 제거·`git push`를 막지 못한다(goldstack-v35 02가 보고만으로 병합).

- 2차 재리뷰(codex·agy 각자 재현, `.goldstack/work/goldstack-v35/report.md`의 02 리뷰 지적):
  - `gs child -- `를 다섯 번 이어 쓰면 `depth <= 3` 재귀 한도에서 검사 없이 통과한다. `bash -c` 안에서는 세 번.
  - `setsid gs child -- git push`, `env -u CLAUDE_EFFORT gs child -- git push`, `timeout -s KILL 5 gs child -- git push`, `exec -a x gs child -- git push`, `echo push | setsid xargs gs child -- git`: `[*lead, *inner]` 재조합 뒤 `strip_prefix`가 명령 이름을 `setsid`·`CLAUDE_EFFORT`로 읽는다.
  - `env -S`로 펼친 앞붙이 뒤 `GS_ROLE` 제거가 통과하고, `env -i -S "GS_ROLE=worker gs child -- claude -p hi"`는 오차단된다.
  - 1차 수정 `32111a9`에서는 막히던 형태다. 2차 수정 `07f78ee`의 회귀.
- 제안: hook이 `gs child` 안쪽을 재귀로 분해하지 않고 허용 목록으로 판정한다. 앞붙이 없는 `gs child -- claude …`·`gs child -- codex …`만 통과, 그 밖의 `gs child` 형태(앞붙이, 반복, 다른 내부 명령)는 막는다. 위 사례 전부를 시험으로 고정한다.

관련: [[final-rereview-high-not-merged]] [[hook-parse-ticket-grill-rule]]. 같은 결함의 리뷰 지적별 아이디어: [[goldstack-v35-02-5]] [[goldstack-v35-02-6]] [[goldstack-v35-02-14]] [[goldstack-v35-02-15]] (함께 taken으로 묶는다)
