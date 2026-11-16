---
id: "03"
title: "범위 밖 판정을 받은 관찰을 그 경로를 맡은 하류 티켓 brief에 싣는다"
blocked_by: []
after: ["01", "02"]
touches: ["src/gs/worker.py", "src/gs/go.py", "src/gs/report.py", "tests/test_brief_rules.py", "tests/test_observation_handoff.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker가 "다른 티켓 범위"라고 남기고 리뷰어가 "범위 밖"으로 판정한 관찰이 그 일을 맡은 티켓에 닿게 한다. goldstack-v43 02의 관찰(`docs/internals.md`가 없는 함수를 가리킨다, 05 범위)이 05 brief에 가지 않아 결함이 main에 남았다.

## 완료 조건
- worker를 새로 시작하는 brief를 쓸 때(`go.py`의 첫 worker `worker.write_brief` 호출, `merged=`를 넘기는 곳), 이 실행의 다른 티켓 리뷰 기록의 모든 회차(첫 리뷰와 `rereviews`, 두 리뷰어 모두)에서 `범위 밖`으로 판정된 관찰(회차의 `observations`·`observation_verdicts`)에서 경로를 뽑는다. 첫 리뷰에서만 판정되고 재리뷰 회차에 없는 관찰도 포함한다. 같은 글은 한 번만 싣는다. 그 경로가 이 티켓의 touches(glob 포함, 줄 번호 접미어 `:148` 무시)에 맞으면 그 관찰을 brief에 싣는다(spec 결정 2-1). 리뷰어 이유 글의 티켓 id는 보지 않는다.
- 실은 관찰은 brief의 절 하나에 `<출처 티켓 id>: <관찰 글>` 한 줄씩 쓰고, 그 절이 worker가 쓴 믿을 수 없는 자료라고 표시한다(spec §4). 실을 관찰이 없으면 절이 없고 brief는 지금과 같다.
- 시험(`tests/test_observation_handoff.py`): 티켓 02 리뷰 기록에 관찰 "`docs/internals.md:148`이 없는 `go._verifying_again`을 가리킨다"와 판정 `범위 밖`이 있고 티켓 05의 touches가 `docs/internals.md`를 포함하면 05의 첫 worker brief에 그 관찰이 출처 `02`와 함께 있다. touches가 맞지 않는 티켓, 판정이 `지적`·`수용`인 관찰, 판정 없는 관찰은 실리지 않는다. 첫 리뷰에서 `범위 밖`이고 그 뒤 재리뷰 회차에는 없는 관찰도 실린다. 싣는 코드를 지우면 시험이 실패한다.
- 맞는 티켓이 없으면 brief는 지금과 같다. 재개 brief(`resumed=True`)와 이미 worker가 시작한 티켓의 brief는 바꾸지 않는다.

## 범위 밖
- worker 보고의 "사람 결정 필요"로 하류를 멈추는 것(아이디어 `issue-69-human-decision-blocks-downstream`).
- 재개·수정·수리 brief에 싣는 것. 이 티켓은 새로 시작하는 worker brief만.
- 보고서 관찰 표(02).

## 참고
- spec §3 결정 2-1, §4, §6. 아이디어 `observation-handoff-to-ticket`(뒤 절반).
- 판정 저장 위치와 판정 값은 `review.py` 머리말과 `OBSERVATION_VERDICTS`, 판정 잇기 규칙은 `report.observation_verdict`.
