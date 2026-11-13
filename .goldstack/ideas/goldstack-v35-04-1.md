---
date: "2026-11-13"
severity: "medium"
source: "goldstack-v35 리뷰 04"
status: "taken"
feature: "goldstack-v36"
---
touches 안내를 `merged is not None`에 묶어, `gs replay`가 띄우는 첫 구현 worker에는 touches 목록과 범위 밖 수정 금지 규칙이 빠진다. replay는 수정·수리 worker가 아니므로 해당 예외에 속하지 않는다.

위치: src/gs/worker.py:174
근거: 티켓 완료 조건은 “첫 worker·재개 worker brief에 그 티켓의 touches 목록”과 범위 밖 수정 금지를 요구한다. 그러나 구현은 `if merged is not None and t.touches else ""`이며, 실제 replay 호출(src/gs/replay.py:571)은 `worker.write_brief(job, spec, feature, DETACHED)`로 merged를 생략한다. 구현 worktree에서 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -B`로 touches=['src/a.py','tests/test_a.py']인 Ticket의 brief를 임시 폴더에 생성해 비교했다. merged=[]이면 목록·금지 문장·src/a.py가 모두 존재했지만, replay와 같이 merged를 생략하면 세 항목 모두 False였다.
판단: 재현은 됐지만 replay worker가 touches 줄을 받아야 하는지 판단할 수 없다. 티켓과 spec 3-4는 '첫 worker·재개 worker' brief만 말하고 replay는 언급하지 않는다. 기존 docstring은 replay를 merged=None 쪽(수정·수리와 같은 묶음)으로 명시하고, replay 결과는 병합되지 않는 detached 측정이다. 게다가 고치려면 고칠 수 있는 파일 밖인 src/gs/replay.py의 호출 방식도 바꿔야 한다.
보고서: .goldstack/work/goldstack-v35/report.md
- 2026-11-13 제안: `replay.py`가 `merged=[]`를 넘기거나, brief의 touches 줄 조건을 `merged`와 떼어 티켓 touches만으로 정한다 (출처: /retro goldstack-v35)
