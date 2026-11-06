---
date: "2026-11-06"
severity: "medium"
source: "/retro goldstack-v19"
status: "taken"
issues: []
feature: "goldstack-v20"
---
claude 첫 worker도 전체 시험을 돌리지 않고 gs 검증에 맡긴다. 범위 밖 `first-worker-no-verify`의 다시 볼 조건이 찼다.

- 전체 시험을 뺀 v19 codex 02·05는 worker 4분·1분이었고 첫 검증에 통과했다. 표본은 2장이고 티켓 크기가 달라 직접 비교는 어렵다.
- claude worker는 v17 03·05가 51분, 04가 33분, v18이 16–24분, v19가 8–28분이었다. v17 03은 전체 시험을 4번 시도했다. gs는 약 7분 걸려 같은 시험을 병합 트리에서 다시 돌린다.
- worker의 전체 시험이 부하(v17 부하 평균 21)와 [[worker-machine-wide-kill]]의 동기를 만들었다. v18 05는 전체 시험의 종료 코드를 파이프로 잃어 실패를 놓쳤으니 돌려도 보장이 아니다.

되돌릴 조건: 뺀 뒤 티켓 첫 검증 실패가 늘어 수리 시간이 줄어든 시간을 넘으면 되돌린다.
