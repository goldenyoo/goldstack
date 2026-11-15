---
date: "2026-11-14"
severity: "high"
source: "/retro goldstack-v40"
status: "taken"
issues: []
feature: "goldstack-v41"
---
마지막으로 전체 검증을 통과한 integration head 뒤에 좁은 검증 티켓(문서·버전)만 병합됐는데도, 마무리의 integration 전체 검증을 다시 돈다.

- goldstack-v40: 03이 전체 검증을 통과한 뒤 들어온 것은 05(문서·버전, 좁은 검증 1초)뿐이었다. 그런데 `run/finish/integration-verify.log`가 약 640초 동안 전체를 다시 돌았고, 이 시간은 일렬 경로 끝에 붙는다(retro subagent 보고).
- 고칠 곳: `src/gs/finish.py`. 마지막 전체 검증 통과 head 이후의 변경이 좁은 검증 티켓의 touches 안뿐이면 integration은 좁게 돌거나 건너뛴다. main 검증의 "integration과 같은 코드면 건너뜀"과 같은 생각이다.
- 관련: taken `docs-ticket-narrow-verify`(v25에서 문서 티켓만 좁혔다).
