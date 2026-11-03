---
id: "04"
title: "보호된 base: revert·보고서를 PR로, 승인 대기와 알림"
blocked_by: ["03"]
model: claude
reviewer: codex
second_reviewer: agy
touches: ["src/gs/finish.py", "tests/test_protected_base.py"]
---
## 목표
base에 직접 push할 수 없는 저장소에서 gs가 base에 넣어야 할 커밋(revert, 최종 보고서)을 PR로 올리고, 승인이 필요하면 멈춰 사람을 부른다.

## 완료 조건
- `git.direct_push = false`면 revert는 `gs/<f>/revert` 브랜치→PR, 병합 뒤 최종 보고서는 `gs/<f>/report` 브랜치→PR로 올리고 `git.merge_method`로 병합을 시도한다(`wait_checks`면 그 PR의 검사도 기다림). base에 직접 push하는 명령은 하나도 나가지 않는다(시험: 가짜 원격이 base push를 거부).
- 병합이 승인 등 보호 규칙에 막히면 PR을 열어 둔 채 phase를 `revert_pending`·`report_pending`으로, outcome `사람 승인 필요: <PR url>`, 알림. 다음 `gs go`가 PR을 다시 읽어 병합됐으면 이어 간다(시험).
- feature PR 자체가 승인에 막히면 지금처럼 `merge_pending`, outcome에 `사람 승인 필요`가 드러나고 알림(시험).
- `direct_push = true`면 지금과 같다(기존 시험).

## 범위 밖
- 승인 자동화, 관리자 권한 우회

## 참고
- spec §3 1-4, §6 병합·revert
