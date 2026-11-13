---
date: "2026-11-13"
severity: "low"
source: "/retro goldstack-v35"
status: "taken"
issues: []
feature: "goldstack-v36"
---
goldstack-v35 06(성공 `result` 뒤 끝나지 않는 worker 정리)은 herdr 실행기 경로에서 확인되지 않았다.

- 시험용 가짜 herdr가 프로세스 그룹을 나누지 않고 실제 herdr는 시험에서 띄울 수 없어, 고아 자식 통합 시험은 `SubprocessRunner`만 검증했다(`run/retro-log.md` L1080, L1103, 원본 `run/06/1/fix/worker.log`). herdr pane에서 run.sh가 프로세스 그룹 리더라는 것은 worker의 가정이다(`report.md` 남은 위험).
- 제안: 맥미니와 리눅스 pod의 실제 herdr pane에서 run.sh의 pid·pgid·sid를 한 번 잰다. 다르면 06의 정리 경로를 고치고 가짜 herdr를 실제에 맞춘다.
- 2026-11-13 goldstack-v36 grill 측정(맥북): herdr pane의 run.sh `bash`가 프로세스 그룹 리더(pid = pgid, 터미널 전경 그룹)다. 가정이 맞아 티켓 없음. pod는 재지 않았다(spec §6)
