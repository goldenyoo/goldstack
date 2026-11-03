---
id: "02"
title: "second_reviewer·[agy] 설정과 검사"
blocked_by: ["01"]
model: codex
reviewer: claude
---
## 목표
티켓에 두 번째 리뷰어를 적을 수 있게 하고, agy 호출 상한 설정과 실행 전 검사를 만든다(실행 중 동작은 03).

## 완료 조건
- 티켓 frontmatter 선택 키 `second_reviewer`(claude | codex | agy). 구현 계열(`model`)이나 `reviewer`와 같으면 `gs check` 오류(시험).
- config `[agy] max_calls_per_run`(0 이상 정수, 없으면 3). 음수·정수 아님은 오류(시험). `gs init`이 쓰는 config 예시와 `gs config agy.max_calls_per_run`이 이 값을 보인다.
- `gs check`가 범위 안 티켓의 agy 배정 수(model·reviewer·second_reviewer가 agy인 것, 각 1회)를 세어 상한을 넘으면 경고, 상한이 0인데 배정이 있으면 경고(시험). 재시도·수정 단계는 미리 세지 않는다.
- 기존 v0–v3 티켓·config는 그대로 통과한다.

## 범위 밖
- 실제 두 리뷰 실행, 실행 중 횟수 세기·건너뜀, 보고서: 03

## 참고
- spec §3 1-8, 1-9, 2-4, 2-5. touches: `src/gs/feature.py` `src/gs/check.py` `src/gs/config.py` `tests/test_agy_config.py`
