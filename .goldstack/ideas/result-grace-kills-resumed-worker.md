---
date: "2026-11-13"
severity: "high"
source: "/retro goldstack-v35"
status: "taken"
issues: [65]
feature: "goldstack-v36"
---
0.2.19의 유예 정리(goldstack-v35 06)는 백그라운드 작업을 기다리려고 턴을 끝냈다가 다시 깨어나 일하는 claude worker를 첫 `result` 60초 뒤에 죽이고 성공(종료 코드 0)으로 넘긴다.

- claude worker는 백그라운드 시험을 띄우고 턴을 끝내면 성공 `result`(`is_error: false`)를 낸다. 작업 알림(`system task_notification`)이 오면 다시 깨어나 이어서 일하고 `result`를 또 낸다.
- goldstack-v35(0.2.18로 실행, 유예 정리 전) worker 실행 13개 중 4개가 성공 `result`를 두 번 냈다: 02 worker, 06 worker, 06 수정 worker, 02 2차 수정 worker(`run/*/1/**/worker.log`의 `"type":"result"` 수).
- 06 수정 worker는 첫 `result`("Running 8 related test files in the background", duration 332초) 뒤 다시 깨어나 `git add … && git commit -qm "fix: 유…"`로 수정을 커밋했다. 단계 전체가 7분 28초라 두 `result` 사이는 약 90초다. 0.2.19였으면 커밋 전에 정리되고 종료 코드 0으로 리뷰에 넘어간다.
- 원인: `go.Active.result_seconds`가 "시계는 처음 본 때부터다: 그 뒤 로그가 자라도 다시 시작하지 않는다"(v35 06 티켓 완료 조건 "유예 중 로그가 다시 자라도 유예 시계는 처음 본 때부터다"를 그대로 구현). grill의 잘못된 결정이다.
- pod `seungjae2_62`의 `ha-rtl-plugin` `loop-1` worker 로그에는 `result`가 두 번인 것이 없었다(gs 0.2.16, 2026-11-13 확인).
- 당장: 0.2.19로 돌리기 전에 레포 config `[timeouts] result_grace_seconds = 0`(끔).
- 제안: 로그가 자라거나 브랜치 커밋이 바뀌면 유예 시계를 지운다(`Active.idle`과 같은 신호). 마지막 `system background_tasks_changed`의 작업 목록이 비어 있지 않으면 유예를 길게(또는 `idle_minutes`만) 본다. #65의 끝나지 않는 대기 루프는 그래도 로그가 멈춰 있으니 잡힌다. 시험: 성공 `result` → 90초 침묵 → 작업 알림 → 커밋 → `result`인 가짜 worker가 정리되지 않는다.

관련: [[herdr-process-group-check]]
