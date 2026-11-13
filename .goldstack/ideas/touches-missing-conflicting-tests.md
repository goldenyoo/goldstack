---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v36"
status: "open"
issues: []
feature: ""
---
동작을 바꾸는 티켓의 touches에 그 동작과 충돌하는 기존 시험 파일이 빠진다. worker가 충돌을 알려도 수정 루프를 끝까지 돌아 시간이 샌다.

- goldstack-v36 03의 touches(`tickets/03-final-rereview-high.md`)에는 `test_rereview`·`test_verify_repair`만 있다. grill 라운드 표 #6(spec.md 92행)도 이 두 파일만 찾았다. 기본 severity가 high인 `finding()` fixture를 쓰는 다른 3개 파일(`test_recheck_resolved.py`, `test_review_target.py`, `test_async_review.py`)은 놓쳤다.
- fix worker가 마지막 메시지(`run/03/1/fix/worker.log`)에서 시험 9개 충돌을 정확히 보고했다. 같은 실패가 fix2 검증(`fix2/verify.log`)에서도 나왔다.
- 그런데도 수정 2회, 검증 실패, 수리, 재검증을 다 돌아 약 44분이 늘었다. 리뷰어 양쪽이 같은 지적을 3회 연속 했다. 이 수치는 agy 요약에서 옮긴 것이다.
- [반복] goldstack-v35: 04 티켓의 `replay.py`가 touches 밖이라 미수리로 남았다.
- 고칠 곳 두 가지:
  - grill: 바뀌는 동작의 fixture·함수를 tests/에서 grep한 결과를 touches에 다 넣으라고 지시한다.
  - gs: worker의 `## 남긴 관찰`에 "touches 밖 시험이 완료 조건과 충돌"이 나오면 수정 루프를 끝까지 돌리지 않고 바로 수리(touches 제한 없음)로 보낸다.
- 범위 밖 `brief-auto-tests`의 다시 볼 조건("grep 규칙을 넣은 뒤에도 touches 밖 시험 실패가 병합 검증에서 반복되면")에 닿는다.
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
