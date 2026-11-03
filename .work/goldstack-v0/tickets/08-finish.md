---
id: "08"
title: "마무리: 보고서, 자동 병합, main 재검증, revert"
blocked_by: ["06", "07"]
model: codex
reviewer: claude
---
## 목표
모든 티켓이 끝나면 `gs`가 보고서를 쓰고 main에 병합하고, main이 깨지면 스스로 되돌린다.

## 완료 조건
- 판단 모델이 `.work/<f>/report.md`를 쓴다: 요약(가장 작은 그림), 티켓별 결과(merged·failed·skipped와 이유), 남은 리뷰 지적, `verify` 출력, 되돌리는 법. integration에 커밋한다.
- integration을 push하고 PR을 만들거나 갱신한다. PR 본문 = report.md.
- merged 티켓이 하나 이상이고 integration `verify`가 통과하면 `gh pr merge`로 병합한다. 병합 명령 뒤에 PR을 다시 읽어 실제로 merged인지 확인한다.
- 병합된 main을 임시 worktree에 받아 `verify`를 돈다. 실패하면 병합 커밋을 `git revert`한 커밋을 main에 push하고(force push 아님) 보고서와 PR에 남긴다.
- `gs go`는 끝날 때 세 줄 요약과 PR 링크를 출력한다.
- 시험: 로컬 bare 원격과 가짜 gh로 "병합 성공", "병합 뒤 main 검증 실패 → revert 커밋", "merged 티켓 없음 → 병합 안 함"을 확인한다.

## 범위 밖
- 알림(.out-of-scope/notifications.md).

## 참고
- spec §3(2-2, 3-6)
- docs/research/mattpocock-skills.md §3(pr 본문: Summary, Evidence, Merge Danger)
- docs/research/pstack.md §5(병합 뒤 다시 읽기)
