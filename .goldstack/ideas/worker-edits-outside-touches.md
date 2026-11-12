---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v33 /retro goldstack-v34"
status: "taken"
issues: []
feature: "goldstack-v35"
---
worker가 touches 밖의 `docs/internals.md`를 고쳐 병렬 티켓끼리 병합 충돌이 난다. brief가 touches를 알려 주지 않고 profile은 오히려 고치라고 지시한다.

- goldstack-v33 03 시도 1: `CONFLICT (content): Merge conflict in docs/internals.md`로 실패(`run/03/1/failure.log`). 버린 worker 39분 + 다시 한 시도 41분(opus로 승급).
- 문서는 grill이 마지막 티켓(v33 08, v34 05)에 맡겼는데, v33 02·03·04와 v34 02·03이 모두 `docs/internals.md`를 고쳤다(`git log -- docs/internals.md`: 2212587, 1428948, d703aef, c269950, 096e921).
- worker brief(`src/gs/worker.py` `write_brief`)에는 touches가 한 줄도 없다. `.goldstack/profile.md` 39행은 "동작을 바꾸면 docstring과 `docs/internals.md`도 고친다".
- v30–v32 보고서에는 병합 충돌이 없다(이번이 처음).

고칠 곳:
- brief에 그 티켓의 `touches`와 "touches 밖 파일은 고치지 않는다. 고쳐야 하면 마지막 메시지에 적는다".
- profile 39행: docstring은 고치고, `docs/internals.md`는 touches에 있을 때만.
- (선택) 리뷰 기준: touches 밖 변경을 지적. 범위 밖 `touches-required-in-go`와 함께 본다.
