---
date: 2026-11-04
severity: high
source: goldstack-v5 report.md 남은 위험(04 리뷰 agy high, 재현됨)
status: "taken"
feature: "goldstack-v6"
---
보호된 base(`git.direct_push = false`)에서 `report_pending`·`merge_pending`을 회복하면 base에 병합된 보고서 PR 커밋이 integration에 합쳐지지 않아, 이어지는 실행이 `report.md` 충돌로 멈추거나 보고서가 base와 어긋난다.

**무슨 일이 나나** (v5 04 리뷰가 시험 fixture로 재현)
- `finish.py`의 `report_pending` 분기가 보고서 PR을 base에 병합한 뒤 그 커밋을 integration worktree(`r.iwt`)에 합치지 않고(`merge_base` 없이) 돌아간다. `_report_to_base`도 `merge_base` 뒤에 돈다.
- `go.py`는 회복(`_finish_run(r, cleanup=False)`) 뒤 `finished`가 참이면 `_loop(r)`와 두 번째 `_finish_run(r)`을 무조건 실행한다.
- (1) 남은·실패한 티켓이 이어서 돌면 새 feature PR이 `report.md`에서 base와 충돌해 병합 실패(`merge_pending`), 다음 `gs go`는 `origin/main를 gs/<f>/integration에 합치다 충돌했다: … report.md`로 멈춘다.
- (2) 돌 티켓이 없어도 두 번째 `_finish_run`이 phase `verified`라 회복 분기를 건너뛰고 `_update`로 integration의 report.md와 PR 본문을 다시 써서 base판과 달라진다.
- 재현 명령은 v5 report.md Evidence(04 리뷰 agy [high])에 있다(`test_protected_base.test_report_pr_blocked_by_approval_then_resumes` 변형).

**왜 아직 안 고쳤나**: 04 수정 단계가 "go.py 회복 흐름과 `_update` 재실행을 한 번에 고치면 재리뷰 없이 회귀할 위험이 크다"고 보류. direct push에서도 merged 회복 뒤 새 티켓이 돌면 보고서 커밋이 integration에 없는 것은 같아, 기존 설계 문제와 얽혀 있다.

**고칠 방향 후보**: 회복 분기(`report_pending`·`merge_pending`·`merged` 등)에서 반환 전에 base를 integration에 합친다(`merge_base`). 회복이 verified로 끝났으면 같은 실행에서 `_loop`·두 번째 `_finish_run`을 돌지 않는다(새 티켓이 있으면 base를 합친 integration 위에서). 시험: 위 재현 경로, direct push의 merged 회복 + 새 티켓.

**같이 볼 v5 지적**: 04 medium — 승인 대기 때 저장한 `finish['error']`가 재개 뒤 병합 성공 시 지워지지 않아 최종 보고서에 옛 거부 메시지가 남는다. 04(재리뷰 없음) — 보고서 PR을 만든 뒤 난 오류(`_poll_checks` 등)를 `verified`·`base_report_tried=True`로 처리해 병합 안 된 보고서 PR이 남은 채 성공으로 끝난다.
