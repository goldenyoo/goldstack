---
id: "06"
title: "push 설정 변경을 정리 경고로 넘기지 않기"
blocked_by: []
touches: ["src/gs/clean.py", "tests/test_clean.py"]
tier: small
model: codex
reviewer: claude
---
## 목표
자동 integration 정리에서 push 설정 변경을 감지하면 사람이 알게 한다.

## 완료 조건
- `clean._remove`에서 `PushSettingsChanged`가 경고로 삼켜지지 않는다. `gs go`가 0이 아닌 종료 코드로 끝나고 바뀐 값을 보인다. 다른 정리 오류는 지금처럼 결과를 바꾸지 않는다.
- `clean.integration` docstring을 고친다. 시험: 설정 변경, 일반 오류.

## 범위 밖
- push 대조 자체.

## 참고
- `.goldstack/ideas/clean-push-settings-warning.md`
