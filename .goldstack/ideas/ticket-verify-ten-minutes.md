---
date: "2026-11-13"
severity: "medium"
source: "/retro goldstack-v37"
status: "taken"
issues: []
feature: "goldstack-v39"
---
티켓 검증이 티켓 크기와 무관하게 매번 약 10분 걸린다. worker가 36초인 small 티켓도 10분을 검증한다.

- goldstack-v37 검증 3회: 613.8 / 610.6 / 610.5초. 합계 약 30분으로 전체 2시간 21분 중 큰 몫이다.
- [반복] goldstack-v35 "07 worker 2분 · 검증 10분", goldstack-v36 "04 worker 10분 · 검증 10분"
- 고칠 곳: `.goldstack/config.toml`·spec frontmatter의 `verify` 명령. 느린 시험 파일을 재서 나누거나, tier small에는 좁은 검증을 쓴다.
- goldstack-v37이 검증을 스레드로 옮겼다. 겹침 효과는 다음 실행(0.2.21)에서 먼저 잰다. 관련 범위 밖: `ticket-verify-narrow`, `verify-concurrency-limit`, `verify-pipeline`
- 근거 출처: retro subagent 보고. 이 세션이 다시 확인하지는 않았다.
- 2026-11-13 goldstack-v38: 검증 7회 621–670초, integration 637초. 일렬 경로에 걸린 검증과 줄 대기가 약 70분으로 전체 198.8분의 약 35%. 검증 스레드는 자리가 하나(`go.py` `ThreadPoolExecutor(max_workers=1)`)라 겹친 것은 일렬 경로 밖 03·06뿐이었다 (출처: /retro goldstack-v38, subagent 보고)
