---
date: "2026-11-05"
severity: "medium"
source: "goldstack-v8 07 리뷰(claude) 보고만 3건, 2026-11-05 코드 대조"
status: "open"
feature: ""
---
티켓 `closes`의 issue가 되돌린 수정에서 닫힌 채 남거나, 직접 반영한 티켓에서 안 닫힌다.

**근거(코드 확인)**:
- `finish._close_without_pr`는 `finish.url`이 있으면 바로 돌아간다. 앞 PR 뒤에 PR 없이 base에 반영된 티켓의 issue는 닫히지 않는다.
- 같은 함수는 `gs-ticket` 표시로 닫을 번호를 고르고 revert 여부를 보지 않는다. base에서 되돌린 티켓의 issue도 닫힐 수 있다.
- `src/gs`에 issue를 다시 여는 코드가 없다. PR 병합으로 닫힌 issue는 base 검증 실패로 revert해도 닫힌 채고, `gs backlog`는 열린 issue만 본다.

**다시 볼 때**: 2026-11-05 기준 `field-report` issue는 0건이고 `closes`를 쓴 실제 실행 기록은 확인하지 않았다. `url` 조건을 빼면 gs가 되돌린 PR의 issue를 닫을 수 있어 세 건을 함께 봐야 한다.
