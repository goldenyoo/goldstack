---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v9 07 리뷰(codex) 보고만, goldstack-v10 grill에서 뺌"
status: "open"
feature: ""
---
사람이 첫 줄이나 위치를 고친 아이디어 파일은 티켓 재시도 때 같은 지적이 새 `open` 파일로 또 생길 수 있다.

**근거(코드 확인)**: `findings._assign`은 본문이 `head`로 시작하는지로 기존 파일을 찾는다. 재시도는 리뷰 기록을 비우므로 `idea_number`도 사라진다.

**다시 볼 때**: 자동 이관은 v9 뒤 설치본에서 처음 실제로 돈다. goldstack-v10 실행과 goldhud-v1에서 중복이 실제로 나오는지 먼저 본다. 고치려면 재시도를 넘어 지적 동일성을 유지하는 설계가 필요하다.
