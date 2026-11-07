---
date: "2026-11-07"
severity: "medium"
source: "/retro goldstack-v20"
status: "taken"
issues: []
feature: "goldstack-v21"
---
새 예외 이름이 `_KIND_WORDS` 낱말 규칙에 걸리는데 규칙이 `src/gs/feedback.py` 안에만 있어, 티켓마다 전체 시험에서야 알게 된다.

- v20에서 3장이 `test_every_exception_class_of_gs_is_a_valid_kind`에 걸렸다. 01 `_Unreadable`(gs 검증 실패, 수리와 재검증에 약 20분), 02 `QueueError`와 03 `StepFailed`(첫 worker의 전체 시험에서 걸림, 03은 후보 이름 10개를 돌려 맞춤).
- `docs`, `.goldstack/profile.md`, skill에 규칙이 없다.
- v20 티켓 08 뒤로는 첫 worker가 전체 시험을 돌리지 않아, 02·03 같은 실패도 gs 검증까지 간다.

고칠 곳: `.goldstack/profile.md` 관례에 한 줄, 시험 실패 메시지에 `_KIND_WORDS`, spec `verify`의 빠른 앞부분에 `test_feedback_format.py`(약 3초).
