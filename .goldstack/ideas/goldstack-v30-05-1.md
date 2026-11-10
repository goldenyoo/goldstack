---
date: "2026-11-10"
severity: "medium"
source: "goldstack-v30 리뷰 05"
status: "open"
feature: ""
---
base에 병합되지 않은 integration 이력까지 후보에 포함하여, base 이력에 시작 commit을 확정할 병합이 하나뿐이어도 중복 후보 오류를 낸다. 폐기하거나 다시 만든 integration 브랜치가 남아 있으면 정상적인 지난 티켓의 자동 재생이 막힌다.

위치: src/gs/replay.py:143
근거: 티켓은 “config `[git] base` 이력에서 그 feature integration에 들어간 `Merge <NN>:` 커밋 M을 찾고”라고 요구한다. 그러나 143행은 base와 integration ref를 모두 refs에 넣고, 147행은 `git log ... *refs`로 이력을 합친다. 구현 worktree에서 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -B -`로 ReplayTestCase 기반 임시 저장소 재현을 실행했다. Merge 03을 main에 병합한 상태에서는 시작 commit `4517be9d3605…`를 반환했다. 이후 integration을 분기점에서 다시 만들고 main에 병합하지 않은 별도 Merge 03을 추가하자, main 이력은 그대로인데 `MissingCommitError: demo-v1/03의 Merge 03: 커밋이 2개다(024bac1bb8e0, 61fc01c …(일부 생략, 보고서에 전체)
판단: 재현은 됐지만 spec 2-1이 'integration의 Merge NN: 커밋'에서 찾으라고 정했고, 그 경우 integration ref를 검색에서 빼면 아직 base에 병합되지 않은 feature는 재생할 수 없게 된다. 또 다시 만든 integration에 Merge 03이 둘이면 후보와 --base 안내를 담아 예외를 내는 것이 티켓이 정한 '여럿이면 예외'에 맞으므로, 기대 동작이 무엇인지 판단할 수 없다.
보고서: .goldstack/work/goldstack-v30/report.md
