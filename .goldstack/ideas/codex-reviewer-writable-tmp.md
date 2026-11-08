---
date: "2026-11-08"
severity: "medium"
source: "/retro goldstack-v25"
status: "taken"
issues: []
feature: "goldstack-v27"
---
codex 리뷰어가 읽기 전용 sandbox라 임시 디렉터리를 못 만들어 시험으로 재현하지 못한다.

- v25 06 리뷰: "test_skill_grill.py 전체 실행은 임시 디렉터리 생성 제한으로 import 단계에서 중단". 02 재리뷰: "전체 시험은 실행하지 않았다".
- 반복: v15 리뷰 2건, v17 리뷰 4건.

고칠 곳: `src/gs/review.py`의 codex 리뷰 호출(`-s read-only`). 쓰기 가능한 곳을 임시 폴더 하나로 한정해 연다(workspace-write + writable_roots). 리뷰 대상 worktree는 계속 쓰지 못해야 한다.

근거는 /retro subagent가 실행 기록으로 확인했다고 보고한 것이다. 이 파일을 쓴 세션은 따로 검증하지 않았다.
