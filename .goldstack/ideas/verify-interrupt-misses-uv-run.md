---
date: "2026-11-07"
severity: "medium"
source: "/retro goldstack-v21"
status: "taken"
issues: []
feature: "goldstack-v22"
---
goldstack-v21 티켓 04의 끊김 판정은 이 레포의 `verify`를 잡지 못하는데, 보고서는 끊긴 검증을 다시 돌린다고만 쓴다.

- `src/gs/verify.py`(integration) 주석: `uv run`처럼 자식의 신호를 종료 코드로 옮기는 명령을 xargs가 띄우면 줄이 남지 않아 일반 실패로 보인다(worker 실측). 이 레포의 `verify`가 `xargs … uv run python`이다. grill 결정 2-5는 `xargs sleep`만 재고 정했다.
- 04 worker는 마지막 메시지에 이 한계를 적었지만 `report.md`로 옮겨지지 않았다.
- 원래 아이디어 `verify-killed-by-signal`의 목표는 이 레포에서 아직 미달이다. `goldstack-v21-04-2`(종료 코드 0)와 고칠 곳이 겹친다.

고칠 곳: 끊김 판별 재설계(예: `verify`에서 `uv run`을 빼고 `.venv/bin/python`을 쓰는지, gs가 자식 종료를 직접 보는지)와 worker 마지막 메시지의 "결정할 것"을 보고서로 옮기는 경로.
