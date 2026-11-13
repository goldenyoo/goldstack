---
date: "2026-11-13"
severity: "high"
source: "goldstack-v35 리뷰 02"
status: "taken"
feature: "goldstack-v36"
---
gs child 내부 명령에 바깥 래퍼를 다시 붙이면서 기존 git push 차단을 우회하게 된다. env -u CLAUDE_EFFORT 또는 setsid 뒤의 gs child가 해당한다.

위치: src/gs/hook.py:1287
근거: worktree에서 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python으로 HEAD^와 최종 hook.decide를 비교했다. `env -u CLAUDE_EFFORT gs child -- git push`와 `setsid gs child -- git push` 모두 수정 전에는 '`git push`는 worker가 하지 않는다', 수정 후에는 None이었다. 새 `check_segment([*lead, *inner], ...)`가 래퍼를 재삽입하지만 strip_prefix는 각각 ['CLAUDE_EFFORT', 'git', 'push'], ['setsid', 'git', 'push']를 남긴다. 따라서 name이 git이 아니어서 1308행의 Git 검사를 건너뛴다.
판단: 2차 재리뷰의 새 지적: 더 고치지 않고 보고만 한다
보고서: .goldstack/work/goldstack-v35/report.md
