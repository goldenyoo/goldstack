---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v9 07 리뷰(codex) 보고만, goldstack-v10 grill에서 뺌"
status: "taken"
feature: "goldstack-v14"
---
사람이 첫 줄이나 위치를 고친 아이디어 파일은 티켓 재시도 때 같은 지적이 새 `open` 파일로 또 생길 수 있다.

**근거(코드 확인)**: `findings._assign`은 본문이 `head`로 시작하는지로 기존 파일을 찾는다. 재시도는 리뷰 기록을 비우므로 `idea_number`도 사라진다.

**다시 볼 때**: 자동 이관은 v9 뒤 설치본에서 처음 실제로 돈다. goldstack-v10 실행과 goldhud-v1에서 중복이 실제로 나오는지 먼저 본다. 고치려면 재시도를 넘어 지적 동일성을 유지하는 설계가 필요하다.

- 2026-11-05 첫 관측: goldstack-v11 09의 재시도에서 같은 `CLI 기본값` 지적이 문장만 달라 `goldstack-v11-09-1`과 `goldstack-v11-09-3` 두 파일이 됐다. 사람이 고치지 않아도 재시도마다 리뷰어 문장이 달라 생긴다. 이 지적은 네 시도 모두 나왔다. 티켓의 "`CLI 기본값`으로 적는다"와 "실제 실행과 같은 함수"가 충돌해 매번 보고만으로 분류된 것이다. `goldstack-v11-09-1`은 `dropped`로 합쳤다. (출처: /retro goldstack-v11)
