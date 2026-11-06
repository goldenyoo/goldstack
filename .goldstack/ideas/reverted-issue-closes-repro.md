---
date: "2026-11-06"
severity: "high"
source: "goldstack-v15 리뷰 02(agy), goldstack-v12–v15 아침 보고"
status: "open"
issues: []
feature: ""
---
되돌린 티켓의 issue가 다음 PR의 `Closes #N`으로 다시 닫히는데 보고서는 `다시 엶`으로 남는지, 재현 시험으로 확인한다.

**근거**: goldstack-v15 02의 agy high 지적이다(`src/gs/finish.py`의 `_pr_body`). 같은 지적을 낸 codex는 수정 뒤 재리뷰에서 해결로 확인했지만, agy 재리뷰는 호출 상한 3/3으로 건너뛰어져 보고서에 `확인 못 함(한도)`로 남았다. 고쳐졌을 가능성이 높지만 확인되지 않았다.

**제안**: 사람이 재현 시험으로 확인하기로 했다(2026-11-06). 다음 feature의 첫 티켓으로 둔다. 시나리오: 티켓 병합 → PR 병합으로 issue 닫힘 → 그 티켓을 base에서 되돌림 → gs가 다시 엶 → 다음 PR 병합 뒤 issue가 열려 있고 보고서와 같은지 본다. 같은 issue를 다른 티켓이 함께 `closes`한 경우도 넣는다. 재현되면 그 티켓에서 고친다.

관련: [[agy-limit-counts-rereview]]
