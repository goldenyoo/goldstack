---
date: "2026-11-15"
severity: "high"
source: "/retro goldstack-v42"
status: "taken"
issues: []
feature: "goldstack-v43"
---
`test_verify.StaleTest`가 병렬 전체 검증(`xargs -P 6`)에서 다른 시험과 함께 돌면 "부모가 죽어도 검증은 살아 있어야 한다"(`test_verify.py` 283행 단언)가 흔들린다. goldstack-v42 01 실패의 직접 원인이다.

- goldstack-v42 01 verify.log: 2회 `test_cleanup_ends_every_verify_of_the_run`, 3회 `test_verify_of_a_feature_inside_a_worktree_stays`가 같은 단언으로 실패했다. 판별에서 test_verify만 따로 돌리면 OK(L1893–1900). 01 diff는 brief 문장과 그 시험뿐이다(retro subagent 보고).
- 재현(retro subagent, 맥미니): 혼자 연속 0/5, CPU 부하(`yes` 10코어) 0/4, test_verify 6벌 동시 3/6, 실제 xargs 이웃 6개 파일과 동시 1/3. 부하가 아니라 동시 실행 간섭이다. 어느 경로로 그룹이 죽는지는 미확인.
- `ps` 차단 아님: 수리 worker가 돌린 시험이 4.48초에 283행 단언으로 실패했다(`ps`가 막히면 120초 기다린 뒤 다른 메시지).
- [반복] goldstack-v36 `run/03/1/repair/verify.log` L617도 StaleTest 실패. 관련 열린 아이디어 `tests-no-wall-clock`은 같은 실패를 벽시계·부하 탓으로 봤으나 부하 실험과 맞지 않는다.
- 고칠 곳 후보: `tests/test_verify.py` StaleTest·`left_behind`, `tests/support.py` `group_alive`·`kill_group_quietly`에서 간섭 경로를 찾아 격리한다. 못 하면 verify 명령에서 이 클래스를 따로(직렬) 돌린다.
- 같은 실행의 다른 모양: 01·02 첫 검증이 같은 6개 파일(test_findings_ideas, finish_skip_verify, feedback_collect, async_review, final_high, finish_stages)에서 가짜 레포 `wt/integration`을 잃고 실패했다. 이것도 시험 간 경합으로 보인다(미확인).
