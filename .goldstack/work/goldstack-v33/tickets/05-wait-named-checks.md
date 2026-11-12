---
id: "05"
title: "config로 기다릴 CI 검사 이름을 고른다"
blocked_by: []
touches: ["src/gs/config.py", "src/gs/finish.py", "src/gs/doctor.py", "tests/test_wait_checks.py", "tests/test_config.py", "tests/test_doctor.py"]
tier: large
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
`wait_checks = true`인 레포가 보호 규칙 없이도 기다릴 검사를 config로 고를 수 있게 한다. 적은 검사만 기다려 병합하고, 적은 검사가 PR에 나타나지 않으면 병합하지 않고 멈춘다(spec 1-4, 2-2).

## 완료 조건
- config `[git] checks`(문자열 목록, 기본 빈 목록). 비어 있으면 지금 동작 그대로다(보호·rulesets 필수 검사 → `gh pr checks --required` → 모든 검사). 비어 있지 않으면 그 이름들만 기다리고, 보호·rulesets 필수 검사 조회는 하지 않는다. 문자열 목록이 아니면 config 오류다.
- 적은 이름이 `checks_grace_seconds`가 지나도 PR 검사에 없으면 `"fail"`과 구분되는 결과로 멈춘다: 병합하지 않고 PR을 열어 둔 채 outcome `CI 검사 없음: <이름…>`. 지금의 `checks_failed`·`checks_timeout`처럼 다음 `gs go`가 다시 확인할 수 있다(재개 시 같은 판정). 적은 이름이 모두 `pass`·`skipping`이면 병합, 하나라도 `fail`·`cancel`이면 지금처럼 `CI 실패: <이름>`.
- 기능 PR, 보고서 PR, 직접 push 대신 여는 PR(`_side_pr` 경로)이 모두 같은 규칙을 쓴다.
- `gs doctor`의 필수 검사 행이 `checks`가 있으면 그 목록과 출처(config)를 보인다. `wait_checks = false`인데 `checks`가 있으면 경고 행.
- 시험(`tests/test_wait_checks.py` 등, 기존 `FAKE_GH`, 실제 시간에 기대지 않음): 적은 검사만 통과하고 다른 검사는 pending → 병합. 적은 검사 실패 → 병합 안 함. 적은 검사가 유예 뒤에도 없음 → `CI 검사 없음` + 병합 안 함, 다음 `gs go`가 같은 판정. `checks` 빈 목록 → 지금 시험 그대로 통과. config 형식 오류.
- `finish.py` 머리말·docstring과 `config.py` 기본 config 문자열을 맞춘다.

## 범위 밖
- 이 레포 `.goldstack/config.toml`과 workflow는 06
- CI 실패를 고치는 티켓 생성(범위 밖 `ci-fix-tickets`)
- 문서는 08

## 참고
- spec §3 1-4, 2-2, §6 CI·보호 줄
- `src/gs/finish.py` `_poll_checks`, `_required_checks`, `_wait_checks`
