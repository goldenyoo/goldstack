---
date: "2026-11-15"
severity: "medium"
source: "goldstack-v43 grill 라운드 1-11"
status: "open"
issues: []
feature: ""
---
병렬 전체 검증에서 여러 시험 파일이 각자 임시 가짜 레포의 `run/wt/integration` 파일을 잃고 FileNotFoundError로 실패한다. 원인 미확인.

- goldstack-v42 01 첫 전체 검증(`run/01/1/verify.log` 160행 부근): test_findings_ideas, test_finish_skip_verify, test_feedback_collect, test_async_review, test_final_high, test_finish_stages 6개. 예: `…/T/tmp7w7mgz6v/repo/.goldstack/work/demo/run/wt/integration/.goldstack/work/demo/report.md` 없음. `.state.*.tmp`도 사라졌다(agent 보고, 172·243·326행).
- `StaleTest`의 `ps` 행 오집힘(goldstack-v43 01)으로는 설명되지 않는다. 그 결함은 프로세스 그룹을 잘못 고를 뿐 파일을 지우지 않는다(agent 보고).
- 그때 티켓 02의 전체 검증이 동시에 돌았을 수 있다(미확인).
- 다시 볼 것: goldstack-v43 01·02 병합 뒤에도 같은 모양이 검증 로그에 나오면, 공용 정리 경로(worktree prune·rmtree)와 새는 GIT_* 환경 변수를 먼저 본다.
