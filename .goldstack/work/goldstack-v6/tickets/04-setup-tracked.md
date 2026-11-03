---
id: "04"
title: "setup이 추적 파일을 바꾸면 되돌리고 경고, 티켓 worktree remember, doctor·/adopt 권고"
blocked_by: ["03"]
touches: ["src/gs/setup.py", "src/gs/go.py", "src/gs/finish.py", "src/gs/doctor.py", "skills/adopt/**", "tests/test_setup_tracked.py"]
model: codex
reviewer: claude
---
## 목표
setup의 부작용(lockfile 갱신 등)이 verify 실패·revert·티켓 실패·worker 커밋으로 번지지 않게 한다.

## 완료 조건
- setup 직후 추적 파일이 바뀌었으면(`git status --porcelain`의 추적 항목) 그 파일들을 `git checkout -- <파일>`로 되돌리고 `경고: setup이 추적 파일을 바꿨다 → 되돌림: <파일들>`을 출력하고 보고서에 남긴다(티켓은 그 티켓 결과, integration·base는 Merge Danger 또는 남은 위험). 설치 산출물(untracked·ignored)은 그대로.
- 시험: setup이 추적 파일(`lock.txt`)을 고치는 가짜 레포에서 (1) 병합 뒤 base 검증이 통과하고 revert하지 않는다, (2) integration에서 티켓이 "worker가 integration worktree를 바꿨다"로 실패하지 않는다, (3) 티켓 worker 커밋에 `lock.txt` 변경이 섞이지 않는다.
- 티켓 worktree(`go._start`)도 setup 뒤 `setup.remember`를 해, 병합 뒤 정리(`_cleanup_merged`·`_drop_kept`)가 setup 산출물 때문에 worktree를 dirty로 보고 `kept_worktrees`에 남기지 않는다(시험).
- `gs doctor`와 `skills/adopt/SKILL.md`: setup 명령에 `npm install`·`yarn`(lock 갱신형)이 있으면 `npm ci`·`yarn --frozen-lockfile`·`uv sync --locked` 같은 lock을 바꾸지 않는 명령을 권하는 한 줄.

## 범위 밖
- 기준선 비교 방식(spec 1-6에서 뺌)

## 참고
- spec §3 1-6, §6 ② setup, 아이디어 `setup-tracked-change-revert`
- 시험 도우미: `tests/test_setup.py` `WorktreeSetupTest.configure`
