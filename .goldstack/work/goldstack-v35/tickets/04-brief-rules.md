---
id: "04"
title: "brief: 남긴 관찰 절, touches, 중첩 세션, 시험 나눠 돌리기"
blocked_by: []
touches: ["src/gs/worker.py", ".goldstack/profile.md", "tests/test_brief_rules.py", "tests/test_fix_brief.py"]
tier: medium
model: claude
reviewer: codex
---
## 목표
worker brief가 다음 넷을 알린다: 고치지 않고 남긴 관찰을 쓰는 고정 절, 그 티켓의 `touches`, 중첩 세션을 띄우는 법, 시험 파일 상한에 걸릴 때 나눠 돌리기(spec 2-2, 2-3, 3-4, 아이디어 `worker-test-file-limit-friction`).

## 완료 조건
- 절 제목 `## 남긴 관찰`을 `worker.py`의 상수 하나(예: `OBSERVATIONS_HEADING`)로 두고, brief가 "고치지 않고 남긴 관찰(리뷰가 짚지 않은 의심, 돌리지 못한 확인, touches 밖에서 고쳐야 할 것)이 있으면 마지막 메시지 끝에 이 제목 아래 한 줄에 하나씩 쓴다. 없으면 절을 쓰지 않는다"를 말한다. 첫 worker·재개·수정·수리 brief 모두.
- 첫 worker·재개 worker brief에 그 티켓의 `touches` 목록과 "touches 밖 파일은 고치지 않는다. 고쳐야 하면 `## 남긴 관찰`에 적는다". `touches`가 없는 티켓이면 그 줄을 쓰지 않는다. 수정·수리 worker의 고칠 수 있는 파일(이 티켓 + 이미 병합된 티켓의 touches)은 `review._fixable_lines`가 이미 알리므로 바꾸지 않고, 그 brief에 첫 worker용 touches 줄을 겹쳐 넣지 않는다(교차 검토 2: 병합된 티켓 파일 수정 허용과 충돌하지 않게).
- brief에 "측정용으로 claude·codex 세션을 띄우면 `gs child -- <명령>`으로 띄우고 모델·effort를 명령에 명시한다. `GS_*`를 지우지 않는다".
- brief의 시험 규칙(v33 03의 "grep해 나온 시험 파일을 모두 돌린다")에 "hook이 한 명령의 시험 파일 수를 막으면 명령을 나눠 돌린다. 일부를 빼지 않는다". 상한 숫자는 brief에 적지 않는다(레포 config 값이다).
- `.goldstack/profile.md` 주의점의 "동작을 바꾸면 docstring과 `docs/internals.md`도 고친다"를 "docstring은 고친다. `docs/internals.md`는 touches에 있을 때만 고친다"로.
- `tests/test_brief_rules.py`·`tests/test_fix_brief.py`: 첫 worker와 수정 worker brief에 절 제목 상수, `gs child`, 나눠 돌리기 문장이 있다. 첫 worker brief에 touches 목록이 있고, touches 없는 티켓 brief에는 그 줄이 없다. 수정 worker brief의 고칠 수 있는 파일 목록은 지금과 같다(`tests/test_judge_scope.py`가 그대로 통과). 첫 시험은 고치기 전 코드에서 실패한다.

## 범위 밖
- 절을 뽑아 리뷰·보고서에 싣기는 05
- touches 밖 변경을 gs가 diff로 대조·실패 처리(spec 3-4에서 뺌)
- `gs child` 구현은 03

## 참고
- spec §3 2-2, 2-3, 3-2, 3-4, §6 brief·profile 줄
- `.goldstack/ideas/worker-edits-outside-touches.md`, `worker-test-file-limit-friction.md`
