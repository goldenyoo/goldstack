---
id: "06"
title: "verify_ticket, verify_retries, 보고서만 바뀌면 재검증 건너뜀"
blocked_by: ["05"]
model: codex
reviewer: claude
touches: ["src/gs/feature.py", "src/gs/verify.py", "src/gs/go.py", "src/gs/finish.py", "tests/test_verify_modes.py"]
---
## 목표
verify가 느리거나 flaky한 프로젝트에서 실행 시간을 줄이고 우연한 실패로 버리는 일을 줄인다.

## 완료 조건
- spec frontmatter `verify_ticket`(선택, 셸 한 줄): 있으면 티켓 worktree 검증은 이것, integration·integration-final·base 검증은 `verify`. worker brief의 검증 안내도 `verify_ticket`을 가리킨다(시험).
- spec frontmatter `verify_retries`(0 이상 정수, 기본 0): 모든 검증 지점에서 실패하면 그만큼 다시 돌린다. 재시도로 통과하면 그 지점을 통과로 보고 보고서에 `flaky: <지점> 재시도 <n>번 만에 통과`(시험: 첫 실패 뒤 통과, 끝까지 실패).
- integration-final: 직전에 통과한 integration head와 비교해 바뀐 파일이 그 feature의 report.md뿐이면 다시 돌리지 않고 `integration-final: 보고서만 바뀜, 건너뜀`을 남긴다(시험: 보고서만, 다른 파일도).
- 둘 다 없는 spec은 지금과 같다(기존 시험). 모르는 값(음수, 빈 문자열)은 `gs check` 오류.

## 범위 밖
- 검증을 아예 안 하는 모드(spec 1-7: `verify: "true"`로 명시)

## 참고
- spec §3 1-7, §6 verify 지점
