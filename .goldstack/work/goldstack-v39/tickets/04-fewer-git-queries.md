---
id: "04"
title: "setup.marker와 _tree_state의 git 호출을 줄인다"
blocked_by: ["03"]
touches: ["src/gs/setup.py", "src/gs/go.py", "tests/test_git_queries.py", "tests/test_setup.py", "tests/test_setup_tracked.py"]
tier: medium
model: codex
reviewer: claude
---
## 목표
티켓 검증 시간의 대부분인 git 프로세스 생성을 상태 판단을 바꾸지 않는 두 곳에서 줄인다(spec 결정 2-4, 3-1, 3-2, 아이디어 ticket-verify-ten-minutes).

## 완료 조건
- `setup.marker(wt)`가 git을 부르지 않고 `wt/.git`에서 git 관리 디렉터리를 구해, 지금처럼 그 아래 `gs-setup-done` 경로를 돌려준다: `.git`이 디렉터리면 그 경로, 파일이면 `gitdir: <경로>` 줄의 경로(상대 경로면 `wt` 기준으로 풀어 절대 경로). 돌려주는 경로가 `Path(git rev-parse --absolute-git-dir) / "gs-setup-done"`과 같다. 읽을 수 없거나 형식이 다르면 지금처럼 git에 묻는다.
- `go._tree_state(wt)`가 git 프로세스를 2개 이하로 띄우고, 돌려주는 4개 값(HEAD, HEAD가 가리키는 브랜치, MERGE_HEAD, index 트리)과 읽지 못한 값의 빈 문자열 규칙이 지금과 같다.
- `tests/test_git_queries.py`(새 파일): (1) 주 worktree와 `git worktree add`로 만든 연결 worktree, 그리고 `gitdir:`이 상대 경로인 `.git` 파일에서 `marker`가 `Path(rev-parse --absolute-git-dir) / "gs-setup-done"`과 같고 git을 부르지 않는다, (2) `_tree_state`가 브랜치 위, detached HEAD, 병합 충돌 중(MERGE_HEAD 있음), 커밋 없는 레포에서 옛 구현(시험 안에 4번 묻는 기준 함수로 둔다)과 같은 값을 돌려주고 git을 2번 이하로 부른다. git 호출 수는 `git.run`(또는 `subprocess`)을 감싸 센다. (1)·(2)의 호출 수 단언은 지금 구현으로 되돌리면 실패한다.
- spec §4 측정법으로 센 `test_final_high.py`의 git 프로세스 수가 8700 이하다(main 기준 9872). 측정 전후 수와 전체 시험 벽시계 전후(목표 아님)를 마지막 메시지에 적는다.
- `marker`·`_tree_state` docstring을 고친다.

## 범위 밖
- `_reset_integration` 건너뛰기, `git.sha` 캐시(범위 밖 reset-integration-skip)
- push 목적지 확인(`git.push_settings`)과 원격 url 조회. 안전 장치라 매번 묻는다
- 병합 대기 단계(03)

## 참고
- spec §3 결정 2-4·3-1·3-2, §4 git 호출 측정, §6 환경 사실
