---
date: "2026-11-12"
severity: "medium"
source: "goldstack-v32 실행 뒤 대화(PR #57 CI 대기)"
status: "taken"
issues: []
feature: "goldstack-v33"
---
GitHub Actions 시험(`tests`)이 한 번에 13–20분 걸린다. 시험을 한 프로세스에서 순서대로 돌리기 때문이다. 파일별로 병렬 실행하고, 리눅스 전용 시험은 빠른 별도 job으로 떼어 내서 병합 전에 기다릴 수 있는 길이로 줄인다.

**근거**
- 최근 완료된 CI 40번이 한 번에 13–20분 걸렸다(`gh run list --limit 40 --status completed`, 2026-11-09–12). 시험 수와 시간: v32 전 `f797bdf`는 `Ran 2365 tests in 1210.393s`, PR #57 `74f41f2`는 `Ran 2472 tests in 1131.811s`.
- 워크플로는 `.github/workflows/tests.yml`의 `uv run python -m unittest discover -s tests`(순차) 한 줄이다. 로컬 verify는 `ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p`로 파일별 병렬이다. profile은 "순차 실행은 훨씬 느리니 쓰지 않는다"고 적었는데 CI만 순차로 남았다.
- 맥북에서 파일 111개를 `xargs -P 6`으로 하나씩 시간을 쟀다(2026-11-12, 스크립트는 그 세션 scratchpad `time1.sh`). 벽시계 608초, 파일 합 2731초(동시 실행이라 파일마다 부풀었다. 같은 시험이 CI 순차로는 약 1130초다). 모두 종료 0.
  - 느린 순서: `test_verify_repair.py` 246초, `test_review_target.py` 213, `test_protected_base.py` 187, `test_async_review.py` 129, `test_only_no_merge.py` 127, `test_recheck_resolved.py` 115, `test_resume_report.py` 103, `test_feedback_collect.py` 103, `test_issue_close.py` 96, `test_finish_stages.py` 95.
  - 위 5개가 합의 33%(902/2731)이고, 위 10개가 52%(1414/2731)다. 10초 안에 끝나는 파일은 67개다.
  - 그래서 병렬로 돌려도 벽시계 하한은 가장 느린 파일 하나(`test_verify_repair.py`)다. 느린 파일부터 띄우거나 그 파일을 나눠야 효과가 크다.
- 이 느림이 병합 관문을 막는다. 아이디어 [[ci-wait-linux-only-tests]]는 `wait_checks = true`를 다시 보자고 하면서 "CI 한 번이 약 20분이라 실행마다 그만큼 늘어난다"를 걸림돌로 적었다. goldstack-v32에서는 리눅스에서만 도는 Landlock 시험 9개가 병합 전에 한 번도 돌지 않았고, 병합 뒤 CI 4번이 같은 시험 하나로 빨갛게 끝났다(43170990820, 43170999523, 43171020014, 43172872166). PR #57로 고쳤다.

**생각(고를 것)**
1. CI도 파일별 병렬로 돌린다: `ls tests | grep '^test_' | xargs -P "$(nproc)" -n 1 python -m unittest discover -s tests -p`. 느린 파일부터 띄우게 목록 순서를 정한다(위 측정이나 이전 CI 시간). 리눅스에서 병렬 실행이 깨지지 않는지는 재지 않았다. 맥에서는 verify가 매번 이렇게 돈다. GitHub 공개 레포 `ubuntu-latest`는 4 vCPU라고 알고 있지만(GitHub 문서 기준) 재지 않았다.
2. 시험 파일을 matrix job 여러 개로 나눈다(예: 4개). 벽시계가 더 줄지만 job마다 설치 시간이 든다. 공개 레포라 분 단위 비용은 없다.
3. 리눅스 전용 시험(`test_jail.py`, `test_sandbox_launch.py`처럼 `skipUnless(리눅스·landlock)`인 것)만 도는 빠른 job을 따로 둔다. 1분 안팎이면 그 job만 병합 관문(`wait_checks`의 필수 검사)으로 삼고 전체 시험은 지금처럼 병합을 막지 않게 할 수 있다. [[ci-wait-linux-only-tests]]의 "실행마다 20분" 문제를 피한다.
4. 느린 통합 시험 자체를 줄인다. 범위 밖 `test-git-call-reduction`(시험의 git 호출 줄이기)의 다시 볼 조건이 "shim 우회 뒤에도 시험 대기가 실행 시간의 큰 비중이면"이다. 위 10개 파일이 그 후보다.

고칠 곳: `.github/workflows/tests.yml`(1–3), 느린 시험 파일(4). 3을 고르면 이 레포 `.goldstack/config.toml`의 `git.wait_checks`와 필수 검사 이름을 [[ci-wait-linux-only-tests]]와 함께 정한다.
