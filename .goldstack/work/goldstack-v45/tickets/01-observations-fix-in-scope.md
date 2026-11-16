---
id: "01"
title: "brief: touches 안 결함과 완료 조건 위반은 관찰로 남기지 말고 고친다"
blocked_by: []
touches: ["src/gs/worker.py", "tests/test_brief_rules.py", "tests/test_fix_brief.py", "tests/test_review_observations.py"]
tier: small
model: claude
reviewer: codex
---
## 목표
worker가 touches 안에서 고칠 수 있는 결함이나 완료 조건을 어기는 것을 알아채고도 `## 남긴 관찰`에만 적어, 그 관찰이 리뷰 fix 지적이 되어 수정·재리뷰가 일렬 경로에 붙는 일을 줄인다(goldstack-v44 02: 1,135초, 실행의 17%).

## 완료 조건
- `src/gs/worker.py` `OBSERVATIONS_RULE`이 다음 뜻을 담는다: 완료 조건을 어기는 것과 touches 안에서 고칠 수 있는 결함은 관찰로 남기지 말고 고친다. 관찰 절에는 touches 밖에서 고쳐야 할 것, 돌리지 못한 확인, 사람 판단이 필요한 것만 쓴다. 기존 뜻(관찰 절 제목·한 줄에 하나·없으면 절을 쓰지 않는다·touches 밖이나 레포 밖에서 판단해서 한 일)은 그대로다.
- 이 규칙은 모든 brief(첫·재개 worker, 수정, 수리, replay)에 그대로 붙는다(`write_brief` 하나가 쓴다).
- `tests/test_brief_rules.py`가 새 문장의 핵심 낱말(규칙 문장의 실제 낱말, 예: "완료 조건"과 "고친다")이 첫 worker brief와 수정 brief에 함께 있음을 단언한다. 새 문장을 지우면 그 시험이 실패한다.
- `write_brief` docstring의 `OBSERVATIONS_RULE` 설명을 새 뜻에 맞게 고친다.

## 범위 밖
- gs가 touches 안 관찰을 리뷰 전에 worker에게 되돌리는 것(out-of-scope `observation-return-to-worker`).
- 범위 밖 관찰을 하류 brief에 싣는 것(03).

## 참고
- spec §3 결정 1-2, 아이디어 `worker-fix-in-scope-observations`.
- goldstack-v42 01 커밋 `38b83f7`(브랜치 `gs/goldstack-v42/01`, 병합되지 않음)이 같은 변경을 했다. 참고로 읽어도 된다.
