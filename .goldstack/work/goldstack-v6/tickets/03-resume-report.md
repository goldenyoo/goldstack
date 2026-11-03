---
id: "03"
title: "보호된 base 재개 보고서 충돌, 옛 error 지우기, 저장 전 오류 난 보고서 PR 찾기"
blocked_by: ["01"]
touches: ["src/gs/finish.py", "src/gs/go.py", "tests/test_resume_report.py"]
model: claude
reviewer: codex
second_reviewer: agy
---
## 목표
병합 뒤 base에 보고서 커밋이 들어가는 흐름(직접 push·보고서 PR 모두)에서, 재개한 실행과 다음 실행이 report.md 충돌이나 어긋난 보고서 없이 끝나게 한다.

## 완료 조건
- 재개(`RESUME_PHASES`·`report_pending` 등)가 `verified`·`reverted`로 끝나면, base(보고서 커밋 포함)를 integration에 합친 뒤 그 실행은 멈춘다: `_loop`와 두 번째 `_finish_run`을 돌지 않는다. 남은 티켓이 있으면 출력에 "남은 티켓 N개 → 다음 gs go"를 보이고, 다음 `gs go`는 base를 합친 integration 위에서 시작한다.
- base에 보고서 커밋을 넣는 단계(`_report_to_base`: 직접 push·보고서 PR)는 base를 integration에 합치는 단계(`merge_base`)보다 앞에 온다. 그 뒤 `_update`가 integration report.md를 base판과 다르게 다시 쓰지 않는다(시험: base의 report.md == integration의 report.md).
- 재현 시험(v5 04 리뷰 agy [high] 경로): 보호된 base에서 보고서 PR 승인 대기 → 승인 → `gs go` 재개 → 남은 티켓이 있는 상태로 다시 `gs go` → 충돌 없이 병합·verified. 새 티켓이 없는 재개도 시험. direct push에서 merged 회복 + 새 티켓도 시험.
- 성공(병합 확인, 보고서 PR 병합, revert PR 병합)하면 `finish['error']`를 지운다. 최종 보고서 Merge Danger에 이전 승인 거부·일시 오류가 남지 않는다(시험).
- `_side_pr`에서 PR 생성 응답이 실패·빈 출력이어도(GitHub 쪽에는 PR이 생겼을 수 있음), 다음 실행이 `gs/<f>/report`(·`revert`) 브랜치의 열린 PR을 찾아 `report_pending`(·`revert_pending`)으로 이어 간다. `base_report_tried=True`로 덮어 버리지 않는다(시험: 가짜 gh가 생성 뒤 오류).

## 범위 밖
- setup 추적 파일: 04, squash 되살림·CI 등록 대기: 05

## 참고
- spec §3 1-5, §6 ① 보고서 충돌·① 같은 자리, 아이디어 `protected-base-resume-report-conflict`
- 시험 도우미: `tests/test_protected_base.py` `ProtectedBaseTest`(protect·approve·base_report·assert_no_base_push)
