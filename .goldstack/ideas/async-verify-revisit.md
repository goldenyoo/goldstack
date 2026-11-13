---
date: "2026-11-10"
severity: "medium"
source: "/retro goldstack-v31"
status: "open"
issues: []
feature: ""
---
[반복] 검증이 도는 동안 코디네이터가 다른 worker 결과를 처리하지 못한다. out-of-scope `async-verify`를 v30·v31 수치로 다시 꺼낸다.

- goldstack-v31: 04 worker가 111초 만에 끝났으나 처리 대기 559초. 01 검증 구간(15:00:41–15:10:00)과 겹친다(report 시도별 표, `run/state.json`).
- 같은 구간에 02 worker가 부하로 `test_replay_run` 1회 실패(단독 11초, 부하 중 46초; `run/retro-log.md` L125–132).
- goldstack-v30: 351–590초 대기 7번. v10–v15에도 있었고, v11의 `verify-blocks-result-wait`는 측정만 더했다.

관련: [[async-verify-evidence]] [[ticket-verify-narrow-revisit]]
- 2026-11-13 goldstack-v33(147분, 티켓 검증 10번이 일렬로 각 590–640초): 처리·결과 대기 03/1 worker 1184초, 05 worker 644초, 02 fix 629초, 02 재리뷰 601초, 07 리뷰 569초, 03/2 worker 420초. 02는 low 지적 하나의 실제 수정이 72초인데 fix·재리뷰에 23분이 걸렸다 (출처: /retro goldstack-v33, report 측정 표·`run/retro-log.md` L113–L115)
- 2026-11-13 goldstack-v35(128분): 01–07 검증 약 10분씩 일곱 번이 차례로 돌았다(약 70분). 그 사이 처리·결과 대기: 02 worker 508초, 02 첫 리뷰(codex·agy) 554초, 03 첫 리뷰 572초. 리뷰·재리뷰 끝 시각이 앞 검증 끝 시각(08:02:27, 08:14:45, 08:54:21, 09:14:12)에 맞물린다 (출처: /retro goldstack-v35, report 측정 표·`run/retro-log.md` L11, L52–L58)
