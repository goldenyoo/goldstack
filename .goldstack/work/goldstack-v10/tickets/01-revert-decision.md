---
id: "01"
title: "되돌리기 판단을 순수 함수로(동작 그대로)"
blocked_by: []
touches: ["src/gs/finish.py", "src/gs/revert_decision.py", "tests/test_revert_decision.py"]
tier: large
model: claude
reviewer: codex
---
## 목표
`finish._postmerge`가 "지금 사실로 되돌리기를 어떻게 할지" 정하는 판단을 git·gh 호출에서 떼어 순수 함수 하나로 모은다. 재개 판단을 임시 git 레포 없이 시험하고, 02가 고칠 경로를 표에서 바로 보이게 한다.

## 완료 조건
- 새 모듈 `src/gs/revert_decision.py`의 함수가 이미 읽은 사실(phase, `revert_sha` 유무, `revert_head`와의 일치, revert가 base에 있는지, 외부 revert 유무, revert 부모와 base 끝의 일치, `direct_push`, 실패 뒤 base 이동 여부)을 받아 다음 단계 이름을 돌려준다. 이 함수는 git·gh·파일·시각을 부르지 않는다.
- `_postmerge`는 사실을 모아 이 함수에 묻고 답에 따라 부수 효과만 실행한다. 판단 분기가 `_postmerge`에 남지 않는다.
- `tests/test_revert_decision.py`가 임시 git 레포 없이 전이표로 모든 다음 단계를 시험한다.
- 기존 시험을 고치지 않고 전체 검증이 통과한다. 특히 `test_protected_base`, `test_go_finish`, `test_squash`, `test_resume_report`다.
- phase 이름과 `state.json` 형식은 그대로다. 옛 `state.json`을 그대로 읽는다.
- 사실을 미리 읽어도 동작이 달라지지 않는다. 특히 `revert_sha`가 없을 때 부모를 읽다가 오류가 나지 않고, 지금처럼 필요 없던 재검증이나 원격 호출이 늘지 않는다.
- 사실을 모으는 코드가 판단만큼 복잡해지면 거기서 멈춘다. 뺄 수 있는 분기만 빼고 남긴 분기와 이유를 마지막 메시지에 적는다.

## 범위 밖
- 승인 대기 중 base가 바뀐 경우의 동작 변경(02).
- `finish.run`, `go._resuming`, `go._finished_after_clean`의 재개 판단(범위 밖 `finish-resume-decisions`).
- phase 이름 변경, 파일 쪼개기.

## 참고
- spec §3의 1-5, `.goldstack/ideas/finish-phase-decisions.md`
