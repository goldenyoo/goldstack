---
id: "05"
title: "변이 확인은 새 시험 하나로, grill은 충돌 시험을 touches에 넣는다"
blocked_by: []
touches: ["src/gs/worker.py", "tests/test_fix_brief.py", "tests/test_brief_rules.py", "skills/grill/templates/spec.md", "tests/test_skill_grill.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
worker가 "되돌려 실패를 본다"를 넓은 시험 묶음으로 돌려 시간을 쓰고 캐시로 거짓 통과를 보는 일을 brief 규칙으로 막고(결정 2-6), grill이 동작을 바꾸는 티켓의 touches에 그 동작과 충돌하는 기존 시험 파일을 넣게 한다(결정 2-5). 아이디어 worker-mutation-test-cost, touches-missing-conflicting-tests.

## 완료 조건
- `worker.SEE_FAIL_RULE`에 다음이 더해진다: 되돌린 상태에서는 새 시험 하나(그 시험 파일, 가능하면 그 시험 이름)만 돌린다, 넓은 묶음이나 전체 시험을 돌리지 않는다, 언어의 캐시·빌드 산출물이 옛 코드를 쓰지 않게 한다. 특정 언어 이름이나 환경 변수는 적지 않는다(레포 profile이 맡는다).
- 모든 brief(구현·수정·수리)에 고친 규칙이 실린다. `tests/test_brief_rules.py` 또는 `tests/test_fix_brief.py`가 새 문장을 단언하고, 문장을 지우면 실패한다.
- `skills/grill/templates/spec.md` §5 주석의 touches 줄에 "동작을 바꾸는 티켓은 바뀌는 함수·fixture·상수 이름을 시험 폴더에서 grep해 나온 시험 파일을 touches에 넣는다"를 더한다. `skills/grill/SKILL.md`는 고치지 않는다(단어 상한 550, 지금 495).
- `tests/test_skill_grill.py`가 템플릿의 그 문장을 단언하고, 지우면 실패한다.
- `worker.py`의 brief 규칙 docstring을 고친다.

## 범위 밖
- worker의 `touches 밖 충돌` 보고로 바로 수리로 보내기(범위 밖 touches-conflict-repair-route)
- `gs mutate` 같은 변이 실행 명령(범위 밖 gs-mutate-command)

## 참고
- spec §3 결정 2-5·2-6
