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
- 2026-11-16 이 머신에 남은 검증 로그 227개 중 이 모양은 goldstack-v42 01·02 둘뿐이다. 한 실행에서 서로 다른 임시 폴더 5개가 통째로 사라졌다(`not a git repository`, `Unable to read current working directory`): 파일 몇 개가 아니라 임시 레포 전체다. v42 worker·리뷰어 기록에 임시 폴더를 지우는 명령이 없고, `src/gs`·`tests`에 공용 임시 루트를 훑어 지우는 코드가 없다. 전체 시험 5회(병렬 6 세 번, 병렬 10 두 번, 다른 gs 실행 없음)에서는 재현되지 않았다. (출처: goldstack-v44 grill 라운드 1-5)
- 2026-11-16 goldstack-v44 03 첫 전체 검증에서 `test_overnight_cmd` setUp의 push 직후 `git clone`이 `fatal: failed to copy file to '…/upstream/.git/objects/…': No such file or directory`로 실패했고 판별 뒤 전체가 다시 통과했다(802초 실패 + 837초 통과). 그 시간대에 다른 티켓·검증은 없었다. 모양은 임시 레포 통째가 아니라 객체 파일 하나다. git 2.54의 `git push`가 `git maintenance run --auto --detach`를 띄우는데 시험 공용 git 환경에 `maintenance.auto=false`가 없다(`tests/test_jail.py`에만 있다). 그것이 원인인지는 재현하지 못했다(retro subagent 보고). (출처: /retro goldstack-v44)
- 2026-11-16 goldstack-v45 05가 시험 공용 git 환경에 `maintenance.auto=false`를 둔다. 원인 확정이 아니라 위생 수리라 이 아이디어는 열어 둔다. v45 뒤에도 같은 모양이 검증 로그에 나오면 maintenance는 원인에서 뺀다. (출처: goldstack-v45 grill 라운드 1-2)
