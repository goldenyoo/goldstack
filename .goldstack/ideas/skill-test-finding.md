---
date: "2026-11-07"
severity: "low"
source: "/retro goldstack-v20"
status: "taken"
issues: []
feature: "goldstack-v21"
---
skill 글을 고칠 때 돌릴 시험을 찾기 어렵다. 수정 worker는 티켓 `touches`도 받지 못한다.

- `.goldstack/profile.md` 19줄과 `tests/test_skills.py` 1줄은 `test_skill_<이름>.py` 목록만 안내하는데 `tests/test_overnight_skill.py`는 그 이름도 목록도 아니다. overnight 문장 일부는 `test_skill_go.py`가 단언한다(v20 03에서 실패).
- v20 04 fix는 `test_skills.py`만 돌리고 `profile.md`를 열지 않아, 시험 2개를 깬 채 커밋했다.

고칠 곳: `profile.md` 19줄과 `test_skills.py` 1줄에 overnight 시험을 더하고, `src/gs/worker.py` fix brief에 티켓 `touches`의 시험을 돌리라고 넣는다.
