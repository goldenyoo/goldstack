---
date: "2026-11-04"
severity: "medium"
source: "2026-11-04 Codex 리뷰(Claude가 코드 대조)"
status: "taken"
feature: "goldstack-v10"
---
보호된 base에서 revert PR이 승인을 기다리는 동안 base가 고쳐져도, 다음 `gs go`가 재검증 없이 옛 revert를 병합한다.

**근거(코드 확인, 재현 안 함)**: `finish._postmerge`는 `revert_sha`가 있고 `revert_head`와 같으면 바로 `_revert_pr`로 돌아간다. 최신 base를 다시 검증하는 `main-recheck`는 그 아래에 있어 닿지 않는다. 대기 중 base가 고쳐지는 경우를 다루는 시험은 찾지 못했다(Codex가 `test_protected_base.py`를 근거로 지적).

**시나리오**: main 검증이 실패해 revert PR이 열린다. 사람이 승인 전에 별도 커밋으로 main을 고친다. 다음 `gs go`가 통과할 base를 확인하지 않고 revert를 병합해 정상 기능을 지운다.

**제안(M)**: revert PR이 아직 OPEN이고 base SHA가 실패 당시와 다르면 최신 base를 재검증한다. 통과하면 revert PR을 쓰지 않고, 계속 실패하면 최신 base 기준으로 revert를 다시 만든다. 이미 병합된 revert는 따로 다룬다. Codex는 high로 냈지만 보호된 base와 사람의 개입이 겹칠 때만 생기고 되돌릴 수 있어 medium으로 낮췄다.
